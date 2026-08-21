"""Higher-level server selection orchestration built on existing policies."""
from __future__ import annotations
from dataclasses import dataclass
from time import time

@dataclass(frozen=True)
class Candidate:
    id: str
    provider: str
    country: str
    transport: str = "udp"
    score: float = 0.0
    healthy: bool = True
    fresh: bool = True

class SelectionEngine:
    def __init__(self, max_failures: int = 3):
        self.max_failures = max_failures
        self.failures: dict[str, int] = {}
        self.quarantine_until: dict[str, float] = {}
        self.audit: list[dict] = []

    def mark_failure(self, server_id: str, cooldown: float = 300.0) -> None:
        count = self.failures.get(server_id, 0) + 1
        self.failures[server_id] = count
        if count >= self.max_failures:
            self.quarantine_until[server_id] = time() + cooldown

    def mark_success(self, server_id: str) -> None:
        self.failures.pop(server_id, None)
        self.quarantine_until.pop(server_id, None)

    def eligible(self, item: Candidate, now: float | None = None) -> bool:
        now = time() if now is None else now
        return item.healthy and item.fresh and self.quarantine_until.get(item.id, 0) <= now

    def choose(self, candidates: list[Candidate], country: str | None = None, provider: str | None = None, transport: str | None = None) -> Candidate | None:
        pool = [c for c in candidates if self.eligible(c)]
        if country:
            scoped = [c for c in pool if c.country.lower() == country.lower()]
            if scoped: pool = scoped
        if provider:
            scoped = [c for c in pool if c.provider.lower() == provider.lower()]
            if scoped: pool = scoped
        if transport:
            scoped = [c for c in pool if c.transport.lower() == transport.lower()]
            if scoped: pool = scoped
        if not pool: return None
        chosen = max(pool, key=lambda c: (c.score, -self.failures.get(c.id, 0), c.id))
        self.audit.append({"server": chosen.id, "reason": "eligible_best", "at": time()})
        return chosen

    def deduplicate(self, candidates: list[Candidate]) -> list[Candidate]:
        seen: set[tuple[str, str, str]] = set(); result = []
        for item in sorted(candidates, key=lambda c: c.score, reverse=True):
            key = (item.provider.lower(), item.country.lower(), item.transport.lower())
            if key not in seen:
                seen.add(key); result.append(item)
        return result

    def diversity_score(self, candidates: list[Candidate]) -> float:
        if not candidates: return 0.0
        providers = len({c.provider for c in candidates}); countries = len({c.country for c in candidates})
        return min(1.0, (providers + countries) / (2 * len(candidates)))
