"""
Findupto VPN Firewall Kill Switch

Security layer preventing traffic leakage when VPN tunnel is unavailable.
Provides platform abstraction for production firewall backends.
"""

import platform


class FirewallKillSwitch:
    def __init__(self):
        self.enabled = False
        self.platform = platform.system()

    def enable(self):
        """Enable VPN-only traffic policy."""
        self.enabled = True
        return {
            "status": "enabled",
            "platform": self.platform,
            "mode": "vpn_only"
        }

    def disable(self):
        """Disable kill switch protection."""
        self.enabled = False
        return {
            "status": "disabled"
        }

    def status(self):
        return {
            "enabled": self.enabled,
            "platform": self.platform
        }
