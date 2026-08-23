"""
Live Server Scanner Engine
Continuously evaluates VPN nodes and keeps healthy servers available.
"""

import time
from datetime import datetime


class LiveServerScannerEngine:
    def __init__(self):
        self.servers = {}
        self.scan_history = []

    def register_server(self, server_id, country, ip):
        self.servers[server_id] = {
            "country": country,
            "ip": ip,
            "status": "unknown",
            "latency": None,
            "last_scan": None,
        }

    def scan_server(self, server_id, latency=None, reachable=True):
        if server_id not in self.servers:
            return None

        server = self.servers[server_id]
        server["status"] = "online" if reachable else "offline"
        server["latency"] = latency
        server["last_scan"] = datetime.utcnow().isoformat()

        self.scan_history.append({
            "server": server_id,
            "status": server["status"],
            "time": time.time(),
        })

        return server

    def get_active_servers(self):
        return [s for s in self.servers.values() if s["status"] == "online"]

    def history(self):
        return self.scan_history
