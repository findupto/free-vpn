"""Cross-platform firewall enforcement abstraction.

Provides the control layer for:
- Windows Filtering Platform
- Linux nftables
- macOS packet filter
"""

from enum import Enum


class FirewallMode(str, Enum):
    DISABLED = "disabled"
    VPN_ONLY = "vpn_only"


class FirewallEngine:
    def __init__(self):
        self.mode = FirewallMode.DISABLED

    def enable_vpn_only(self):
        # Platform-specific enforcement hooks are implemented by adapters.
        self.mode = FirewallMode.VPN_ONLY

    def disable(self):
        self.mode = FirewallMode.DISABLED

    def status(self):
        return {"mode": self.mode.value}
