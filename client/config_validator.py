"""Defensive validation for VPN configuration dictionaries."""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass
class ValidationResult:
    valid: bool
    reason: str = ""


class ConfigValidator:
    REQUIRED_FIELDS = {"server_public_key", "endpoint", "allowed_ips"}

    def validate(self, config: dict) -> ValidationResult:
        if not isinstance(config, dict):
            return ValidationResult(False, "Configuration must be a dictionary")
        missing = self.REQUIRED_FIELDS - set(config.keys())
        if missing:
            return ValidationResult(False, f"Missing fields: {', '.join(sorted(missing))}")
        key = config.get("server_public_key")
        if not isinstance(key, str) or not (32 <= len(key) <= 128):
            return ValidationResult(False, "Invalid server public key")
        endpoint = config.get("endpoint")
        if not isinstance(endpoint, str) or not self._valid_endpoint(endpoint):
            return ValidationResult(False, "Invalid VPN endpoint")
        allowed = config.get("allowed_ips")
        if not isinstance(allowed, (list, tuple)) or not allowed:
            return ValidationResult(False, "allowed_ips must contain at least one network")
        try:
            for network in allowed:
                ipaddress.ip_network(str(network), strict=False)
        except ValueError:
            return ValidationResult(False, "Invalid allowed IP network")
        return ValidationResult(True, "Configuration validated")

    @staticmethod
    def _valid_endpoint(endpoint: str) -> bool:
        parsed = urlparse(endpoint if "://" in endpoint else f"vpn://{endpoint}")
        host = parsed.hostname
        port = parsed.port
        return bool(host) and port is not None and 1 <= port <= 65535
