"""
Real-Time Speed & Latency Measurement Engine

Provides network testing foundation for VPN server selection.
"""

import time
from datetime import datetime


class SpeedLatencyEngine:
    def __init__(self):
        self.history = []

    def measure_server(self, server_id, latency_ms=0, download_mbps=0, upload_mbps=0, packet_loss=0):
        score = self.calculate_score(
            latency_ms,
            download_mbps,
            upload_mbps,
            packet_loss
        )

        result = {
            "server": server_id,
            "latency_ms": latency_ms,
            "download_mbps": download_mbps,
            "upload_mbps": upload_mbps,
            "packet_loss": packet_loss,
            "quality_score": score,
            "timestamp": datetime.utcnow().isoformat()
        }

        self.history.append(result)
        return result

    def calculate_score(self, latency, download, upload, loss):
        score = 100
        score -= min(latency / 5, 40)
        score += min(download / 10, 30)
        score += min(upload / 10, 20)
        score -= min(loss * 5, 30)
        return max(0, round(score, 2))

    def fastest_server(self, servers):
        if not servers:
            return None
        return max(servers, key=lambda x: x.get("quality_score", 0))

    def get_history(self):
        return self.history
