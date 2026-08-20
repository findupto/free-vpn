"""
Findupto VPN security integration layer.

Coordinates security modules before and after VPN lifecycle events.
"""


class SecurityIntegration:
    def __init__(self, firewall=None, dns=None, ipv6=None):
        self.firewall = firewall
        self.dns = dns
        self.ipv6 = ipv6
        self.active = False

    def prepare_connection(self):
        """Enable protection before starting the VPN tunnel."""
        if self.firewall:
            self.firewall.enable()
        if self.dns:
            self.dns.enable()
        if self.ipv6:
            self.ipv6.enable()
        self.active = True
        return True

    def cleanup(self):
        """Restore protection state after disconnect."""
        if self.firewall:
            self.firewall.disable()
        if self.dns:
            self.dns.disable()
        if self.ipv6:
            self.ipv6.disable()
        self.active = False

    def status(self):
        return {
            "active": self.active,
            "firewall": self.firewall.status() if self.firewall else None,
            "dns": self.dns.status() if self.dns else None,
            "ipv6": self.ipv6.status() if self.ipv6 else None,
        }
