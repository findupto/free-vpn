from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class ServerScore:
    host: str
    latency_ms: float = 9999
    reliability: float = 0.0
    failures: int = 0
    last_used: float = 0.0

    def score(self) -> float:
        latency_score = max(0.0, 1000.0 - self.latency_ms)
        reliability_score = self.reliability * 1000
        failure_penalty = self.failures * 250
        return latency_score + reliability_score - failure_penalty


class SmartController:
    """Connection intelligence layer.

    Selects servers using measured performance instead of fixed ordering.
    """

    def __init__(self):
        self.history: dict[str, ServerScore] = {}
        self.blocked: dict[str, float] = {}

    def update(self, host: str, latency_ms: float, success: bool):
        item = self.history.setdefault(host, ServerScore(host))
        item.latency_ms = latency_ms
        item.last_used = time.time()
        if success:
            item.reliability = min(1.0, item.reliability + 0.1)
            item.failures = max(0, item.failures - 1)
        else:
            item.failures += 1
            item.reliability = max(0.0, item.reliability - 0.2)
            self.blocked[host] = time.time() + 300

    def rank(self, servers: list[dict]) -> list[dict]:
        now = time.time()
        available = [s for s in servers if self.blocked.get(s.get('host'), 0) < now]
        return sorted(available, key=lambda s: self.history.get(s.get('host'), ServerScore(s.get('host', ''))).score(), reverse=True)
