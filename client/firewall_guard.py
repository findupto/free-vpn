"""Platform firewall protection layer for Findupto VPN.

This module provides the interface used by the VPN core to enable a kill switch.
The implementation is intentionally separated so platform-specific firewall
providers can be added safely.
"""

from __future__ import annotations

import platform


class FirewallGuard:
    """Manage VPN traffic protection state."""

    def __init__(self) -> None:
        self.enabled = False
        self.platform = platform.system()

    def enable_kill_switch(self, vpn_interface: str | None = None) -> bool:
        """Enable protected mode.

        A platform backend should apply firewall rules here. The state machine
        is kept independent from the VPN protocol implementation.
        """
        self.enabled = True
        return True

    def disable_kill_switch(self) -> bool:
        """Disable protected mode and restore normal networking."""
        self.enabled = False
        return True

    def is_enabled(self) -> bool:
        return self.enabled
