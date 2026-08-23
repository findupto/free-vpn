"""
Automatic VPN Server Database Sync Engine
Keeps server inventory refreshed and synchronized.
"""

from datetime import datetime


class ServerDatabaseSyncEngine:
    def __init__(self):
        self.servers = {}
        self.history = []

    def sync_servers(self, discovered_servers):
        updated = 0
        for server in discovered_servers:
            key = server.get("ip")
            if key:
                self.servers[key] = {
                    **server,
                    "updated_at": datetime.utcnow().isoformat()
                }
                updated += 1

        self.history.append({
            "event": "sync",
            "servers_updated": updated,
            "time": datetime.utcnow().isoformat()
        })

        return updated

    def remove_expired_servers(self, active_ips):
        removed = []
        for ip in list(self.servers.keys()):
            if ip not in active_ips:
                removed.append(ip)
                del self.servers[ip]
        return removed

    def get_servers(self, country=None):
        if not country:
            return list(self.servers.values())
        return [s for s in self.servers.values() if s.get("country") == country]

    def debug_history(self):
        return self.history
