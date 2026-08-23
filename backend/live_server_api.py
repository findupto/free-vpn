"""Live server API adapter.

Provides a single interface for clients to request available VPN locations,
filter countries, and connect using the fastest available endpoint.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import List

from .fast_connect_manager import FastConnectManager
from .global_server_discovery import GlobalServerDiscovery


@dataclass
class ServerView:
    country: str
    city: str
    ip: str
    latency_ms: float
    status: str


class LiveVPNServerAPI:
    def __init__(self):
        self.discovery = GlobalServerDiscovery()
        self.connector = FastConnectManager()

    def list_servers(self, country: str | None = None) -> List[dict]:
        servers = self.discovery.discover()
        if country:
            servers = [s for s in servers if s.get("country", "").lower() == country.lower()]

        return [
            asdict(ServerView(
                country=s.get("country", "Unknown"),
                city=s.get("city", "Unknown"),
                ip=s.get("ip") or s.get("endpoint", ""),
                latency_ms=float(s.get("latency_ms", 9999)),
                status=s.get("status", "available"),
            ))
            for s in servers
        ]

    def connect(self, server):
        return self.connector.connect_fast(server)


server_api = LiveVPNServerAPI()
