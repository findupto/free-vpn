"""Automatic VPN failover controller.

Keeps sessions resilient by monitoring tunnel health and selecting
backup endpoints when the current server becomes unstable.
"""

import time


class AutoFailoverManager:
    def __init__(self, health_checker=None, connector=None):
        self.health_checker = health_checker
        self.connector = connector
        self.current_server = None
        self.last_switch = 0
        self.switch_cooldown = 10

    def attach(self, server):
        self.current_server = server
        self.last_switch = time.time()

    def is_healthy(self, server):
        if not self.health_checker:
            return True
        try:
            return bool(self.health_checker(server))
        except Exception:
            return False

    def failover(self, candidates):
        now = time.time()
        if now - self.last_switch < self.switch_cooldown:
            return None

        for server in candidates:
            if server == self.current_server:
                continue
            if not self.is_healthy(server):
                continue

            try:
                if self.connector:
                    self.connector(server)
                self.current_server = server
                self.last_switch = now
                return server
            except Exception:
                continue

        return None


failover_manager = AutoFailoverManager()
