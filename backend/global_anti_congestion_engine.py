"""
Global Anti Congestion Engine
Maintains region health and prevents overloaded VPN routes.
"""

from datetime import datetime


class GlobalAntiCongestionEngine:
    def __init__(self):
        self.regions = {}

    def update_region(self, region, active_users=0, latency=0, load=0):
        self.regions[region] = {
            "active_users": active_users,
            "latency": latency,
            "load": load,
            "updated": datetime.utcnow().isoformat(),
        }

    def congestion_score(self, region):
        data = self.regions.get(region, {})
        load = data.get("load", 100)
        latency = data.get("latency", 999)
        users = data.get("active_users", 0)
        return max(0, 100 - ((load * 0.5) + (latency * 0.3) + (users * 0.01)))

    def best_region(self):
        if not self.regions:
            return None
        return max(self.regions, key=self.congestion_score)

    def status(self):
        return {
            "regions": self.regions,
            "best_region": self.best_region(),
        }
