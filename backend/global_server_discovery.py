"""Global VPN server discovery and fast endpoint selection.

Provides a provider-agnostic registry that can ingest VPN nodes from
multiple regions and select the fastest available endpoint.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed


@dataclass
class GlobalServer:
    id: str
    country: str
    city: str
    endpoint: str
    exit_ip: str
    latency_ms: float = 9999
    online: bool = False
    checked_at: int = 0


class GlobalServerDiscovery:
    def __init__(self):
        self.servers: dict[str, GlobalServer] = {}

    def add_server(self, server: GlobalServer):
        self.servers[server.id] = server

    def import_servers(self, servers: list[dict]):
        for item in servers:
            self.add_server(GlobalServer(**item))

    def probe(self, checker, timeout=5):
        def check(server):
            try:
                latency = checker(server.endpoint, timeout)
                server.latency_ms = float(latency)
                server.online = True
            except Exception:
                server.online = False
            server.checked_at = int(time.time())
            return server

        with ThreadPoolExecutor(max_workers=min(32, len(self.servers) or 1)) as pool:
            jobs = [pool.submit(check, server) for server in self.servers.values()]
            for job in as_completed(jobs):
                job.result()

    def countries(self):
        return sorted(set(server.country for server in self.servers.values()))

    def fastest(self, country=None, limit=10):
        items = [
            server for server in self.servers.values()
            if server.online and (country is None or server.country == country)
        ]
        return [asdict(x) for x in sorted(items, key=lambda s: s.latency_ms)[:limit]]


server_discovery = GlobalServerDiscovery()
