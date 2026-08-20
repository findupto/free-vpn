from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class ServerScore:
    host: str
    latency_ms: float = 9999.0
    reliability: float = 0.0
    failures: int = 0
    last_used: float = 0.0
    samples: int = 0

    def score(self, base_rank: float = 0.0) -> float:
        latency_score = max(0.0, 1500.0 - self.latency_ms)
        reliability_score = self.reliability * 1800.0
        failure_penalty = self.failures * 450.0
        freshness_bonus = 80.0 if self.last_used and time.time() - self.last_used < 900 else 0.0
        return base_rank + latency_score + reliability_score - failure_penalty + freshness_bonus


class SmartController:
    """Adaptive server-selection intelligence.

    Combines provider metadata with locally observed latency/reliability and
    temporarily quarantines repeatedly failing endpoints.
    """

    def __init__(self):
        self.history: dict[str, ServerScore] = {}
        self.blocked: dict[str, float] = {}

    def update(self, host: str, latency_ms: float, success: bool) -> None:
        if not host:
            return
        item = self.history.setdefault(host, ServerScore(host))
        item.latency_ms = max(0.0, float(latency_ms))
        item.last_used = time.time()
        item.samples += 1
        if success:
            item.reliability = min(1.0, item.reliability * 0.8 + 0.2)
            item.failures = max(0, item.failures - 1)
            self.blocked.pop(host, None)
        else:
            item.reliability = max(0.0, item.reliability * 0.7)
            item.failures += 1
            # Short quarantine after a failed attempt; repeated failures get
            # progressively longer so the client does not hammer dead hosts.
            cooldown = min(900.0, 45.0 * (2 ** min(item.failures - 1, 4)))
            self.blocked[host] = time.time() + cooldown

    def rank(self, servers: list[dict]) -> list[dict]:
        now = time.time()
        ranked = []
        for server in servers:
            host = str(server.get("host") or "")
            if not host or self.blocked.get(host, 0.0) > now:
                continue
            history = self.history.get(host)
            base_rank = float(server.get("rank", 0.0) or 0.0)
            score = history.score(base_rank) if history else base_rank
            item = dict(server)
            item["smart_rank"] = score
            ranked.append(item)
        return sorted(
            ranked,
            key=lambda s: (float(s.get("smart_rank", -999999.0)), -float(s.get("ping", 9999.0))),
            reverse=True,
        )
