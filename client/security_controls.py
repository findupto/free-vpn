"""Client-side security controls for VPN sessions.

These controls provide safe policy/state management and diagnostics. OS-specific
firewall and route changes remain behind explicit adapter interfaces so importing
this module never changes the host network unexpectedly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from ipaddress import ip_address, ip_network
from typing import Iterable


class KillSwitchState(str, Enum):
    DISABLED = "disabled"
    ARMING = "arming"
    ARMED = "armed"
    DISARMING = "disarming"


@dataclass
class RoutePolicy:
    full_tunnel: bool = True
    allowed_networks: set[str] = field(default_factory=set)
    excluded_networks: set[str] = field(default_factory=set)

    def validate(self) -> None:
        for value in self.allowed_networks | self.excluded_networks:
            ip_network(value, strict=False)
        if self.allowed_networks & self.excluded_networks:
            raise ValueError("A network cannot be both allowed and excluded")


@dataclass
class SecurityState:
    kill_switch: KillSwitchState = KillSwitchState.DISABLED
    vpn_interface: str | None = None
    public_interface: str | None = None
    route_policy: RoutePolicy = field(default_factory=RoutePolicy)


class FirewallAdapter:
    """Platform adapter contract; implementations must be fail-closed."""

    def arm(self, state: SecurityState) -> bool:
        raise NotImplementedError

    def disarm(self, state: SecurityState) -> bool:
        raise NotImplementedError


class SecurityController:
    def __init__(self, firewall: FirewallAdapter | None = None):
        self.firewall = firewall
        self.state = SecurityState()

    def configure_routes(self, policy: RoutePolicy) -> SecurityState:
        policy.validate()
        self.state.route_policy = policy
        return self.state

    def arm_kill_switch(self) -> bool:
        if self.firewall is None:
            return False
        self.state.kill_switch = KillSwitchState.ARMING
        if self.firewall.arm(self.state):
            self.state.kill_switch = KillSwitchState.ARMED
            return True
        self.state.kill_switch = KillSwitchState.DISABLED
        return False

    def disarm_kill_switch(self) -> bool:
        if self.firewall is None:
            return False
        self.state.kill_switch = KillSwitchState.DISARMING
        if self.firewall.disarm(self.state):
            self.state.kill_switch = KillSwitchState.DISABLED
            return True
        self.state.kill_switch = KillSwitchState.ARMED
        return False

    @staticmethod
    def validate_endpoint(host: str, port: int) -> bool:
        if not host or not (1 <= port <= 65535):
            return False
        try:
            ip_address(host)
            return True
        except ValueError:
            return all(1 <= len(part) <= 63 for part in host.split("."))
