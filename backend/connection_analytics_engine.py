"""Premium VPN connection analytics.

Tracks session quality metrics and produces a connection health score.
"""

import time
from collections import deque


class ConnectionAnalytics:
    def __init__(self, history_size=100):
        self.sessions = deque(maxlen=history_size)

    def record(self, server, latency_ms=0, packet_loss=0, speed_mbps=0, uptime=1):
        score = self.calculate_score(
            latency_ms,
            packet_loss,
            speed_mbps,
            uptime,
        )
        item = {
            "server": server,
            "latency_ms": latency_ms,
            "packet_loss": packet_loss,
            "speed_mbps": speed_mbps,
            "uptime": uptime,
            "score": score,
            "timestamp": int(time.time()),
        }
        self.sessions.append(item)
        return item

    def calculate_score(self, latency, loss, speed, uptime):
        latency_score = max(0, 100 - min(latency, 1000) / 10)
        loss_score = max(0, 100 - loss * 10)
        speed_score = min(speed * 10, 100)
        uptime_score = max(0, min(uptime * 100, 100))
        return round(
            latency_score * 0.35
            + loss_score * 0.25
            + speed_score * 0.20
            + uptime_score * 0.20,
            2,
        )

    def best_sessions(self, limit=10):
        return sorted(
            list(self.sessions),
            key=lambda x: x["score"],
            reverse=True,
        )[:limit]


analytics_engine = ConnectionAnalytics()
