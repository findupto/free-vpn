"""VPN server health monitoring agent foundation."""

import time


class HealthMonitor:
    def __init__(self):
        self.status = {}

    def update(self, server_id, metrics):
        self.status[server_id] = {
            "metrics": metrics,
            "updated": int(time.time())
        }

    def healthy_servers(self):
        return [k for k, v in self.status.items() if v.get("metrics")]
