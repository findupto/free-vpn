"""
VPN Server Benchmark Engine

Measures and scores VPN servers using latency,
reliability and future bandwidth metrics.
"""

import time


class ServerBenchmark:
    def __init__(self):
        self.results = {}

    def measure_latency(self, server_id, ping_function=None):
        start = time.time()
        try:
            if ping_function:
                ping_function(server_id)
            latency = (time.time() - start) * 1000
        except Exception:
            latency = None

        self.results.setdefault(server_id, {})["latency_ms"] = latency
        return latency

    def update_score(self, server_id, reliability=1.0, bandwidth=0):
        data = self.results.setdefault(server_id, {})
        data["reliability"] = reliability
        data["bandwidth"] = bandwidth

        latency = data.get("latency_ms") or 9999

        score = (
            max(0, 100 - latency) * 0.4
            + bandwidth * 0.3
            + reliability * 100 * 0.3
        )

        data["score"] = round(score, 2)
        return data["score"]

    def best_server(self):
        if not self.results:
            return None
        return max(
            self.results,
            key=lambda item: self.results[item].get("score", 0)
        )
