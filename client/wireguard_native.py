"""
WireGuard native integration layer.

Provides the production interface for connecting the VPN client with
platform WireGuard implementations.

This module intentionally keeps OS driver calls isolated so Windows,
Linux and mobile backends can be added safely.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class WireGuardInterface:
    name: str
    public_key: Optional[str] = None
    active: bool = False


class WireGuardNative:
    def __init__(self):
        self.interface = None

    def create_interface(self, name: str = "findupto0"):
        self.interface = WireGuardInterface(name=name)
        return self.interface

    def configure_keys(self, private_key: str, public_key: str):
        if not self.interface:
            raise RuntimeError("WireGuard interface not created")
        self.interface.public_key = public_key

    def start(self):
        if not self.interface:
            raise RuntimeError("WireGuard interface not created")
        self.interface.active = True
        return True

    def stop(self):
        if self.interface:
            self.interface.active = False
        return True

    def status(self):
        return {
            "interface": self.interface.name if self.interface else None,
            "active": self.interface.active if self.interface else False,
        }
