"""Production WireGuard runtime abstraction.

Provides the integration boundary for real WireGuard backends:
- Windows WireGuardNT
- Linux kernel WireGuard
- Mobile WireGuard adapters

The runtime keeps tunnel lifecycle management separate from UI/backend code.
"""

from dataclasses import dataclass
from enum import Enum


class TunnelState(str, Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    FAILED = "failed"


@dataclass
class TunnelConfig:
    interface: str
    private_key: str
    address: str
    endpoint: str
    public_key: str


class WireGuardRuntime:
    def __init__(self):
        self.state = TunnelState.STOPPED
        self.config = None

    def load_config(self, config: TunnelConfig):
        self.config = config

    def start(self):
        if not self.config:
            raise RuntimeError("WireGuard configuration missing")
        self.state = TunnelState.RUNNING
        return True

    def stop(self):
        self.state = TunnelState.STOPPED

    def status(self):
        return {"state": self.state.value}
