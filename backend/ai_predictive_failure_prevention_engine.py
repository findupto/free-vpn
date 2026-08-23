"""
AI Predictive Failure Prevention Engine

Predicts VPN reliability issues before they impact users.
"""

import time
from collections import defaultdict


class AIPredictiveFailurePreventionEngine:
    def __init__(self):
        self.server_metrics = defaultdict(list)
        self.predictions = []

    def record_metric(self, server, latency, packet_loss, failures):
        self.server_metrics[server].append({
            "time": time.time(),
            "latency": latency,
            "packet_loss": packet_loss,
            "failures": failures,
        })

    def predict_server_risk(self, server):
        history = self.server_metrics.get(server, [])

        if not history:
            return {
                "server": server,
                "risk": "unknown",
                "action": "collect_more_data",
            }

        latest = history[-1]
        risk = 0

        if latest["latency"] > 250:
            risk += 30
        if latest["packet_loss"] > 5:
            risk += 35
        if latest["failures"] > 2:
            risk += 35

        action = "keep_server"
        if risk >= 70:
            action = "move_users_and_scan_backup"
        elif risk >= 40:
            action = "monitor_and_reduce_priority"

        result = {
            "server": server,
            "risk_score": risk,
            "action": action,
            "timestamp": time.time(),
        }

        self.predictions.append(result)
        return result

    def get_history(self):
        return self.predictions
