"""Global VPN server registry.

Maintains discovered server nodes, metadata and availability state.
"""

from dataclasses import dataclass, asdict
import time


@dataclass
class ServerNode:
    country: str
    city: str
    host: str
    ip: str
    latency_ms: float = 9999
    online: bool = True
    last_check: int = 0


class GlobalServerRegistry:
    def __init__(self):
        self.nodes = {}

    def add_server(self, server: ServerNode):
        key = f"{server.country}:{server.host}"
        server.last_check = int(time.time())
        self.nodes[key] = server

    def update_health(self, host, latency, online=True):
        for node in self.nodes.values():
            if node.host == host:
                node.latency_ms = latency
                node.online = online
                node.last_check = int(time.time())

    def list_servers(self, country=None):
        servers = [n for n in self.nodes.values() if n.online]
        if country:
            servers = [n for n in servers if n.country.lower() == country.lower()]
        return sorted(servers, key=lambda x: x.latency_ms)

    def export(self):
        return [asdict(server) for server in self.list_servers()]


registry = GlobalServerRegistry()
