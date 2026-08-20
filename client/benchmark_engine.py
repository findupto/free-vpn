"""Fast VPN benchmark engine.
Ranks VPN profiles using latency, reliability, throughput and stability."""

import time
import statistics


class BenchmarkEngine:
    def __init__(self):
        self.history = {}

    def score(self, server, latency_ms, success=True, speed_mbps=0, packet_loss=0, jitter_ms=0):
        record = self.history.setdefault(server, {"samples": []})
        record["samples"].append({
            "latency": latency_ms,
            "success": success,
            "speed": speed_mbps,
            "loss": packet_loss,
            "jitter": jitter_ms,
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

        return max(0, (
            reliability * 35
            + min(speed, 500) * 0.35
            + max(0, 250 - latency) * 0.12
            + max(0, 10 - loss) * 2
            + max(0, 50 - jitter) * 0.2
        ))

    def usable(self, server):
        samples = self.history.get(server, {}).get("samples", [])
        if not samples:
            return False
        latest = samples[-1]
        return (
            latest["success"]
            and latest["latency"] <= 220
            and latest["speed"] >= 10
            and latest["loss"] <= 5
        )

    def rank(self, servers):
        return sorted(
            servers,
            key=lambda x: x.get("score", 0),
            reverse=True,
        )
