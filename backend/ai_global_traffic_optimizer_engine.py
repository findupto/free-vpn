"""
AI Global Traffic Optimizer Engine

Optimizes VPN traffic distribution using health, latency,
load and performance signals.
"""

from datetime import datetime


class AIGlobalTrafficOptimizerEngine:
    def __init__(self):
        self.server_metrics = {}
        self.optimization_history = []

    def update_server_metrics(self, server_id, latency=0, load=0, packet_loss=0):
        self.server_metrics[server_id] = {
            "latency": latency,
            "load": load,
            "packet_loss": packet_loss,
            "updated": datetime.utcnow().isoformat(),
        }

    def calculate_score(self, server_id):
        metrics = self.server_metrics.get(server_id, {})
        latency = metrics.get("latency", 999)
        load = metrics.get("load", 100)
        packet_loss = metrics.get("packet_loss", 100)

        return max(0, 100 - (latency * 0.2) - (load * 0.5) - (packet_loss * 2))

    def choose_best_server(self):
        if not self.server_metrics:
            return None

        best = max(self.server_metrics, key=self.calculate_score)
        self.optimization_history.append({
            "selected": best,
            "score": self.calculate_score(best),
            "time": datetime.utcnow().isoformat(),
        })
        return best

    def get_history(self):
        return self.optimization_history
