"""Smart multi-path VPN routing support.

Ranks multiple available routes and keeps fallback paths ready
for improved reliability and performance.
"""

from dataclasses import dataclass
import time


@dataclass
class RoutePath:
    endpoint: str
    latency_ms: float = 9999
    packet_loss: float = 100
    bandwidth_score: float = 0
    active: bool = True

    def score(self):
        return (
            (100 - min(self.packet_loss, 100)) * 0.35
            + max(0, 100 - self.latency_ms / 10) * 0.35
            + self.bandwidth_score * 0.30
        )


class MultiPathRouter:
    def __init__(self):
        self.routes = []
        self.last_switch = 0

    def add_route(self, route: RoutePath):
        self.routes.append(route)

    def remove_failed(self):
        self.routes = [r for r in self.routes if r.active]

    def best_route(self):
        self.remove_failed()
        if not self.routes:
            return None
        return max(self.routes, key=lambda r: r.score())

    def prepare_fallbacks(self):
        return sorted(self.routes, key=lambda r: r.score(), reverse=True)

    def switch_allowed(self, cooldown=10):
        now = time.time()
        if now - self.last_switch >= cooldown:
            self.last_switch = now
            return True
        return False


multipath_router = MultiPathRouter()
