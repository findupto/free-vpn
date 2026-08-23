"""
AI VPN Authentication Recovery Engine

Handles authentication failures, rejected public relays,
credential issues, and endpoint trust decisions.
"""

from datetime import datetime


class AIVPNAuthenticationRecoveryEngine:
    def __init__(self):
        self.history = []

    def analyze_failure(self, error_message):
        error = error_message.lower()

        diagnosis = "unknown"
        actions = []

        if "authentication rejected" in error:
            diagnosis = "authentication_failure"
            actions.extend([
                "refresh credentials",
                "remove invalid relay",
                "test alternate endpoint"
            ])

        elif "no working vpn endpoint" in error:
            diagnosis = "endpoint_failure"
            actions.extend([
                "rescan servers",
                "check protocol compatibility",
                "try backup nodes"
            ])

        elif "certificate" in error:
            diagnosis = "certificate_failure"
            actions.append("validate and refresh certificate")

        event = {
            "time": datetime.utcnow().isoformat(),
            "error": error_message,
            "diagnosis": diagnosis,
            "actions": actions
        }

        self.history.append(event)
        return event

    def get_history(self):
        return self.history
