"""Deterministic server selection, failover and audit primitives."""
from __future__ import annotations
from dataclasses import dataclass, field
from time import time

@dataclass
class ServerRecord:
    id: str
    provider: str
    country: str
    score: float = 0.0
    available: bool = True
    failures: int = 0
    last_failure: float = 0.0

@dataclass
class SelectionEvent:
    server_id: str
    reason: str
    timestamp: float = field(default_factory=time)

class ServerSelectionPolicy:
    def __init__(self):
        self.servers: dict[str, ServerRecord] = {}
        self.audit: list[SelectionEvent] = []

    def upsert(self, server: ServerRecord) -> None:
        self.servers[server.id] = server

    def mark_failure(self, server_id: str) -> None:
        server = self.servers[server_id]
        server.failures += 1
        server.last_failure = time()
        if server.failures >= 3:
            server.available = False

    def mark_success(self, server_id: str) -> None:
        server = self.servers[server_id]
        server.failures = 0
        server.available = True

    def choose(self, country: str | None = None, provider: str | None = None) -> ServerRecord | None:
        candidates = [s for s in self.servers.values() if s.available]
        if country:
            scoped = [s for s in candidates if s.country.lower() == country.lower()]
            if scoped:
                candidates = scoped
        if provider:
            scoped = [s for s in candidates if s.provider.lower() == provider.lower()]
            if scoped:
                candidates = scoped
        if not candidates:
            return None
        selected = max(candidates, key=lambda s: (s.score, -s.failures, s.id))
        self.audit.append(SelectionEvent(selected.id, "best_available"))
        return selected

    def fallback(self, failed_id: str) -> ServerRecord | None:
        self.mark_failure(failed_id)
        return self.choose()

    def audit_log(self) -> list[SelectionEvent]:
        return list(self.audit)
