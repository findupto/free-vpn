"""
Global VPN Control Center Dashboard Backend
Provides unified operational metrics for servers, users, health and incidents.
"""

from datetime import datetime


class VPNControlCenter:
    def __init__(self):
        self.servers = {}
        self.users = {}
        self.incidents = []

    def register_server(self, server_id, country, status="online"):
        self.servers[server_id] = {
            "country": country,
            "status": status,
            "updated": datetime.utcnow().isoformat()
        }

    def update_server_status(self, server_id, status):
        if server_id in self.servers:
            self.servers[server_id]["status"] = status
            self.servers[server_id]["updated"] = datetime.utcnow().isoformat()

    def add_user_session(self, user_id, server_id):
        self.users[user_id] = {
            "server": server_id,
            "connected": datetime.utcnow().isoformat()
        }

    def add_incident(self, message, severity="warning"):
        self.incidents.append({
            "message": message,
            "severity": severity,
            "time": datetime.utcnow().isoformat()
        })

    def get_dashboard(self):
        return {
            "servers": self.servers,
            "active_users": len(self.users),
            "incidents": self.incidents,
            "generated": datetime.utcnow().isoformat()
        }
