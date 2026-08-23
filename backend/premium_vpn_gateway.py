"""Unified VPN gateway orchestration layer.

Combines server discovery, ranking, connection selection,
and failover components into one client-facing interface.
"""

from dataclasses import dataclass, asdict
from time import time


@dataclass
class VPNServerView:
    country: str
    city: str
    ip: str
    latency_ms: float
    score: float
    online: bool = True


class PremiumVPNGateway:
    def __init__(self, registry=None, selector=None, connector=None):
        self.registry = registry
        self.selector = selector
        self.connector = connector
        self.sessions = {}

    def list_servers(self, country=None):
        servers = []
        if self.registry and hasattr(self.registry, "servers"):
            servers = self.registry.servers
        if country:
            servers = [s for s in servers if s.get("country") == country]
        return sorted(servers, key=lambda x: x.get("latency_ms", 999999))

    def fastest(self):
        servers = self.list_servers()
        return servers[0] if servers else None

    def connect(self, server):
        if not server:
            return {"connected": False, "error": "No server available"}

        try:
            result = self.connector(server) if self.connector else True
            session = {
                "server": server,
                "connected_at": int(time()),
                "active": bool(result),
            }
            self.sessions[str(server)] = session
            return session
        except Exception as exc:
            return {"connected": False, "error": str(exc)}

    def status(self):
        return list(self.sessions.values())


premium_gateway = PremiumVPNGateway()
