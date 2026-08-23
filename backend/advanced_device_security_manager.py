"""
Advanced Device Security Manager
Provides device trust, fingerprint tracking and session protection foundation.
"""

import hashlib
import time


class DeviceSecurityManager:
    def __init__(self):
        self.devices = {}
        self.security_events = []

    def create_fingerprint(self, device_data: str) -> str:
        return hashlib.sha256(device_data.encode()).hexdigest()

    def register_device(self, user_id: str, device_data: str):
        fingerprint = self.create_fingerprint(device_data)
        self.devices[fingerprint] = {
            "user_id": user_id,
            "trusted": True,
            "created": time.time(),
            "last_seen": time.time(),
        }
        return fingerprint

    def verify_device(self, fingerprint: str):
        device = self.devices.get(fingerprint)
        if not device:
            return False
        device["last_seen"] = time.time()
        return device["trusted"]

    def revoke_device(self, fingerprint: str):
        if fingerprint in self.devices:
            self.devices[fingerprint]["trusted"] = False
            return True
        return False

    def record_security_event(self, event: dict):
        event["timestamp"] = time.time()
        self.security_events.append(event)
