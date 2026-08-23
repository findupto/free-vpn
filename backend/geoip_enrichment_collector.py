"""Automatic server metadata enrichment layer.

Provides a safe framework for collecting VPN nodes and attaching
country/city information before publishing them to clients.
"""

from dataclasses import dataclass
from time import time


@dataclass
class GeoServer:
    endpoint: str
    country: str = "Unknown"
    city: str = "Unknown"
    ip: str = ""
    verified: bool = False
    updated_at: int = 0


class GeoIPEnrichmentCollector:
    def __init__(self):
        self.servers = {}

    def register(self, endpoint, ip="", country="Unknown", city="Unknown"):
        server = GeoServer(
            endpoint=endpoint,
            ip=ip,
            country=country,
            city=city,
            verified=bool(country != "Unknown"),
            updated_at=int(time()),
        )
        self.servers[endpoint] = server
        return server

    def enrich(self, endpoint, geo_data):
        server = self.servers.get(endpoint)
        if not server:
            return None
        server.country = geo_data.get("country", server.country)
        server.city = geo_data.get("city", server.city)
        server.ip = geo_data.get("ip", server.ip)
        server.verified = True
        server.updated_at = int(time())
        return server

    def export(self):
        return [vars(server) for server in self.servers.values()]


geoip_collector = GeoIPEnrichmentCollector()
