"""
Unified VPN security orchestration layer.

Connects protection modules together:
- Firewall protection
- DNS protection
- IPv6 protection
- Tunnel security state
"""


class VPNSecurityManager:
    def __init__(self, firewall=None, dns=None, ipv6=None):
        self.firewall = firewall
        self.dns = dns
        self.ipv6 = ipv6
        self.active = False

    def enable_protection(self):
        if self.firewall:
            self.firewall.enable()
        if self.dns:
            self.dns.enable()
        if self.ipv6:
            self.ipv6.enable()

        self.active = True
        return True

    def disable_protection(self):
        if self.firewall:
            self.firewall.disable()
        if self.dns:
            self.dns.disable()
        if self.ipv6:
            self.ipv6.disable()

        self.active = False
        return True

    def status(self):
        return {
            "protected": self.active,
            "firewall": bool(self.firewall),
            "dns": bool(self.dns),
            "ipv6": bool(self.ipv6),
        }
