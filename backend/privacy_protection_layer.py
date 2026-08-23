"""Privacy protection controls for VPN sessions.

Provides kill-switch state management and DNS protection hooks.
"""

from dataclasses import dataclass, field
from time import time


@dataclass
class PrivacyState:
    vpn_connected: bool = False
    kill_switch_enabled: bool = True
    dns_protection_enabled: bool = True
    blocked_requests: int = 0
    last_change: float = field(default_factory=time)


class KillSwitch:
    def __init__(self):
        self.state = PrivacyState()

    def enable(self):
        self.state.kill_switch_enabled = True
        self.state.last_change = time()

    def disable(self):
        self.state.kill_switch_enabled = False
        self.state.last_change = time()

    def allow_network(self):
        if self.state.kill_switch_enabled:
            return self.state.vpn_connected
        return True

    def update_tunnel(self, connected: bool):
        self.state.vpn_connected = connected
        self.state.last_change = time()
        return self.allow_network()


class DNSLeakProtection:
    def __init__(self):
        self.enabled = True
        self.preferred_dns = []

    def configure(self, dns_servers):
        self.preferred_dns = list(dns_servers or [])
        self.enabled = True
        return self.preferred_dns

    def verify(self, dns_servers):
        if not self.enabled:
            return True
        return all(server in self.preferred_dns for server in dns_servers)


privacy_layer = {
    "kill_switch": KillSwitch(),
    "dns_protection": DNSLeakProtection(),
}
