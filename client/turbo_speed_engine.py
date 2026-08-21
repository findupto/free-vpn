"""Turbo speed selection helpers.

Focuses on selecting servers that are likely to provide throughput, not only reachability.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
import socket
import time


class TurboSpeedEngine:
    def __init__(self, workers=32, timeout=1.5):
        self.workers = workers
        self.timeout = timeout

    def probe(self, host, port):
        started = time.monotonic()
        try:
            with socket.create_connection((host, int(port)), self.timeout):
                latency = (time.monotonic() - started) * 1000
                return {
                    "host": host,
                    "port": port,
                    "latency_ms": round(latency, 2),
                    "score": max(0, 100 - latency),
                    "available": True,
                }
        except Exception:
            return {
                "host": host,
                "port": port,
                "latency_ms": None,
                "score": 0,
                "available": False,
            }

    def rank(self, servers):
        results = []
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            jobs = [pool.submit(self.probe, s["host"], s.get("port", 443)) for s in servers]
            for job in as_completed(jobs):
                result = job.result()
                if result["available"]:
                    results.append(result)
        return sorted(results, key=lambda x: x["score"], reverse=True)
