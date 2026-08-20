from __future__ import annotations

"""Runtime integration for adaptive server selection.

This module intentionally wraps the existing standalone engine instead of
replacing its OpenVPN implementation. It adds measured history, quarantine,
and smart ordering without changing the GUI contract.
"""

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


def connect(server: dict, total_deadline: float = 60):
    started = time.monotonic()
    host = str(server.get("host") or "")
    try:
        result = _original_connect(server, total_deadline)
        elapsed_ms = (time.monotonic() - started) * 1000.0
        controller.update(host, elapsed_ms, True)
        engine.log(f"SMART RESULT server={host} success=1 elapsed_ms={elapsed_ms:.0f}")
        return result
    except Exception as exc:
        elapsed_ms = (time.monotonic() - started) * 1000.0
        controller.update(host, elapsed_ms, False)
        engine.log(
            f"SMART RESULT server={host} success=0 elapsed_ms={elapsed_ms:.0f} "
            f"error={type(exc).__name__}: {exc}"
        )
        raise


# Patch the already-imported module object used by gui.py.
engine.discover = discover
engine.connect = connect
