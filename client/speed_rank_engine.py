from __future__ import annotations

"""Real-time VPN speed ranking helpers.

Ranks servers by actual connection quality instead of catalog data only.
"""

import socket
import time
from concurrent.futures import ThreadPoolExecutor, as_completed


MIN_SPEED_SCORE = 40
MAX_LATENCY_MS = 250


def tcp_latency(host: str, port: int = 443, timeout: float = 2.5):
    start = time.monotonic()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return round((time.monotonic() - start) * 1000, 1)
    except Exception:
        return None


def score_server(server):
    host = server.get("host") or server.get("hostname")
    latency = tcp_latency(host) if host else None
    if latency is None:
        return {**server, "available": False, "score": 0}

    score = max(0, 100 - latency / 3)
    return {
        **server,
        "latency_ms": latency,
        "available": latency <= MAX_LATENCY_MS,
        "score": round(score, 1),
    }


def build_fast_pool(servers, workers=32, limit=20):
    ranked = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        jobs = [pool.submit(score_server, s) for s in servers]
        for job in as_completed(jobs):
            result = job.result()
            if result.get("available") and result.get("score", 0) >= MIN_SPEED_SCORE:
                ranked.append(result)

    return sorted(
        ranked,
        key=lambda x: (-x.get("score", 0), x.get("latency_ms", 9999))
    )[:limit]
