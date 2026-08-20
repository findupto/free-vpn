from __future__ import annotations

import socket

class SecurityGuard:
    def __init__(self):
        self.vpn_active = False
        self.killswitch = True

    def vpn_up(self):
        self.vpn_active = True

    def vpn_down(self):
        self.vpn_active = False

    def allow_network(self) -> bool:
        if self.killswitch and not self.vpn_active:
            return False
        return True

    def dns_safe(self, dns_servers: list[str]) -> bool:
        return bool(dns_servers)

    def ipv6_safe(self) -> bool:
        return True
