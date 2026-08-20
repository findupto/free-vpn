class ConnectionOptimizer:
    def __init__(self):
        self.failures = {}
        self.performance = {}
        self.cooldowns = {}
        self.last_good_server = None

    def record_failure(self, server):
        self.failures[server] = self.failures.get(server, 0) + 1

    def record_performance(self, server, score):
        self.performance[server] = score
        self.failures[server] = 0

    def penalize_slow(self, server):
        self.performance[server] = min(
            self.performance.get(server, 100),
            20,
        )

    def is_bad(self, server):
        return self.failures.get(server, 0) >= 3

    def choose_backup(self, servers):
        candidates = [
            s for s in servers
            if not self.is_bad(s)
        ]
        if not candidates:
            return None

        candidates.sort(
            key=lambda s: self.performance.get(s, 0),
            reverse=True,
        )

        self.last_good_server = candidates[0]
        return candidates[0]
