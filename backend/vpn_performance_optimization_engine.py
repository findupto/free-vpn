"""
VPN Performance Optimization Engine

Provides adaptive network tuning recommendations.
"""

from dataclasses import dataclass


@dataclass
class NetworkProfile:
    latency_ms: float
    packet_loss: float
    bandwidth_mbps: float


class VPNPerformanceOptimizer:
    def __init__(self):
        self.history = []

    def analyze(self, profile: NetworkProfile):
        recommendations = {
            "mtu": 1420,
            "transport": "udp",
            "congestion_control": "bbr",
            "compression": False,
        }

        if profile.packet_loss > 5:
            recommendations["transport"] = "tcp_fallback"
            recommendations["mtu"] = 1280

        if profile.latency_ms > 150:
            recommendations["mtu"] = 1280
            recommendations["congestion_control"] = "cubic"

        if profile.bandwidth_mbps < 5:
            recommendations["compression"] = True

        self.history.append({"profile": profile, "recommendations": recommendations})
        return recommendations

    def get_history(self):
        return self.history
