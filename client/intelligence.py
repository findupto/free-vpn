from __future__ import annotations

import socket
import time
from dataclasses import dataclass, field

@dataclass
class ServerScore:
    server: str
    latency_ms: float = 9999
    success_rate: float = 0
    score: float = 0
    history: dict = field(default_factory=dict)


def benchmark_server(host: str, port: int = 1194, timeout: float = 2.5) -> ServerScore:
    result = ServerScore(server=host)
    started = time.monotonic()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            result.latency_ms = (time.monotonic() - started) * 1000
            result.success_rate = 100
    except Exception:
        result.latency_ms = 9999
    result.score = max(0, 100 - min(result.latency_ms, 1000) / 10) * (result.success_rate / 100)
    return result


def choose_best_server(servers: list[tuple[str, int]]) -> ServerScore | None:
    results = [benchmark_server(host, port) for host, port in servers]
    return max(results, key=lambda x: x.score, default=None)
