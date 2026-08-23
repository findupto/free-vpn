"""Premium VPN server quality scoring engine."""

from dataclasses import dataclass


@dataclass
class HealthMetrics:
    latency_ms: float = 999
    uptime: float = 0.0
    packet_loss: float = 100.0
    speed_mbps: float = 0.0
    active_users: int = 0


class ServerHealthScorer:
    def score(self, metrics: HealthMetrics) -> float:
        latency_score = max(0, 100 - min(metrics.latency_ms, 1000) / 10)
        uptime_score = max(0, min(metrics.uptime, 100))
        loss_score = max(0, 100 - min(metrics.packet_loss, 100) * 5)
        speed_score = min(metrics.speed_mbps * 5, 100)
        load_penalty = min(metrics.active_users, 100) * 0.2

        return max(
            0,
            round(
                (latency_score * 0.3)
                + (uptime_score * 0.3)
                + (loss_score * 0.2)
                + (speed_score * 0.2)
                - load_penalty,
                2,
            ),
        )

    def rank_servers(self, servers):
        ranked = []
        for server in servers:
            metrics = server.get("health", HealthMetrics())
            if isinstance(metrics, dict):
                metrics = HealthMetrics(**metrics)
            server["health_score"] = self.score(metrics)
            ranked.append(server)
        return sorted(ranked, key=lambda item: item["health_score"], reverse=True)


health_scorer = ServerHealthScorer()
