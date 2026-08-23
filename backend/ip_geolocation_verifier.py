"""Exit IP verification and geolocation helpers for VPN servers."""

from dataclasses import dataclass
from time import time


@dataclass
class IPLocation:
    ip: str
    country: str = "Unknown"
    city: str = "Unknown"
    verified: bool = False
    checked_at: int = 0


class IPGeolocationVerifier:
    def __init__(self, provider=None):
        self.provider = provider
        self.cache = {}

    def verify(self, ip: str):
        if ip in self.cache:
            return self.cache[ip]

        result = IPLocation(ip=ip, checked_at=int(time()))

        if self.provider:
            try:
                data = self.provider(ip)
                result.country = data.get("country", "Unknown")
                result.city = data.get("city", "Unknown")
                result.verified = True
            except Exception:
                result.verified = False

        self.cache[ip] = result
        return result

    def enrich_server(self, server: dict):
        location = self.verify(server.get("exit_ip", ""))
        server.update({
            "country": location.country,
            "city": location.city,
            "ip_verified": location.verified,
            "geo_checked_at": location.checked_at,
        })
        return server


geo_verifier = IPGeolocationVerifier()
