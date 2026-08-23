"""
OpenVPN Auto Repair & Config Validator Engine

Validates OpenVPN endpoint configurations and prepares recovery actions.
"""

from datetime import datetime


class OpenVPNConfigValidator:
    def __init__(self):
        self.history = []

    def validate(self, config):
        checks = {
            "certificate": bool(config.get("certificate")),
            "remote": bool(config.get("remote")),
            "port": bool(config.get("port")),
            "protocol": config.get("protocol") in ["udp", "tcp"]
        }

        result = {
            "valid": all(checks.values()),
            "checks": checks,
            "time": datetime.utcnow().isoformat()
        }
        self.history.append(result)
        return result

    def repair_actions(self, result):
        actions = []
        if not result["checks"]["certificate"]:
            actions.append("refresh_certificate")
        if not result["checks"]["remote"]:
            actions.append("replace_endpoint")
        if not result["checks"]["port"]:
            actions.append("test_alternative_ports")
        if not result["checks"]["protocol"]:
            actions.append("switch_protocol")
        return actions

    def get_history(self):
        return self.history
