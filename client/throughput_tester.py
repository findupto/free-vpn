from __future__ import annotations

import socket
import time
from dataclasses import dataclass


@dataclass
class NetworkQuality:
    latency_ms: float = 9999.0
    jitter_ms: float = 0.0
    packet_loss: float = 0.0
    score: float = 0.0


def quality_score(latency: float, jitter: float, loss: float, speed_mbps: float) -> float:
    latency_score = max(0, 100 - latency / 3)
    jitter_score = max(0, 100 - jitter * 5)
    loss_score = max(0, 100 - loss * 10)
    speed_score = min(100, speed_mbps * 5)
    return round(latency_score * 0.3 + speed_score * 0.4 + loss_score * 0.2 + jitter_score * 0.1, 2)


def probe_latency(host: str, port: int = 443, attempts: int = 5, timeout: float = 1.0) -> NetworkQuality:
    samples = []
    failures = 0
    for _ in range(attempts):
        started = time.monotonic()
        try:
            with socket.create_connection((host, port), timeout=timeout):
                samples.append((time.monotonic() - started) * 1000)
        except OSError:
            failures += 1

    if not samples:
        return NetworkQuality(packet_loss=100.0)

    average = sum(samples) / len(samples)
    jitter = max(samples) - min(samples) if len(samples) > 1 else 0
    loss = (failures / attempts) * 100

    return NetworkQuality(
        latency_ms=round(average, 2),
        jitter_ms=round(jitter, 2),
        packet_loss=round(loss, 2),
    )
