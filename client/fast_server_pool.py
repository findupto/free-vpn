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


def rank(servers: Iterable[dict], max_ping: float = 250.0, fast_only: bool = True, available_only: bool = True) -> list[dict]:
    def ok(s: dict) -> bool:
        ping = float(s.get("live_ping", s.get("ping", 9999)))
        return (not available_only or bool(s.get("available"))) and (not fast_only or ping <= max_ping)
    return sorted((s for s in servers if ok(s)), key=lambda s: (float(s.get("live_ping", 9999)), -float(s.get("speed", 0) or 0), -float(s.get("rank", 0) or 0)))
