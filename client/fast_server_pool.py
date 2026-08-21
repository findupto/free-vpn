"""Fast-connect server pool helpers for the desktop dashboard."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable

@dataclass(frozen=True)
class Endpoint:
    host: str
    port: int | None = None

@dataclass
class FastServer:
    data: dict
    endpoints: list[Endpoint]
    live_ping: float = 9999.0
    available: bool = False

    @property
    def label(self) -> str:
        return str(self.data.get("city") or self.data.get("country") or self.data.get("host") or "Server")


def endpoints(server: dict) -> list[Endpoint]:
    values = []
    for key in ("ips", "ip_list", "addresses", "endpoints"):
        raw = server.get(key)
        if isinstance(raw, (list, tuple, set)):
            values.extend(raw)
    for key in ("ip", "host", "address"):
        raw = server.get(key)
        if raw:
            values.append(raw)
    seen: set[str] = set(); result: list[Endpoint] = []
    for value in values:
        if isinstance(value, dict):
            host = str(value.get("ip") or value.get("host") or value.get("address") or "").strip()
            port = value.get("port")
        else:
            host, port = str(value).strip(), None
        if not host or host in seen:
            continue
        seen.add(host)
        try: port = int(port) if port else None
        except (TypeError, ValueError): port = None
        result.append(Endpoint(host, port))
    return result


def expand_servers(items: Iterable[dict]) -> list[FastServer]:
    return [FastServer(dict(item), endpoints(dict(item))) for item in items]


def throughput_score(server: dict, max_ping: float = 250.0) -> float:
    """Score a reachable endpoint for real-world throughput, not just ping.

    Free VPN catalogs expose an advertised speed. A very low-latency relay can
    still be dramatically slower than a slightly farther relay, so throughput
    is deliberately weighted much more heavily than latency.
    """
    ping = max(1.0, float(server.get("live_ping", server.get("ping", 9999)) or 9999))
    speed = max(0.0, float(server.get("speed", 0) or 0))
    rank_hint = max(0.0, float(server.get("rank", 0) or 0))
    if ping > max_ping:
        return -1.0
    latency_factor = max(0.15, min(1.0, max_ping / ping))
    speed_factor = min(speed, 1000.0) / 1000.0
    # 72% throughput, 18% latency, 10% source/rank quality.
    return speed_factor * 72.0 + latency_factor * 18.0 + min(rank_hint / 100.0, 1.0) * 10.0


def rank(servers: Iterable[dict], max_ping: float = 250.0, fast_only: bool = True, available_only: bool = True) -> list[dict]:
    def ok(s: dict) -> bool:
        ping = float(s.get("live_ping", s.get("ping", 9999)))
        return (not available_only or bool(s.get("available"))) and (not fast_only or ping <= max_ping)

    candidates = [s for s in servers if ok(s)]
    return sorted(
        candidates,
        key=lambda s: (
            throughput_score(s, max_ping),
            -float(s.get("live_ping", 9999)),
            float(s.get("speed", 0) or 0),
            float(s.get("rank", 0) or 0),
        ),
        reverse=True,
    )
