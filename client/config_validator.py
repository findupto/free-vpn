"""
Secure VPN configuration validation layer.

Validates VPN profiles before tunnel creation.
"""

from dataclasses import dataclass


@dataclass
class ValidationResult:
    valid: bool
    reason: str = ""


class ConfigValidator:
    REQUIRED_FIELDS = {
        "server_public_key",
        "endpoint",
        "allowed_ips",
    }

    def validate(self, config: dict) -> ValidationResult:
        if not isinstance(config, dict):
            return ValidationResult(False, "Configuration must be a dictionary")

        missing = self.REQUIRED_FIELDS - set(config.keys())
        if missing:
            return ValidationResult(False, f"Missing fields: {', '.join(sorted(missing))}")

        if not config.get("server_public_key"):
            return ValidationResult(False, "Invalid server key")

        if not config.get("endpoint"):
            return ValidationResult(False, "Invalid endpoint")

        return ValidationResult(True, "Configuration validated")
