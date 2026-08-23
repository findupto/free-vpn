"""
Premium Monitoring & Alert System
Tracks VPN infrastructure health and generates recovery actions.
"""

import time


class PremiumMonitoringAlertSystem:
    def __init__(self):
        self.events = []
        self.servers = {}

    def register_server(self, server_id, metadata=None):
        self.servers[server_id] = {
            "metadata": metadata or {},
            "status": "unknown",
            "last_check": time.time(),
        }

    def record_health(self, server_id, latency=0, uptime=True, online=True):
        if server_id not in self.servers:
            self.register_server(server_id)

        status = "healthy"
        if not online:
            status = "offline"
        elif latency > 300 or not uptime:
            status = "degraded"

        self.servers[server_id].update({
            "status": status,
            "latency": latency,
            "last_check": time.time(),
        })

        if status != "healthy":
            self.events.append({
                "server": server_id,
                "event": status,
                "time": time.time(),
            })

        return status

    def get_alerts(self):
        return list(self.events)

    def get_status(self):
        return self.servers
