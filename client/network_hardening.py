"""Network hardening utilities for Findupto VPN.

Adds safe diagnostics and policy helpers for production networking flows.
"""

from dataclasses import dataclass, field
import socket
import time


@dataclass
class NetworkState:
    interface: str | None = None
    ipv4: str | None = None
    ipv6_available: bool = False
    captive_portal_detected: bool = False
    mtu: int | None = None
    updated: int = field(default_factory=lambda: int(time.time()))


class NetworkDiagnostics:
    def inspect(self, hostname="example.com"):
        state = NetworkState()
        try:
            addresses = socket.getaddrinfo(hostname, None)
            state.ipv6_available = any(item[0] == socket.AF_INET6 for item in addresses)
            for item in addresses:
                if item[0] == socket.AF_INET:
                    state.ipv4 = item[4][0]
                    break
        except OSError:
            pass
        state.updated = int(time.time())
        return state


class RoutingPolicy:
    def __init__(self):
        self.rules = []

    def add_split_route(self, destination):
        self.rules.append({"destination": destination, "mode": "split"})
        return self.rules

    def clear(self):
        self.rules.clear()


class KillSwitchState:
    def __init__(self):
        self.enabled = False
        self.tunnel_required = True

    def enable(self):
        self.enabled = True

    def disable(self):
        self.enabled = False

    def allow_network(self, tunnel_active):
        return not self.enabled or tunnel_active
