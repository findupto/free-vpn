"""In-process VPN node registry with health and staleness handling."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
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
    def __init__(self, stale_after_seconds: int = 120):
        self.nodes: Dict[str, VPNNode] = {}
        self.stale_after = timedelta(seconds=max(1, stale_after_seconds))

    def register_node(self, node: VPNNode) -> None:
        node.last_seen = datetime.now(timezone.utc).isoformat()
        node.status = "online"
        self.nodes[node.node_id] = node

    def heartbeat(self, node_id: str, health_score: int | None = None) -> bool:
        node = self.nodes.get(node_id)
        if node is None:
            return False
        node.last_seen = datetime.now(timezone.utc).isoformat()
        node.status = "online"
        if health_score is not None:
            node.health_score = max(0, min(int(health_score), 100))
        return True

    def update_health(self, node_id: str, score: int) -> None:
        self.heartbeat(node_id, score)

    def mark_stale(self) -> list[str]:
        now = datetime.now(timezone.utc)
        stale: list[str] = []
        for node in self.nodes.values():
            if not node.last_seen:
                continue
            seen = datetime.fromisoformat(node.last_seen)
            if now - seen > self.stale_after:
                node.status = "stale"
                stale.append(node.node_id)
        return stale

    def get_available_nodes(self, min_health: int = 0) -> list[VPNNode]:
        self.mark_stale()
        threshold = max(0, min(int(min_health), 100))
        return [
            node for node in self.nodes.values()
            if node.status == "online" and node.health_score >= threshold
        ]

    def get_node(self, node_id: str) -> Optional[VPNNode]:
        return self.nodes.get(node_id)
