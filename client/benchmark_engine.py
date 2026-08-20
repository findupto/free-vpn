"""Smart VPN benchmark engine.
Ranks VPN profiles using latency, reliability and historical performance."""

import time
import statistics


class BenchmarkEngine:
    def __init__(self):
        self.history = {}

    def score(self, server, latency_ms, success=True, speed_mbps=0):
        old = self.history.get(server, {"samples": []})
        old["samples"].append({
            "latency": latency_ms,
            "success": success,
            "speed": speed_mbps,
            "time": time.time(),
        })
        self.history[server] = old

        samples = old["samples"][-20:]
        latency = statistics.mean(x["latency"] for x in samples)
        reliability = sum(x["success"] for x in samples) / len(samples)
        speed = statistics.mean(x["speed"] for x in samples)

        return max(0, (reliability * 50) + min(speed, 100) * 0.3 + max(0, 50-latency) * 0.4)

    def rank(self, servers):
        return sorted(servers, key=lambda x: x.get("score", 0), reverse=True)
