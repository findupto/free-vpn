"""
Automatic Country & IP Expansion Engine

Discovers, organizes and ranks VPN locations globally.
"""

from datetime import datetime


class AutomaticCountryIPEngine:
    def __init__(self):
        self.countries = {}
        self.history = []

    def add_server(self, country, ip, latency=None):
        self.countries.setdefault(country, []).append({
            "ip": ip,
            "latency": latency,
            "added": datetime.utcnow().isoformat()
        })
        self.history.append({
            "event": "server_added",
            "country": country,
            "ip": ip
        })

    def list_countries(self):
        return list(self.countries.keys())

    def get_servers(self, country=None):
        if country:
            return self.countries.get(country, [])
        return self.countries

    def rank_servers(self, country):
        servers = self.countries.get(country, [])
        return sorted(
            servers,
            key=lambda x: x.get("latency") or 999999
        )

    def get_history(self):
        return self.history
