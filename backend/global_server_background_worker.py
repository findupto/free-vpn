"""Background worker for maintaining global VPN server inventory."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import Event


@dataclass
class ServerRecord:
    host: str
    country: str = "Unknown"
    city: str = "Unknown"
    latency_ms: float = 9999
    online: bool = False
    updated_at: float = field(default_factory=time.time)


class GlobalServerDatabaseWorker:
    def __init__(self, interval=300):
        self.interval = interval
        self.servers = {}
        self.stop_event = Event()

    def update_server(self, record: ServerRecord):
        record.updated_at = time.time()
        self.servers[record.host] = record

    def remove_offline(self):
        self.servers = {
            host: server
            for host, server in self.servers.items()
            if server.online
        }

    def ranked_servers(self):
        return sorted(
            self.servers.values(),
            key=lambda server: (not server.online, server.latency_ms),
        )

    def run_once(self, collector=None):
        if collector:
            for server in collector():
                self.update_server(server)
        self.remove_offline()
        return self.ranked_servers()

    def stop(self):
        self.stop_event.set()
