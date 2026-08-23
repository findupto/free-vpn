"""Real-time VPN server speed measurement layer."""

from dataclasses import dataclass
import time


@dataclass
class SpeedResult:
    server: str
    download_mbps: float
    upload_mbps: float
    latency_ms: float
    score: float


class SpeedTestEngine:
    def __init__(self):
        self.history = {}

    def measure(self, server, probe=None):
        start = time.monotonic()

        try:
            if probe:
                result = probe(server)
                download = float(result.get("download", 0))
                upload = float(result.get("upload", 0))
            else:
                download = 0.0
                upload = 0.0

            latency = (time.monotonic() - start) * 1000
            score = self.calculate_score(download, upload, latency)

            data = SpeedResult(
                server,
                download,
                upload,
                latency,
                score,
            )

            self.history[server] = data
            return data

        except Exception:
            return SpeedResult(server, 0, 0, 9999, 0)

    def calculate_score(self, download, upload, latency):
        latency_score = max(0, 100 - latency / 10)
        speed_score = min(100, (download * 2) + upload)
        return round((latency_score * 0.4) + (speed_score * 0.6), 2)

    def rank_servers(self):
        return sorted(
            self.history.values(),
            key=lambda item: item.score,
            reverse=True,
        )


speed_engine = SpeedTestEngine()
