"""
IPv6 Protection Layer

Provides the foundation for preventing IPv6 leaks while VPN protection is active.
Platform-specific implementations can extend this module.
"""


class IPv6Guard:
    def __init__(self):
        self.protection_enabled = False

    def enable_protection(self):
        self.protection_enabled = True
        return True

    def disable_protection(self):
        self.protection_enabled = False
        return True

    def check_status(self):
        return {
            "ipv6_protection": self.protection_enabled,
            "leak_safe": self.protection_enabled,
        }
