"""Smart automatic VPN optimization controller.

Combines server quality signals and chooses the best available strategy.
"""

from dataclasses import dataclass
from time import time


@dataclass
class OptimizationDecision:
    server: str | None
    score: float
    reason: str
    timestamp: int


class SmartAutoOptimizer:
    def __init__(self):
        self.history = {}

    def record_result(self, server, quality):
        values = self.history.setdefault(server, [])
        values.append(float(quality))
        if len(values) > 100:
            values.pop(0)

    def _history_score(self, server):
        values = self.history.get(server, [])
        if not values:
            return 0
        return sum(values) / len(values)

    def choose_server(self, servers):
        if not servers:
            return OptimizationDecision(None, 0, "no servers available", int(time()))

        best = None
        best_score = -1

        for server in servers:
            score = (
                float(server.get("health", 0)) * 0.35
                + float(server.get("speed", 0)) * 0.35
                + float(server.get("stability", 0)) * 0.20
                + self._history_score(server.get("id", "")) * 0.10
            )

            if score > best_score:
                best = server
                best_score = score

        return OptimizationDecision(
            best.get("id") if best else None,
            best_score,
            "highest combined performance score",
            int(time()),
        )


optimizer = SmartAutoOptimizer()
