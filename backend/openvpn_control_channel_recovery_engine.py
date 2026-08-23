"""
OpenVPN Control Channel Recovery Engine
Handles endpoint failures where servers do not complete TLS/control-channel push exchange.
"""

from datetime import datetime


class OpenVPNControlChannelRecoveryEngine:
    def __init__(self):
        self.failures = []

    def analyze_failure(self, server, error):
        reason = "unknown"
        if "control-channel" in error.lower() or "push exchange" in error.lower():
            reason = "openvpn_handshake_failure"

        event = {
            "server": server,
            "error": error,
            "reason": reason,
            "time": datetime.utcnow().isoformat()
        }
        self.failures.append(event)
        return event

    def should_retry(self, server_failures):
        return server_failures < 3

    def recovery_actions(self):
        return [
            "validate certificate",
            "switch UDP/TCP transport",
            "retry with fresh endpoint",
            "remove unhealthy server from pool"
        ]

    def get_history(self):
        return self.failures
