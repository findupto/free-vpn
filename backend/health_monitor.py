"""Health monitor with rolling availability and latency statistics."""

from __future__ import annotations

import statistics
import time
from collections import defaultdict, deque


class HealthMonitor:
    def __init__(self, window: int = 20, stale_after: int = 300):
        self.window = max(3, int(window))
        self.stale_after = max(1, int(stale_after))
        self.status: dict[str, dict] = {}
        self.history: dict[str, deque[dict]] = defaultdict(lambda: deque(maxlen=self.window))

    def update(self, server_id: str, metrics: dict) -> None:
        now = int(time.time())
        sample = dict(metrics)
        sample["updated"] = now
        self.history[server_id].append(sample)
        self.status[server_id] = {
            "metrics": sample,
            "updated": now,
            "health": self.health_score(server_id),
        }

    def health_score(self, server_id: str) -> int:
        samples = list(self.history.get(server_id, ()))
        if not samples:
            return 0
        success = sum(1 for item in samples if item.get("success", bool(item))) / len(samples)
        latencies = [float(item["latency_ms"]) for item in samples if item.get("latency_ms") is not None]
        latency = statistics.median(latencies) if latencies else 5000.0
        latency_score = max(0.0, 100.0 - min(latency, 5000.0) / 50.0)
        return round(success * 70 + latency_score * 0.3)

    def healthy_servers(self, min_score: int = 60) -> list[str]:
        now = int(time.time())
        threshold = max(0, min(int(min_score), 100))
        return [
            server_id
            for server_id, state in self.status.items()
            if now - int(state.get("updated", 0)) <= self.stale_after
            and int(state.get("health", 0)) >= threshold
        ]
