"""
AI Network Intelligence Engine

Detects network conditions and recommends VPN connection strategies.
"""

from datetime import datetime


class AINetworkIntelligenceEngine:
    def __init__(self):
        self.events = []

    def analyze_network(self, metrics):
        issues = []
        strategy = []

        latency = metrics.get("latency", 0)
        packet_loss = metrics.get("packet_loss", 0)
        dns_ok = metrics.get("dns_ok", True)
        firewall = metrics.get("firewall_detected", False)

        if latency > 200:
            issues.append("high_latency")
            strategy.append("select_nearer_server")

        if packet_loss > 5:
            issues.append("packet_loss")
            strategy.append("switch_protocol")

        if not dns_ok:
            issues.append("dns_issue")
            strategy.append("repair_dns_configuration")

        if firewall:
            issues.append("firewall_restriction")
            strategy.append("try_tcp_fallback")

        result = {
            "time": datetime.utcnow().isoformat(),
            "issues": issues,
            "recommended_actions": strategy,
            "network_quality": self._score(metrics),
        }

        self.events.append(result)
        return result

    def _score(self, metrics):
        score = 100
        score -= min(metrics.get("latency", 0) / 5, 40)
        score -= min(metrics.get("packet_loss", 0) * 3, 30)
        return max(0, round(score, 2))

    def history(self):
        return self.events
