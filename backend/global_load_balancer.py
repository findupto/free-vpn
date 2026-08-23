"""
Global VPN Load Balancer Engine
Distributes users across healthy servers and avoids overloaded nodes.
"""

from time import time


class GlobalLoadBalancer:
    def __init__(self):
        self.nodes = {}

    def register_node(self, node_id, country, capacity=100):
        self.nodes[node_id] = {
            "country": country,
            "capacity": capacity,
            "users": 0,
            "health": 100,
            "updated": time(),
        }

    def update_load(self, node_id, users, health=100):
        if node_id in self.nodes:
            self.nodes[node_id]["users"] = users
            self.nodes[node_id]["health"] = health
            self.nodes[node_id]["updated"] = time()

    def score(self, node):
        capacity = max(node["capacity"], 1)
        load_score = max(0, 100 - (node["users"] / capacity * 100))
        return (load_score * 0.6) + (node["health"] * 0.4)

    def best_server(self):
        if not self.nodes:
            return None
        return max(self.nodes.items(), key=lambda x: self.score(x[1]))[0]

    def available_servers(self):
        return sorted(
            self.nodes.items(),
            key=lambda x: self.score(x[1]),
            reverse=True,
        )
