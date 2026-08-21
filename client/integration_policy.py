"""Integration-state primitives for VPN networking subsystems."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum

class NetworkState(str, Enum): OFFLINE="offline"; ONLINE="online"; CAPTIVE="captive"; VPN="vpn"; RECOVERING="recovering"
@dataclass
class IntegrationState:
    network: NetworkState = NetworkState.OFFLINE
    firewall_ready: bool = False
    routes_ready: bool = False
    dns_ready: bool = False
    vpn_ready: bool = False
class IntegrationCoordinator:
    def __init__(self): self.state=IntegrationState()
    def ready(self)->bool: return self.state.firewall_ready and self.state.routes_ready and self.state.dns_ready and self.state.vpn_ready
    def reset(self)->None: self.state=IntegrationState()
