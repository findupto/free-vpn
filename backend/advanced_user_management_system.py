"""
Advanced VPN User Management System

Provides account, device, session and access-control management foundation.
"""

from datetime import datetime


class UserManager:
    def __init__(self):
        self.users = {}
        self.sessions = {}

    def create_user(self, user_id, plan="free"):
        self.users[user_id] = {
            "plan": plan,
            "devices": [],
            "created": datetime.utcnow().isoformat(),
            "active": True,
        }
        return self.users[user_id]

    def add_device(self, user_id, device_id):
        if user_id in self.users:
            self.users[user_id]["devices"].append(device_id)
            return True
        return False

    def create_session(self, user_id, server=None):
        session_id = f"{user_id}-{datetime.utcnow().timestamp()}"
        self.sessions[session_id] = {
            "user_id": user_id,
            "server": server,
            "created": datetime.utcnow().isoformat(),
            "active": True,
        }
        return session_id

    def revoke_session(self, session_id):
        if session_id in self.sessions:
            self.sessions[session_id]["active"] = False
            return True
        return False

    def get_user_status(self, user_id):
        return self.users.get(user_id)
