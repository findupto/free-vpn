"""
Automatic VPN Self-Healing AI Engine

Provides automated diagnosis and recovery workflow foundation.
"""

import time


class SelfHealingEngine:
    def __init__(self):
        self.history = []

    def analyze_issue(self, metrics):
        issues = []

        if metrics.get("latency", 0) > 200:
            issues.append("high_latency")
        if metrics.get("packet_loss", 0) > 5:
            issues.append("packet_loss")
        if not metrics.get("connected", True):
            issues.append("connection_failure")

        return issues

    def repair_action(self, issues):
        actions = []

        for issue in issues:
            if issue == "high_latency":
                actions.append("switch_better_server")
            elif issue == "packet_loss":
                actions.append("change_protocol")
            elif issue == "connection_failure":
                actions.append("restart_connection")

        event = {
            "time": time.time(),
            "issues": issues,
            "actions": actions,
        }

        self.history.append(event)
        return event

    def get_history(self):
        return self.history
