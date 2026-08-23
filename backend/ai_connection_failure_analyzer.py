"""
AI Connection Failure Analyzer
Analyzes VPN connection failures and recommends recovery actions.
"""

from datetime import datetime


class AIConnectionFailureAnalyzer:
    def __init__(self):
        self.history = []

    def analyze(self, error_log: str):
        error = error_log.lower()
        result = {
            "time": datetime.utcnow().isoformat(),
            "error": error_log,
            "reason": "unknown",
            "repair": []
        }

        if "control-channel" in error or "tls" in error:
            result["reason"] = "openvpn_handshake_failure"
            result["repair"] = [
                "try alternate server",
                "switch udp/tcp protocol",
                "validate certificates"
            ]
        elif "timeout" in error or "unreachable" in error:
            result["reason"] = "endpoint_failure"
            result["repair"] = [
                "remove endpoint",
                "scan replacement servers"
            ]
        elif "certificate" in error:
            result["reason"] = "certificate_issue"
            result["repair"] = [
                "refresh certificate configuration"
            ]

        self.history.append(result)
        return result

    def get_history(self):
        return self.history
