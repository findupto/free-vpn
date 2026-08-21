"""Local, privacy-preserving observability primitives."""
from __future__ import annotations
from dataclasses import dataclass, field
from time import time

@dataclass(frozen=True)
class Event:
    name: str
    timestamp: float
    fields: dict[str, object] = field(default_factory=dict)

class EventLog:
    def __init__(self, max_events: int = 5000):
        self.max_events = max(1, max_events)
        self._events: list[Event] = []
    def record(self, name: str, **fields) -> None:
        self._events.append(Event(name, time(), dict(fields)))
        if len(self._events) > self.max_events:
            del self._events[:len(self._events) - self.max_events]
    def snapshot(self) -> list[Event]:
        return list(self._events)
    def clear(self) -> None:
        self._events.clear()
