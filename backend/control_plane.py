"""
Findupto VPN Control Plane Foundation

Provides the initial backend orchestration layer for:
- VPN node registration
- Server health state tracking
- Secure configuration delivery hooks
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Optional


@dataclass
class VPNNode:
    node_id: str
    region: str
    public_key: str
    status: str = "offline"
    health_score: int = 0
    last_seen: Optional[str] = None


class ControlPlane:
    def __init__(self):
        self.nodes: Dict[str, VPNNode] = {}

    def register_node(self, node: VPNNode):
        node.last_seen = datetime.now(timezone.utc).isoformat()
        node.status = "online"
        self.nodes[node.node_id] = node

    def update_health(self, node_id: str, score: int):
        if node_id in self.nodes:
            self.nodes[node_id].health_score = max(0, min(score, 100))
            self.nodes[node_id].last_seen = datetime.now(timezone.utc).isoformat()

    def get_available_nodes(self):
        return [
            node for node in self.nodes.values()
            if node.status == "online"
        ]

    def get_node(self, node_id: str):
        return self.nodes.get(node_id)
