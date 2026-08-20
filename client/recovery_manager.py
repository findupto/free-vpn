"""Adaptive recovery logic for failed VPN connections."""

class RecoveryManager:
    def __init__(self):
        self.failures = {}

    def record_failure(self, server, reason):
        self.failures.setdefault(server, []).append(reason)

    def strategy(self, reason):
        if "timeout" in reason.lower():
            return "switch_transport"
        if "auth" in reason.lower():
            return "refresh_credentials"
        if "push" in reason.lower():
            return "retry_profile"
        return "next_best_server"

    def should_block(self, server):
        return len(self.failures.get(server, [])) >= 5
