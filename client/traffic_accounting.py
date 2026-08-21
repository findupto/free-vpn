"""Crash-tolerant in-process traffic/session accounting."""
from __future__ import annotations
from dataclasses import dataclass, asdict
import json, time

@dataclass
class TrafficSnapshot:
    started_at: float
    connected_at: float | None = None
    disconnected_at: float | None = None
    bytes_up: int = 0
    bytes_down: int = 0
    packets_up: int = 0
    packets_down: int = 0

class TrafficAccounting:
    def __init__(self):
        self.session: TrafficSnapshot | None = None
    def start(self, now: float | None = None) -> TrafficSnapshot:
        self.session = TrafficSnapshot(now if now is not None else time.time())
        self.session.connected_at = self.session.started_at
        return self.session
    def add(self, up: int = 0, down: int = 0, packets_up: int = 0, packets_down: int = 0) -> None:
        if self.session is None:
            self.start()
        if min(up, down, packets_up, packets_down) < 0:
            raise ValueError("traffic counters cannot be negative")
        self.session.bytes_up += int(up); self.session.bytes_down += int(down)
        self.session.packets_up += int(packets_up); self.session.packets_down += int(packets_down)
    def stop(self, now: float | None = None) -> TrafficSnapshot:
        if self.session is None:
            raise RuntimeError("no active session")
        self.session.disconnected_at = now if now is not None else time.time()
        return self.session
    def export(self) -> str:
        return json.dumps(asdict(self.session) if self.session else None, sort_keys=True)
