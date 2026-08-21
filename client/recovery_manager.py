"""Adaptive recovery logic with failure windows and temporary server quarantine."""

from __future__ import annotations

import time
from collections import defaultdict, deque


class RecoveryManager:
    def __init__(self, max_failures=5, window_seconds=600, quarantine_seconds=300):
        self.max_failures = max(1, int(max_failures))
        self.window_seconds = max(1, int(window_seconds))
        self.quarantine_seconds = max(1, int(quarantine_seconds))
        self.failures = defaultdict(deque)
        self.quarantined_until: dict[str, float] = {}

    def record_failure(self, server, reason):
        now = time.time()
        history = self.failures[server]
        history.append((now, str(reason)))
        self._prune(server, now)
        if len(history) >= self.max_failures:
            self.quarantined_until[server] = now + self.quarantine_seconds

    def _prune(self, server, now=None):
        now = time.time() if now is None else now
        history = self.failures.get(server)
        if history is None:
            return
        cutoff = now - self.window_seconds
        while history and history[0][0] < cutoff:
            history.popleft()

    def strategy(self, reason):
        value = str(reason).lower()
        if "timeout" in value or "unreachable" in value:
            return "switch_transport"
        if "auth" in value or "credential" in value:
            return "refresh_credentials"
        if "push" in value or "route" in value:
            return "retry_profile"
        return "next_best_server"

    def should_block(self, server):
        now = time.time()
        until = self.quarantined_until.get(server, 0)
        if until > now:
            return True
        self.quarantined_until.pop(server, None)
        self._prune(server, now)
        return len(self.failures.get(server, ())) >= self.max_failures
