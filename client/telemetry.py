"""Privacy-first local telemetry primitives. No network transport is performed here."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from collections import deque
import json, re, time

_SECRET = re.compile(r"(?i)(token|password|passwd|secret|private[_-]?key|authorization)\s*[:=]\s*[^,\s]+")
_IP = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")

@dataclass(frozen=True)
class Event:
    name: str
    timestamp: float
    data: dict

class Redactor:
    @staticmethod
    def text(value: object) -> str:
        text = str(value)
        text = _SECRET.sub(lambda m: m.group(1) + "=<redacted>", text)
        return _IP.sub("<ip>", text)
    @classmethod
    def mapping(cls, value: dict) -> dict:
        out = {}
        for k, v in value.items():
            if re.search(r"(?i)token|password|secret|private[_-]?key|authorization", str(k)):
                out[str(k)] = "<redacted>"
            else:
                out[str(k)] = cls.text(v) if isinstance(v, (str, int, float)) else v
        return out

class EventBuffer:
    def __init__(self, max_events: int = 1000):
        self.events = deque(maxlen=max(1, int(max_events)))
    def record(self, name: str, **data) -> Event:
        event = Event(str(name), time.time(), Redactor.mapping(data))
        self.events.append(event)
        return event
    def export_json(self) -> str:
        return json.dumps([asdict(e) for e in self.events], sort_keys=True, separators=(",", ":"))
    def clear(self) -> None:
        self.events.clear()
