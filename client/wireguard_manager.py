"""
WireGuard tunnel management foundation.

Provides a protocol-independent interface for creating,
starting and stopping WireGuard connections.
Platform-specific drivers can be added without changing the VPN core.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class WireGuardConfig:
    private_key: str
    server_public_key: str
    endpoint: str
    address: str
    dns: Optional[str] = None
    allowed_ips: str = "0.0.0.0/0"
    persistent_keepalive: int = 25


class WireGuardManager:
    def __init__(self):
        self.active = False
        self.config: Optional[WireGuardConfig] = None

    def load_config(self, config: WireGuardConfig) -> bool:
        if not config.private_key or not config.server_public_key:
            return False
        self.config = config
        return True

    def connect(self) -> bool:
        if not self.config:
            return False

        # Real platform drivers should be called here:
        # Windows: WireGuardNT
        # Linux: wg / wg-quick
        # Mobile: native VPN APIs
        self.active = True
        return True

    def disconnect(self) -> bool:
        self.active = False
        return True

    def status(self) -> dict:
        return {
            "protocol": "wireguard",
            "connected": self.active,
            "endpoint": self.config.endpoint if self.config else None,
        }
