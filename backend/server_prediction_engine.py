"""Adaptive VPN server prediction engine.

Ranks servers using historical connection performance and current network
conditions to reduce connection time.
"""

from dataclasses import dataclass, field
from time import time


@dataclass
class ServerProfile:
    server_id: str
    country: str = ""
    score: float = 0.0
    attempts: int = 0
    successful_connections: int = 0
    average_latency: float = 9999
    updated_at: float = field(default_factory=time)


class ServerPredictionEngine:
    def __init__(self):
        self.history = {}

    def update_result(self, server_id, latency, success):
        profile = self.history.get(server_id) or ServerProfile(server_id=server_id)
        profile.attempts += 1
        if success:
            profile.successful_connections += 1
            profile.average_latency = (
                (profile.average_latency + latency) / 2
                if profile.average_latency < 9999
                else latency
            )

        reliability = profile.successful_connections / max(profile.attempts, 1)
        latency_score = max(0, 100 - min(profile.average_latency, 1000) / 10)
        profile.score = reliability * 70 + latency_score * 0.3
        profile.updated_at = time()
        self.history[server_id] = profile
        return profile

    def recommend(self, servers, limit=5):
        ranked = []
        for server in servers:
            profile = self.history.get(server.get("id"))
            ranked.append((profile.score if profile else 50, server))
        return [server for _, server in sorted(ranked, key=lambda x: x[0], reverse=True)[:limit]]


prediction_engine = ServerPredictionEngine()
