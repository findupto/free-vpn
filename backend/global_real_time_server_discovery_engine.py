"""
Global Real-Time Server Discovery Engine

Provides a foundation for discovering, validating, and ranking worldwide VPN nodes.
"""

import time


class GlobalServerDiscoveryEngine:
    def __init__(self):
        self.servers = {}
        self.history = []

    def discover_server(self, server):
        server_id = server.get("id")
        if not server_id:
            return False

        self.servers[server_id] = {
            **server,
            "discovered_at": time.time(),
            "status": "unknown"
        }

        self.history.append({
            "event": "server_discovered",
            "server": server_id,
            "time": time.time()
        })

        return True

    def validate_server(self, server_id, latency=999, reachable=False):
        if server_id not in self.servers:
            return False

        score = 0
        if reachable:
            score += 50
        if latency < 100:
            score += 50
        elif latency < 250:
            score += 25

        self.servers[server_id]["trust_score"] = score
        self.servers[server_id]["status"] = "online" if reachable else "offline"

        return self.servers[server_id]

    def best_servers(self):
        return sorted(
            self.servers.values(),
            key=lambda x: x.get("trust_score", 0),
            reverse=True
        )

    def get_history(self):
        return self.history
