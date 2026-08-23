"""Smart VPN protocol selection engine.

Chooses transport strategy based on network conditions.
"""

from dataclasses import dataclass


@dataclass
class NetworkProfile:
    latency_ms: float = 0
    packet_loss: float = 0
    bandwidth_mbps: float = 0
    restricted_network: bool = False


class SmartProtocolSwitcher:
    def select(self, profile: NetworkProfile):
        if profile.restricted_network:
            return "tcp_fallback"

        if profile.packet_loss > 5:
            return "udp_reliable"

        if profile.latency_ms < 80 and profile.bandwidth_mbps > 50:
            return "wireguard_fast"

        if profile.latency_ms > 180:
            return "optimized_udp"

        return "balanced"

    def rank_protocols(self, profile: NetworkProfile):
        selected = self.select(profile)
        return [selected, "wireguard_fast", "optimized_udp", "tcp_fallback"]


protocol_switcher = SmartProtocolSwitcher()
