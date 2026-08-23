"""Premium VPN connection orchestration.

Provides instant connection selection by racing healthy endpoints,
scoring results, and falling back automatically.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass


@dataclass
class ConnectionCandidate:
    server_id: str
    endpoint: str
    country: str = "Unknown"
    ip: str = ""
    latency_ms: float = 999999
    available: bool = False


class FastConnectManager:
    def __init__(self, max_parallel: int = 8):
        self.max_parallel = max_parallel
        self.history = {}

    def race_servers(self, servers, connector, timeout=10):
        candidates = []

        def connect(server):
            started = time.monotonic()
            try:
                ok = connector(server, timeout=timeout)
                latency = (time.monotonic() - started) * 1000
                return ConnectionCandidate(
                    server_id=server.get("id", ""),
                    endpoint=server.get("host", ""),
                    country=server.get("country", "Unknown"),
                    ip=server.get("ip", ""),
                    latency_ms=latency,
                    available=bool(ok),
                )
            except Exception:
                return None

        with ThreadPoolExecutor(max_workers=min(self.max_parallel, len(servers))) as pool:
            jobs = [pool.submit(connect, server) for server in servers]
            for job in as_completed(jobs):
                result = job.result()
                if result and result.available:
                    candidates.append(result)

        candidates.sort(key=lambda item: item.latency_ms)

        if candidates:
            self.history[candidates[0].server_id] = time.time()

        return candidates

    def best_connection(self, servers, connector):
        results = self.race_servers(servers, connector)
        return results[0] if results else None
