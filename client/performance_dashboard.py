"""Next generation UI/performance dashboard helpers.

Designed for integration with the VPN client UI.
Provides live metrics, server scoring and connection quality state.
"""

from dataclasses import dataclass
from time import monotonic


@dataclass
class ConnectionMetrics:
    latency_ms: float = 9999
    jitter_ms: float = 0
    packet_loss: float = 0
    download_mbps: float = 0
    upload_mbps: float = 0
    uptime: float = 0

    def score(self):
        latency = max(0, 100 - self.latency_ms / 5)
        speed = min(100, self.download_mbps * 2)
        stability = max(0, 100 - self.packet_loss * 20 - self.jitter_ms)
        return round(latency * .35 + speed * .45 + stability * .20, 2)


class ServerRacer:
    """Ranks endpoints using real connection quality metrics."""

    def __init__(self):
        self.samples = {}
        self.started = monotonic()

    def update(self, server, metrics: ConnectionMetrics):
        self.samples[server] = metrics

    def fastest(self):
        if not self.samples:
            return None
        return max(self.samples, key=lambda x: self.samples[x].score())


class TunnelWarmPool:
    """Keeps ready connection candidates before user connects."""

    def __init__(self, size=5):
        self.size = size
        self.pool = []

    def add(self, endpoint):
        if endpoint not in self.pool:
            self.pool.append(endpoint)
        self.pool = self.pool[-self.size:]

    def get_ready(self):
        return list(self.pool)
