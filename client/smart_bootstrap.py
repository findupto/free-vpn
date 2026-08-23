from __future__ import annotations

"""Runtime integration for adaptive server selection and connection failover.

This module wraps the existing OpenVPN engine instead of replacing it. A public
VPN endpoint can be stale even when discovery data looks healthy, so a failed
control-channel/TLS attempt is treated as an endpoint failure and the engine
automatically advances through freshly ranked candidates.
"""

import sys
import time

import standalone_engine as engine
from smart_controller import SmartController

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
    )
    return any(token in text for token in endpoint_errors)


def _ranked_fallbacks(failed_server: dict, deadline: float) -> list[dict]:
    """Refresh discovery after an endpoint failure and return new candidates."""
    try:
        fresh = _original_discover(deadline=max(4.0, min(10.0, deadline)))
    except Exception as exc:
        engine.log(f"FAILOVER DISCOVERY FAILED error={type(exc).__name__}: {exc}")
        return []
    ranked = controller.rank(fresh)
    candidates = [s for s in ranked if isinstance(s, dict) and not _same_endpoint(s, failed_server)]
    engine.log(
        "FAILOVER CANDIDATES discovered=%d usable=%d candidates=%s"
        % (len(fresh), len(candidates), ",".join(str(s.get("host") or "") for s in candidates[:8]))
    )
    return candidates


def connect(server: dict, total_deadline: float = 60):
    started = time.monotonic()
    host = str(server.get("host") or "")
    deadline = started + max(8.0, float(total_deadline))
    last_error: Exception | None = None
    attempted: set[str] = set()

    def attempt(candidate: dict, budget: float):
        candidate_host = str(candidate.get("host") or "")
        attempted.add(candidate_host.lower())
        engine.log(f"FAILOVER ATTEMPT host={candidate_host} budget={budget:.1f}s")
        attempt_started = time.monotonic()
        try:
            result = _original_connect(candidate, total_deadline=min(30.0, max(5.0, budget)))
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

    # The first endpoint failed during the actual OpenVPN negotiation. Do not
    # make the user manually test countries one by one. Refresh the catalog and
    # immediately try a small number of independent endpoints.
    candidates = _ranked_fallbacks(server, max(4.0, min(8.0, deadline - time.monotonic())))
    for candidate in candidates[:8]:
        remaining = deadline - time.monotonic()
        if remaining < 5.0:
            break
        candidate_host = str(candidate.get("host") or "").lower()
        if candidate_host in attempted:
            continue
        try:
            engine.log(f"FAILOVER SWITCH from={host} to={candidate.get('host')} remaining={remaining:.1f}s")
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


# Patch the already-imported module object used by the GUI. app.py imports
# standalone_engine after this bootstrap, so it receives this failover-aware
# connect function automatically.
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
