"""Premium Fast Connect Engine

Provides intelligent one-click VPN connection selection logic.
"""

import time


class PremiumFastConnectEngine:
    def __init__(self):
        self.history = []

    def rank_servers(self, servers):
        return sorted(
            servers,
            key=lambda s: (
                s.get("latency", 9999),
                -s.get("speed", 0),
                s.get("load", 100),
            ),
        )

    def select_fastest(self, servers):
        ranked = self.rank_servers(servers)
        selected = ranked[0] if ranked else None
        self.history.append({
            "time": time.time(),
            "selected": selected,
            "count": len(servers),
        })
        return selected

    def get_history(self):
        return self.history
