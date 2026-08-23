"""Realtime client synchronization helpers for VPN server selection."""

from __future__ import annotations

import time


class ClientServerSync:
    def __init__(self, refresh_interval=15):
        self.refresh_interval = refresh_interval
        self.last_sync = 0
        self.cache = []

    def update_servers(self, servers):
        self.cache = sorted(
            servers,
            key=lambda server: (
                server.get("latency_ms", 999999),
                server.get("load", 999999),
            ),
        )
        self.last_sync = time.time()
        return self.cache

    def should_refresh(self):
        return (time.time() - self.last_sync) >= self.refresh_interval

    def get_fastest(self):
        healthy = [s for s in self.cache if s.get("status", "offline") == "online"]
        return healthy[0] if healthy else None

    def country_list(self):
        return sorted({s.get("country") for s in self.cache if s.get("country")})


client_sync = ClientServerSync()
