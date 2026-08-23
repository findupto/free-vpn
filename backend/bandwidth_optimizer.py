"""Adaptive bandwidth optimization for VPN connections.

Provides dynamic MTU selection, congestion hints, and transport profiles
for improving performance across different network conditions.
"""

from dataclasses import dataclass


@dataclass
class NetworkProfile:
    latency_ms: float = 50
    packet_loss: float = 0.0
    bandwidth_mbps: float = 50


class AdaptiveMTU:
    def calculate(self, profile: NetworkProfile):
        if profile.packet_loss > 5:
            return 1280
        if profile.latency_ms > 150:
            return 1360
        return 1420


class TransportOptimizer:
    def choose_protocol_mode(self, profile: NetworkProfile):
        if profile.packet_loss > 3:
            return "loss_resistant"
        if profile.bandwidth_mbps > 100:
            return "high_throughput"
        return "balanced"


class BandwidthOptimizer:
    def __init__(self):
        self.profile = NetworkProfile()
        self.mtu = AdaptiveMTU()
        self.transport = TransportOptimizer()

    def update(self, latency_ms, packet_loss, bandwidth_mbps):
        self.profile = NetworkProfile(
            latency_ms=float(latency_ms),
            packet_loss=float(packet_loss),
            bandwidth_mbps=float(bandwidth_mbps),
        )
        return {
            "mtu": self.mtu.calculate(self.profile),
            "mode": self.transport.choose_protocol_mode(self.profile),
        }


bandwidth_optimizer = BandwidthOptimizer()
