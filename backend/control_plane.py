"""In-process VPN node registry with health, selection, and staleness handling."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional


@dataclass
class VPNNode:
    node_id: str
    region: str
    public_key: str
    endpoint: str = ""
    exit_ip: str = ""
    status: str = "offline"
    health_score: int = 0
    last_seen: Optional[str] = None
    active_sessions: int = 0


class ControlPlane:
    def __init__(self, stale_after_seconds: int = 120):
        self.nodes: Dict[str, VPNNode] = {}
        self.stale_after = timedelta(seconds=max(1, stale_after_seconds))

    def register_node(self, node: VPNNode) -> None:
        node.last_seen = datetime.now(timezone.utc).isoformat()
        node.status = "online"
        node.health_score = max(0, min(int(node.health_score), 100))
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
        return sorted(
            (
                node for node in self.nodes.values()
                if node.status == "online" and node.health_score >= threshold
            ),
            key=lambda node: (-node.health_score, node.active_sessions, node.region, node.node_id),
        )

    def get_node(self, node_id: str) -> Optional[VPNNode]:
        return self.nodes.get(node_id)

    def get_servers(self, min_health: int = 0) -> dict[str, dict]:
        """Compatibility API consumed by ClientServerBridge."""
        return {
            node.node_id: {
                **asdict(node),
                "host": node.endpoint,
                "ip": node.exit_ip,
            }
            for node in self.get_available_nodes(min_health)
        }

    def acquire_session(self, node_id: str) -> bool:
        node = self.nodes.get(node_id)
        if node is None or node.status != "online":
            return False
        node.active_sessions += 1
        return True

    def release_session(self, node_id: str) -> bool:
        node = self.nodes.get(node_id)
        if node is None or node.active_sessions <= 0:
            return False
        node.active_sessions -= 1
        return True

    def best_node(self, min_health: int = 0, exclude_node_id: str | None = None) -> Optional[VPNNode]:
        for node in self.get_available_nodes(min_health):
            if exclude_node_id and node.node_id == exclude_node_id:
                continue
            return node
        return None
