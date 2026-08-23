from __future__ import annotations

"""Runtime integration for adaptive server selection and connection failover.

The UI should never wait for a fresh provider scan when a valid local catalog
already exists. Discovery is cache-first; fresh provider data is refreshed in
one background task. Fast connection calls also avoid nested failover because
app.py already owns the candidate loop.
"""

import threading
import sys
import time

import standalone_engine as engine
from smart_controller import SmartController
from openvpn_compat import install as install_openvpn_compat

install_openvpn_compat(engine)

controller = SmartController()
_original_discover = engine.discover
_original_connect = engine.connect
_refresh_lock = threading.Lock()
_refresh_running = False


def _rank(servers):
    ranked = controller.rank(servers)
    engine.log(
        "SMART RANK candidates=%d usable=%d top=%s"
        % (
            len(servers),
            len(ranked),
            ",".join(
                f"{s.get('host','')}:{float(s.get('smart_rank', 0.0)):.0f}"
                for s in ranked[:5]
            ),
        )
    )
    return ranked


def _background_refresh():
    global _refresh_running
    try:
        fresh = _original_discover(deadline=6.0)
        engine.log(f"BACKGROUND DISCOVERY COMPLETE servers={len(fresh)}")
    except Exception as exc:
        engine.log(f"BACKGROUND DISCOVERY FAILED error={type(exc).__name__}: {exc}")
    finally:
        with _refresh_lock:
            _refresh_running = False


def discover(deadline: float = 10):
    """Return cached servers immediately and refresh provider data once.

    This is the key latency optimization for the server browser: filtering and
    connection selection can begin from the local catalog without waiting for
    VPN Gate/VPNBook HTTP requests.
    """
    global _refresh_running
    cached = []
    try:
        loader = getattr(engine, "_cache_load", None)
        if callable(loader):
            cached = loader()
    except Exception as exc:
        engine.log(f"CACHE-FIRST LOAD FAILED error={type(exc).__name__}: {exc}")

    if cached:
        ranked = _rank(cached)
        with _refresh_lock:
            if not _refresh_running:
                _refresh_running = True
                threading.Thread(
                    target=_background_refresh,
                    daemon=True,
                    name="findupto-background-discovery",
                ).start()
        engine.log(f"CACHE-FIRST READY servers={len(ranked)} background_refresh=1")
        return ranked

    # Cold start: parallel provider discovery, but keep the wait bounded.
    fresh = _original_discover(deadline=max(4.0, min(7.0, float(deadline))))
    return _rank(fresh)


def _same_endpoint(a: dict, b: dict) -> bool:
    ah = str((a or {}).get("host") or "").lower()
    bh = str((b or {}).get("host") or "").lower()
    ai = str((a or {}).get("ip") or "").lower()
    bi = str((b or {}).get("ip") or "").lower()
    return bool(ah and ah == bh) or (bool(ai) and ai == bi)


def _failure_is_endpoint_specific(exc: Exception) -> bool:
    text = str(exc).lower()
    endpoint_errors = (
        "control-channel push exchange", "tls handshake", "tls error",
        "connection refused", "connection timeout", "transport startup timeout",
        "network unreachable", "server did not complete", "all connection methods failed",
        "openvpn exited", "authentication failed", "auth_failed", "auth failed",
        "bad username or password",
    )
    return any(token in text for token in endpoint_errors)


def _fresh_discovery(deadline: float) -> list[dict]:
    """Discard stale cache before an explicit recovery scan."""
    cache = getattr(engine, "CACHE", None)
    if cache is not None:
        try:
            cache.unlink(missing_ok=True)
            engine.log("FAILOVER CACHE CLEARED for fresh provider discovery")
        except Exception as exc:
            engine.log(f"FAILOVER CACHE CLEAR FAILED error={type(exc).__name__}: {exc}")
    return _original_discover(deadline=max(5.0, min(10.0, deadline)))


def _ranked_fallbacks(failed_server: dict, deadline: float) -> list[dict]:
    try:
        fresh = _fresh_discovery(deadline)
    except Exception as exc:
        engine.log(f"FAILOVER DISCOVERY FAILED error={type(exc).__name__}: {exc}")
        return []
    candidates = [s for s in _rank(fresh) if isinstance(s, dict) and not _same_endpoint(s, failed_server)]
    engine.log(
        "FAILOVER CANDIDATES discovered=%d usable=%d candidates=%s"
        % (len(fresh), len(candidates), ",".join(str(s.get("host") or "") for s in candidates[:16]))
    )
    return candidates


def connect(server: dict, total_deadline: float = 60):
    """Connect with a fast single-endpoint path for UI candidate loops.

    app.py deliberately supplies a 22-second budget and its own candidate list.
    In that mode, don't start another discovery/failover loop inside this
    function. This removes the previous nested 24-server retry explosion.
    """
    fast_path = float(total_deadline) <= 30.0 or bool(server.get("_fast_path"))
    if fast_path:
        started = time.monotonic()
        host = str(server.get("host") or server.get("ip") or "")
        try:
            result = _original_connect(server, total_deadline=min(22.0, max(8.0, float(total_deadline))))
            controller.update(host, (time.monotonic() - started) * 1000.0, True)
            return result
        except Exception as exc:
            controller.update(host, (time.monotonic() - started) * 1000.0, False)
            raise

    started = time.monotonic()
    deadline = started + max(45.0, float(total_deadline))
    attempted: set[str] = set()
    last_error: Exception | None = None

    def attempt(candidate: dict, budget: float):
        host = str(candidate.get("host") or candidate.get("ip") or "")
        key = f"{host.lower()}|{str(candidate.get('ip') or '')}"
        attempted.add(key)
        t0 = time.monotonic()
        engine.log(f"FAILOVER ATTEMPT host={host} ip={candidate.get('ip')} budget={budget:.1f}s")
        try:
            result = _original_connect(candidate, total_deadline=min(22.0, max(8.0, budget)))
            controller.update(host, (time.monotonic() - t0) * 1000.0, True)
            return result
        except Exception as exc:
            controller.update(host, (time.monotonic() - t0) * 1000.0, False)
            raise

    try:
        return attempt(server, deadline - time.monotonic())
    except Exception as exc:
        last_error = exc
        if not _failure_is_endpoint_specific(exc):
            raise

    for candidate in _ranked_fallbacks(server, min(8.0, max(5.0, deadline - time.monotonic())))[:12]:
        remaining = deadline - time.monotonic()
        if remaining < 8.0:
            break
        key = f"{str(candidate.get('host') or '').lower()}|{str(candidate.get('ip') or '')}"
        if key in attempted:
            continue
        try:
            return attempt(candidate, remaining)
        except Exception as exc:
            last_error = exc
            if not _failure_is_endpoint_specific(exc):
                break

    raise RuntimeError(
        f"No working VPN endpoint was found after testing {len(attempted)} servers. "
        f"Last endpoint error: {last_error or 'unknown'}"
    ) from last_error


engine.discover = discover
engine.connect = connect

try:
    from gui_modern import App as ModernApp
    import types
    modern_module = types.ModuleType("gui_spinner")
    modern_module.App = ModernApp
    sys.modules["gui_spinner"] = modern_module
except Exception as exc:
    engine.log(f"MODERN GUI BOOTSTRAP FAIL error={type(exc).__name__}: {exc}")
