"""
AI Adaptive VPN Protocol Engine
Automatically evaluates network conditions and recommends the best VPN transport mode.
"""

from datetime import datetime


class AIAdaptiveVPNProtocolEngine:
    def __init__(self):
        self.history = []

    def analyze_network(self, latency=0, packet_loss=0, blocked_udp=False):
        if blocked_udp:
            protocol = "TCP"
        elif packet_loss > 5:
            protocol = "TCP"
        elif latency > 200:
            protocol = "WireGuard"
        else:
            protocol = "OpenVPN-UDP"

        result = {
            "protocol": protocol,
            "latency": latency,
            "packet_loss": packet_loss,
            "time": datetime.utcnow().isoformat()
        }

        self.history.append(result)
        return result

    def get_history(self):
        return self.history
