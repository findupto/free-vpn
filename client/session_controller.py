from __future__ import annotations

"""Thread-safe lifecycle helpers for VPN sessions.

The controller deliberately knows nothing about OpenVPN itself. It provides the
state machine and process teardown policy used by the desktop client so that
Disconnect and Change IP cannot race with a connection attempt.
"""

from dataclasses import dataclass
from enum import Enum
from threading import RLock
from typing import Any, Callable, Iterable, Optional


class SessionState(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    CHANGING_IP = "changing_ip"
    DISCONNECTING = "disconnecting"
    ERROR = "error"


@dataclass
class Session:
    state: SessionState = SessionState.DISCONNECTED
    server: Optional[dict[str, Any]] = None
    public_ip: Optional[str] = None
    process: Any = None


class SessionController:
    """Serialize tunnel lifecycle operations and choose alternate endpoints."""

    def __init__(self) -> None:
        self._lock = RLock()
        self.session = Session()

    @property
    def state(self) -> SessionState:
        with self._lock:
            return self.session.state

    def begin_connect(self, server: dict[str, Any]) -> bool:
        with self._lock:
            if self.session.state not in {SessionState.DISCONNECTED, SessionState.ERROR}:
                return False
            self.session = Session(state=SessionState.CONNECTING, server=server)
            return True

    def mark_connected(self, process: Any, public_ip: str) -> None:
        with self._lock:
            self.session.process = process
            self.session.public_ip = public_ip
            self.session.state = SessionState.CONNECTED

    def begin_change_ip(self) -> bool:
        with self._lock:
            if self.session.state != SessionState.CONNECTED:
                return False
            self.session.state = SessionState.CHANGING_IP
            return True

    def mark_change_target(self, server: dict[str, Any]) -> None:
        with self._lock:
            self.session.server = server
            self.session.process = None
            self.session.public_ip = None
            self.session.state = SessionState.CONNECTING

    def mark_error(self) -> None:
        with self._lock:
            self.session.state = SessionState.ERROR
            self.session.process = None

    def mark_disconnected(self) -> None:
        with self._lock:
            self.session = Session()

    def terminate_process(self, process: Any, timeout: float = 5.0) -> None:
        """Best-effort graceful termination followed by a hard kill."""
        if process is None:
            return
        try:
            if process.poll() is not None:
                return
            process.terminate()
            try:
                process.wait(timeout=timeout)
            except Exception:
                process.kill()
                try:
                    process.wait(timeout=2)
                except Exception:
                    pass
        except Exception:
            # Disconnect must remain idempotent even when the process vanished.
            return

    def disconnect(self, process: Any = None) -> None:
        with self._lock:
            self.session.state = SessionState.DISCONNECTING
            active = process if process is not None else self.session.process
        self.terminate_process(active)
        self.mark_disconnected()

    @staticmethod
    def alternate_servers(servers: Iterable[dict[str, Any]], current: Optional[dict[str, Any]]) -> list[dict[str, Any]]:
        """Return usable candidates, preferring a different host/IP from current."""
        current_host = str((current or {}).get("host", "")).lower()
        current_ip = str((current or {}).get("ip", "")).lower()
        candidates = []
        for server in servers:
            if not isinstance(server, dict):
                continue
            if server.get("disabled") or server.get("status") in {"offline", "failed", "quarantined"}:
                continue
            host = str(server.get("host", "")).lower()
            ip = str(server.get("ip", "")).lower()
            if host == current_host and ip == current_ip:
                continue
            candidates.append(server)
        return candidates

    def run_change_ip(
        self,
        servers: Iterable[dict[str, Any]],
        current: Optional[dict[str, Any]],
        connect: Callable[[dict[str, Any]], tuple[Any, str]],
    ) -> tuple[dict[str, Any], Any, str]:
        """Try alternate endpoints until a verified, different public IP is obtained."""
        if not self.begin_change_ip():
            raise RuntimeError("No active VPN session to change")

        previous_ip = self.session.public_ip
        last_error: Optional[Exception] = None
        for server in self.alternate_servers(servers, current):
            self.mark_change_target(server)
            try:
                process, new_ip = connect(server)
                if previous_ip and new_ip == previous_ip:
                    self.terminate_process(process)
                    last_error = RuntimeError(f"Endpoint returned the same exit IP: {new_ip}")
                    continue
                self.mark_connected(process, new_ip)
                return server, process, new_ip
            except Exception as exc:
                last_error = exc
                self.mark_error()

        self.mark_error()
        raise RuntimeError("Unable to obtain a different VPN exit IP") from last_error
