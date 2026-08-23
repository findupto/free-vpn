"""
AI Security Guardian Engine
Premium VPN security monitoring foundation.
"""

from datetime import datetime


class AISecurityGuardianEngine:
    def __init__(self):
        self.events = []
        self.threat_score = 0

    def record_event(self, event_type, details=None):
        event = {
            "time": datetime.utcnow().isoformat(),
            "type": event_type,
            "details": details or {}
        }
        self.events.append(event)
        return event

    def analyze(self, metrics=None):
        metrics = metrics or {}
        score = 0

        if metrics.get("dns_leak"):
            score += 40
        if metrics.get("webrtc_leak"):
            score += 30
        if metrics.get("suspicious_traffic"):
            score += 30

        self.threat_score = score

        return {
            "threat_score": score,
            "action": "auto_repair" if score >= 50 else "monitor"
        }

    def get_history(self):
        return self.events
