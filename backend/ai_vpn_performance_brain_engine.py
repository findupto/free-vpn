"""
AI VPN Performance Brain Engine

Continuous performance optimization layer for VPN operations.
"""

import time


class AIVPNPerformanceBrain:
    def __init__(self):
        self.metrics_history = []
        self.optimizations = []

    def collect_metrics(self, server, latency=0, packet_loss=0, bandwidth=0):
        record = {
            "server": server,
            "latency": latency,
            "packet_loss": packet_loss,
            "bandwidth": bandwidth,
            "timestamp": time.time(),
        }
        self.metrics_history.append(record)
        return record

    def optimize(self, metrics):
        score = 100
        score -= min(metrics.get("latency", 0) / 10, 40)
        score -= min(metrics.get("packet_loss", 0) * 5, 40)
        score += min(metrics.get("bandwidth", 0) / 100, 20)

        decision = {
            "server": metrics.get("server"),
            "performance_score": max(0, round(score, 2)),
            "action": "keep" if score > 60 else "replace",
            "timestamp": time.time(),
        }
        self.optimizations.append(decision)
        return decision

    def health_report(self):
        return {
            "samples": len(self.metrics_history),
            "optimizations": len(self.optimizations),
            "latest": self.optimizations[-1] if self.optimizations else None,
        }
