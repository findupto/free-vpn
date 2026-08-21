"""Adaptive VPN benchmark engine.
Ranks VPN profiles using throughput first, then latency, reliability and stability."""

import statistics
import time


class BenchmarkEngine:
    def __init__(self):
        self.history = {}

    def score(self, server, latency_ms, success=True, speed_mbps=0, packet_loss=0, jitter_ms=0):
        record = self.history.setdefault(server, {"samples": []})
        record["samples"].append({
            "latency": max(0.0, latency_ms),
            "success": bool(success),
            "speed": max(0.0, speed_mbps),
            "loss": max(0.0, packet_loss),
            "jitter": max(0.0, jitter_ms),
            "time": time.time(),
        })
        record["samples"] = record["samples"][-30:]

        samples = record["samples"]
        latency = statistics.mean(x["latency"] for x in samples)
        reliability = sum(1 for x in samples if x["success"]) / len(samples)
        speed = statistics.mean(x["speed"] for x in samples)
        loss = statistics.mean(x["loss"] for x in samples)
        jitter = statistics.mean(x["jitter"] for x in samples)

        if not success:
            return 0

        # Throughput is the primary objective. A 100 Mbps relay with 80 ms
        # latency is normally far better for downloads than a 10 Mbps relay
        # with 20 ms latency. Latency remains important, but cannot dominate.
        throughput_component = min(speed, 1000.0) * 0.60
        latency_component = max(0.0, 250.0 - latency) * 0.08
        reliability_component = reliability * 20.0
        loss_component = max(0.0, 10.0 - loss) * 1.0
        jitter_component = max(0.0, 50.0 - jitter) * 0.12
        return max(0.0, throughput_component + latency_component + reliability_component + loss_component + jitter_component)

    def usable(self, server):
        samples = self.history.get(server, {}).get("samples", [])
        if not samples:
            return False
        latest = samples[-1]
        return (
            latest["success"]
            and latest["latency"] <= 300
            and latest["speed"] >= 5
            and latest["loss"] <= 5
        )

    def best(self, servers):
        """Return the highest-throughput healthy endpoints first."""
        return sorted(
            servers,
            key=lambda x: (
                float(x.get("measured_speed_mbps", x.get("speed", 0)) or 0),
                -float(x.get("latency_ms", x.get("live_ping", 9999)) or 9999),
                float(x.get("score", 0) or 0),
            ),
            reverse=True,
        )

    def rank(self, servers):
        return self.best(servers)
