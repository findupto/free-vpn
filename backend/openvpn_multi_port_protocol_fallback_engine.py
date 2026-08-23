"""
OpenVPN Multi-Port Protocol Auto Fallback Engine
Provides fallback strategy for failed VPN endpoint connections.
"""

from datetime import datetime


class OpenVPNFallbackEngine:
    def __init__(self):
        self.history = []
        self.protocols = ["udp", "tcp"]
        self.ports = [1194, 443, 53, 80]

    def generate_attempts(self, endpoint):
        attempts = []
        for protocol in self.protocols:
            for port in self.ports:
                attempts.append({
                    "endpoint": endpoint,
                    "protocol": protocol,
                    "port": port
                })
        return attempts

    def record_result(self, attempt, success, error=None):
        self.history.append({
            "time": datetime.utcnow().isoformat(),
            "attempt": attempt,
            "success": success,
            "error": error
        })

    def best_next_attempt(self):
        failed = {str(x["attempt"]) for x in self.history if not x["success"]}
        for protocol in self.protocols:
            for port in self.ports:
                item = {"protocol": protocol, "port": port}
                if str(item) not in failed:
                    return item
        return None
