"""Live VPN server dashboard helpers.

Provides UI-ready data formatting for country, IP, latency and connection status.
"""

from datetime import datetime


class ServerDashboard:
    def __init__(self, discovery=None):
        self.discovery = discovery

    def format_servers(self, servers):
        output = []
        for server in servers or []:
            output.append({
                "country": server.get("country", "Unknown"),
                "city": server.get("city", "Unknown"),
                "ip": server.get("exit_ip", server.get("ip", "")),
                "endpoint": server.get("endpoint", ""),
                "latency_ms": server.get("latency_ms", None),
                "load": server.get("load", 0),
                "online": server.get("online", True),
                "updated": datetime.utcnow().isoformat(),
            })
        return sorted(output, key=lambda item: (
            item["latency_ms"] is None,
            item["latency_ms"] or 999999
        ))

    def fastest(self, servers):
        available = [s for s in self.format_servers(servers) if s["online"]]
        return available[0] if available else None


server_dashboard = ServerDashboard()
