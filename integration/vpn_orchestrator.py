"""Unified production VPN lifecycle orchestrator.

Connects runtime components into one controlled lifecycle.
"""

class VPNOrchestrator:
    def __init__(self, wireguard, firewall, dns_guard, security):
        self.wireguard = wireguard
        self.firewall = firewall
        self.dns_guard = dns_guard
        self.security = security
        self.connected = False

    def connect(self, profile):
        self.security.enable()
        self.firewall.enable()
        self.dns_guard.enable()
        self.wireguard.connect(profile)
        self.connected = True
        return True

    def disconnect(self):
        self.wireguard.disconnect()
        self.dns_guard.disable()
        self.firewall.disable()
        self.security.disable()
        self.connected = False
        return True

    def status(self):
        return {"connected": self.connected}
