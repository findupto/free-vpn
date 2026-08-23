"""
Zero Downtime VPN Failover Engine

Provides failover decision logic for switching unhealthy VPN nodes
without interrupting service workflows.
"""

import time


class ZeroDowntimeVPNFailoverEngine:
    def __init__(self):
        self.active_server = None
        self.failover_history = []

    def monitor_server(self, server, health):
        return health >= 70

    def select_backup(self, servers):
        healthy = [s for s in servers if s.get("health", 0) >= 70]
        healthy.sort(key=lambda x: (x.get("latency", 999), -x.get("health", 0)))
        return healthy[0] if healthy else None

    def failover(self, failed_server, servers):
        backup = self.select_backup(servers)
        event = {
            "time": time.time(),
            "failed": failed_server,
            "backup": backup,
            "status": "switched" if backup else "no_backup"
        }
        self.failover_history.append(event)
        self.active_server = backup
        return event

    def history(self):
        return self.failover_history
