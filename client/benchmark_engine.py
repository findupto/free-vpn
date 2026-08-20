"""Fast VPN benchmark engine.
Ranks VPN profiles using latency, reliability, throughput and stability."""

import time
import statistics


class BenchmarkEngine:
    def __init__(self):
        self.history = {}

    def score(self, server, latency_ms, success=True, speed_mbps=0, packet_loss=0):
        old = self.history.setdefault(server, {"samples": []})
        old["samples"].append({
            "latency": latency_ms,
            "success": success,
            "speed": speed_mbps,
            "loss": packet_loss,
            "time": time.time(),
        })
        old["samples"] = old["samples"][-20:]

        samples = old["samples"]
        latency = statistics.mean(x["latency"] for x in samples)
        reliability = sum(1 for x in samples if x["success"]) / len(samples)
        speed = statistics.mean(x["speed"] for x in samples)
        loss = statistics.mean(x["loss"] for x in samples)

        if not success:
            return 0

        return max(0, (
            reliability * 35
            + min(speed, 200) * 0.3
            + max(0, 200 - latency) * 0.15
            + max(0, 10 - loss) * 2
        ))

    def usable(self, server):
        samples = self.history.get(server, {}).get("samples", [])
        if not samples:
            return False
        latest = samples[-1]
        return latest["success"] and latest["latency"] < 250 and latest["speed"] >= 5

    def rank(self, servers):
        return sorted(servers, key=lambda x: x.get("score", 0), reverse=True)
