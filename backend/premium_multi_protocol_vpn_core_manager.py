"""
Premium Multi Protocol VPN Core Manager

Provides protocol orchestration framework for VPN connections.
Supports protocol health scoring, automatic fallback and selection logic.
"""

from datetime import datetime


class ProtocolManager:
    def __init__(self):
        self.protocols = {
            "wireguard": {"priority": 1, "health": 100},
            "openvpn": {"priority": 2, "health": 100},
            "ikev2": {"priority": 3, "health": 100},
            "tcp_fallback": {"priority": 4, "health": 100},
        }
        self.history = []

    def score_protocols(self, network):
        latency = network.get("latency", 0)
        loss = network.get("packet_loss", 0)

        for name, data in self.protocols.items():
            score = 100
            if latency > 150:
                score -= 15
            if loss > 5:
                score -= 20
            data["health"] = max(0, score)

        return sorted(self.protocols.items(), key=lambda x: (-x[1]["health"], x[1]["priority"]))

    def select_protocol(self, network):
        ranked = self.score_protocols(network)
        selected = ranked[0][0]
        self.history.append({
            "time": datetime.utcnow().isoformat(),
            "selected": selected,
            "network": network,
        })
        return selected

    def get_history(self):
        return self.history
