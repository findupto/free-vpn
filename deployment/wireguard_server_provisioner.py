"""
WireGuard Server Provisioner Foundation

Provides automated server setup workflow abstraction.
Production adapters can integrate with cloud providers,
SSH automation, and secret managers.
"""

from dataclasses import dataclass
from typing import Dict


@dataclass
class ServerNode:
    hostname: str
    region: str
    public_ip: str = ""
    status: str = "pending"


class WireGuardProvisioner:
    def __init__(self):
        self.nodes: Dict[str, ServerNode] = {}

    def register_node(self, node: ServerNode):
        self.nodes[node.hostname] = node
        return node

    def generate_server_config(self, node_name: str):
        node = self.nodes[node_name]
        return {
            "interface": "wg0",
            "hostname": node.hostname,
            "region": node.region,
            "status": node.status,
        }

    def provision(self, node_name: str):
        node = self.nodes[node_name]
        node.status = "provisioning"
        return self.generate_server_config(node_name)

    def get_status(self, node_name: str):
        return self.nodes[node_name].status
