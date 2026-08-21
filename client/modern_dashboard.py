"""Modern dashboard components for Findupto VPN.

Designed to replace the basic table-only interface with reusable widgets.
"""

import time


class ConnectionMetrics:
    def __init__(self):
        self.reset()

    def reset(self):
        self.connected = False
        self.server = None
        self.download = 0.0
        self.upload = 0.0
        self.latency = 0.0
        self.jitter = 0.0
        self.loss = 0.0
        self.updated = time.time()

    def update(self, **values):
        for key, value in values.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.updated = time.time()


class ServerScore:
    @staticmethod
    def calculate(server):
        ping = max(float(server.get("ping", 999)), 1)
        speed = float(server.get("speed", 0))
        loss = float(server.get("loss", 0))
        jitter = float(server.get("jitter", 0))

        return (
            min(speed / 100, 1) * 40
            + max(0, 30 - ping / 5)
            + max(0, 20 - loss * 2)
            + max(0, 10 - jitter)
        )


class DashboardState:
    def __init__(self):
        self.metrics = ConnectionMetrics()
        self.servers = []

    def rank_servers(self, servers):
        self.servers = sorted(
            servers,
            key=ServerScore.calculate,
            reverse=True,
        )
        return self.servers
