from __future__ import annotations

"""Runtime integration for adaptive server selection and connection failover.

A public VPN endpoint can be stale even when discovery data looks healthy.
This module performs fresh discovery, skips quarantined endpoints, and treats
provider authentication/transport failures as endpoint-level failures.
"""

import sys
import time

import standalone_engine as engine
from smart_controller import SmartController
from openvpn_compat import install as install_openvpn_compat

install_openvpn_compat(engine)

controller = SmartController()
_original_discover = engine.discover
_original_connect = engine.connect


def discover(deadline: float = 10):
    servers = _original_discover(deadline)
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


def _same_endpoint(a: dict, b: dict) -> bool:
    ah = str((a or {}).get("host") or "").lower()
    bh = str((b or {}).get("host") or "").lower()
    ai = str((a or {}).get("ip") or "").lower()
    bi = str((b or {}).get("ip") or "").lower()
    return bool(ah and ah == bh) or (bool(ai) and ai == bi)


def _failure_is_endpoint_specific(exc: Exception) -> bool:
    text = str(exc).lower()
    endpoint_errors = (
        "control-channel push exchange",
        "tls handshake",
        "tls error",
        "connection refused",
        "connection timeout",
        "transport startup timeout",
        "network unreachable",
        "server did not complete",
        "all connection methods failed",
        "openvpn exited",
        "authentication failed",
        "auth_failed",
        "auth failed",
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
    return _original_discover(deadline=max(6.0, min(15.0, deadline)))


def _ranked_fallbacks(failed_server: dict, deadline: float) -> list[dict]:
    try:
        fresh = _fresh_discovery(deadline)
    except Exception as exc:
        engine.log(f"FAILOVER DISCOVERY FAILED error={type(exc).__name__}: {exc}")
        return []
    ranked = controller.rank(fresh)
    candidates = [
        s for s in ranked
        if isinstance(s, dict) and not _same_endpoint(s, failed_server)
    ]
    engine.log(
        "FAILOVER CANDIDATES discovered=%d usable=%d candidates=%s"
        % (
            len(fresh),
            len(candidates),
            ",".join(str(s.get("host") or "") for s in candidates[:24]),
        )
    )
    return candidates


def connect(server: dict, total_deadline: float = 60):
    started = time.monotonic()
    host = str(server.get("host") or "")
    # Public relays are inherently slow/unreliable. Give recovery enough time
    # to test independent endpoints instead of failing after a handful.
    deadline = started + max(120.0, float(total_deadline))
    last_error: Exception | None = None
    attempted: set[str] = set()

    def attempt(candidate: dict, budget: float):
        candidate_host = str(candidate.get("host") or "")
        candidate_key = f"{candidate_host.lower()}|{str(candidate.get('ip') or '')}"
        attempted.add(candidate_key)
        engine.log(f"FAILOVER ATTEMPT host={candidate_host} ip={candidate.get('ip')} budget={budget:.1f}s")
        attempt_started = time.monotonic()
        try:
            result = _original_connect(candidate, total_deadline=min(30.0, max(8.0, budget)))
            elapsed_ms = (time.monotonic() - attempt_started) * 1000.0
            controller.update(candidate_host, elapsed_ms, True)
            engine.log(f"SMART RESULT server={candidate_host} success=1 elapsed_ms={elapsed_ms:.0f}")
            return result
        except Exception as exc:
            elapsed_ms = (time.monotonic() - attempt_started) * 1000.0
            controller.update(candidate_host, elapsed_ms, False)
            engine.log(
                f"SMART RESULT server={candidate_host} success=0 elapsed_ms={elapsed_ms:.0f} "
                f"error={type(exc).__name__}: {exc}"
            )
            raise

    try:
        return attempt(server, deadline - time.monotonic())
    except Exception as exc:
        last_error = exc
        if not _failure_is_endpoint_specific(exc):
            raise

    candidates = _ranked_fallbacks(server, max(8.0, min(15.0, deadline - time.monotonic())))
    for candidate in candidates[:24]:
        remaining = deadline - time.monotonic()
        if remaining < 8.0:
            break
        candidate_key = f"{str(candidate.get('host') or '').lower()}|{str(candidate.get('ip') or '')}"
        if candidate_key in attempted:
            continue
        try:
            engine.log(
                f"FAILOVER SWITCH from={host} to={candidate.get('host')} "
                f"ip={candidate.get('ip')} remaining={remaining:.1f}s"
            )
            return attempt(candidate, remaining)
        except Exception as exc:
            last_error = exc
            if not _failure_is_endpoint_specific(exc):
                break

    engine.log(
        f"FAILOVER EXHAUSTED initial={host} attempts={len(attempted)} "
        f"last_error={type(last_error).__name__ if last_error else 'unknown'}: {last_error}"
    )
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
