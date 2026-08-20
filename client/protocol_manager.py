from __future__ import annotations

"""Protocol abstraction layer for Findupto VPN.

Keeps VPN protocol selection independent from the GUI and connection engine.
WireGuard is preferred when available, with OpenVPN fallback support.
"""

from dataclasses import dataclass
from enum import Enum


class VPNProtocol(str, Enum):
    WIREGUARD = "wireguard"
    OPENVPN = "openvpn"


@dataclass(frozen=True)
class ProtocolDecision:
    protocol: VPNProtocol
    reason: str


class ProtocolManager:
    def __init__(self, wireguard_available: bool = False):
        self.wireguard_available = wireguard_available

    def choose(self, prefer_fast: bool = True) -> ProtocolDecision:
        if prefer_fast and self.wireguard_available:
            return ProtocolDecision(VPNProtocol.WIREGUARD, "WireGuard available")
        return ProtocolDecision(VPNProtocol.OPENVPN, "OpenVPN compatibility fallback")

    def available(self) -> list[str]:
        protocols = [VPNProtocol.OPENVPN.value]
        if self.wireguard_available:
            protocols.insert(0, VPNProtocol.WIREGUARD.value)
        return protocols
