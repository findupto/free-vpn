"""Adaptive server selection layer for Findupto VPN.

Combines latency, stability and throughput signals into one score.
"""

from dataclasses import dataclass
from typing import Iterable


@dataclass
class ServerScore:
    server: dict
    score: float


def score_server(server: dict) -> float:
    ping = float(server.get("live_ping", server.get("ping", 9999)) or 9999)
    loss = float(server.get("packet_loss", 100) or 100)
    jitter = float(server.get("jitter", 999) or 999)
    speed = float(server.get("speed", 0) or 0)

    latency_score = max(0, 100 - ping / 5)
    loss_score = max(0, 100 - loss * 10)
    jitter_score = max(0, 100 - jitter / 2)
    speed_score = min(100, speed)

    return (
        latency_score * 0.30
        + speed_score * 0.40
        + loss_score * 0.20
        + jitter_score * 0.10
    )


def select_fastest(servers: Iterable[dict], limit: int = 10) -> list[dict]:
    ranked = [ServerScore(s, score_server(s)) for s in servers]
    ranked.sort(key=lambda item: item.score, reverse=True)
    return [item.server for item in ranked[:limit]]


def should_switch(current: dict, candidate: dict) -> bool:
    return score_server(candidate) > score_server(current) * 1.15
