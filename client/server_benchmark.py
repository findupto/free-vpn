"""VPN server benchmark engine with latency, jitter, loss, and bandwidth scoring."""

from __future__ import annotations

import statistics
import time


class ServerBenchmark:
    def __init__(self):
        self.results: dict[str, dict] = {}

    def measure_latency(self, server_id, ping_function=None, samples: int = 3):
        samples = max(1, min(int(samples), 10))
        measurements = []
        for _ in range(samples):
            start = time.monotonic()
            try:
                if ping_function:
                    ping_function(server_id)
                measurements.append((time.monotonic() - start) * 1000)
            except Exception:
                continue
        data = self.results.setdefault(server_id, {})
        data["latency_samples_ms"] = measurements
        data["latency_ms"] = round(statistics.median(measurements), 2) if measurements else None
        data["jitter_ms"] = round(statistics.pstdev(measurements), 2) if len(measurements) > 1 else 0.0
        data["packet_loss"] = round(1 - len(measurements) / samples, 4)
        return data["latency_ms"]

    def update_score(self, server_id, reliability=1.0, bandwidth=0):
        data = self.results.setdefault(server_id, {})
        data["reliability"] = max(0.0, min(float(reliability), 1.0))
        data["bandwidth"] = max(0.0, float(bandwidth))
        latency = data.get("latency_ms")
        latency_score = max(0.0, 100.0 - min(latency or 5000.0, 5000.0) / 50.0)
        jitter_score = max(0.0, 100.0 - min(float(data.get("jitter_ms") or 0), 1000.0) / 10.0)
        loss_score = max(0.0, 100.0 * (1.0 - float(data.get("packet_loss") or 0)))
        bandwidth_score = min(data["bandwidth"], 100.0)
        score = (
            latency_score * 0.30
            + jitter_score * 0.10
            + loss_score * 0.20
            + bandwidth_score * 0.15
            + data["reliability"] * 100 * 0.25
        )
        data["score"] = round(score, 2)
        return data["score"]

    def best_server(self):
        if not self.results:
            return None
        return max(self.results, key=lambda item: self.results[item].get("score", 0))
