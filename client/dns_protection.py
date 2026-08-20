"""DNS protection layer for Findupto VPN.

Provides the abstraction required for DNS leak prevention.
Platform-specific adapters can enforce DNS routing while the VPN tunnel is active.
"""

from dataclasses import dataclass
from typing import Iterable


@dataclass
class DNSState:
    enabled: bool = False
    protected_servers: tuple[str, ...] = ()


class DNSProtection:
    """Manage VPN DNS protection lifecycle."""

    def __init__(self, servers: Iterable[str] = ()):
        self.state = DNSState(protected_servers=tuple(servers))

    def enable(self) -> None:
        self.state.enabled = True

    def disable(self) -> None:
        self.state.enabled = False

    def is_protected(self) -> bool:
        return self.state.enabled and bool(self.state.protected_servers)

    def verify(self) -> bool:
        """Return current protection status.

        OS-level DNS enforcement will be implemented by platform adapters.
        """
        return self.is_protected()
