class ConnectionOptimizer:
    def __init__(self):
        self.failures = {}
        self.last_good_server = None

    def record_failure(self, server):
        self.failures[server] = self.failures.get(server, 0) + 1

    def is_bad(self, server):
        return self.failures.get(server, 0) >= 3

    def choose_backup(self, servers):
        for server in servers:
            if not self.is_bad(server):
                self.last_good_server = server
                return server
        return None
