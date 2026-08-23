"""
VPN Threat Detection Engine
Provides suspicious activity detection foundation.
"""

from datetime import datetime


class ThreatDetectionEngine:
    def __init__(self):
        self.events = []
        self.blocked_sessions = set()

    def analyze_session(self, session_id, metrics):
        risk = 0

        if metrics.get("connection_changes", 0) > 5:
            risk += 30
        if metrics.get("failed_attempts", 0) > 3:
            risk += 30
        if metrics.get("traffic_spike", False):
            risk += 20
        if metrics.get("unknown_device", False):
            risk += 20

        result = {
            "session_id": session_id,
            "risk_score": risk,
            "status": "blocked" if risk >= 70 else "safe",
            "timestamp": datetime.utcnow().isoformat()
        }

        self.events.append(result)

        if result["status"] == "blocked":
            self.blocked_sessions.add(session_id)

        return result

    def is_blocked(self, session_id):
        return session_id in self.blocked_sessions

    def get_events(self):
        return self.events
