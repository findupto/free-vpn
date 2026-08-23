"""
Global IP Reputation & Server Trust Engine

Provides VPN exit-node trust scoring, reputation checks,
and safer server selection foundations.
"""

from datetime import datetime


class IPReputationEngine:
    def __init__(self):
        self.records = {}

    def register_ip(self, ip, country=None):
        self.records[ip] = {
            "ip": ip,
            "country": country,
            "risk_score": 0,
            "trust_score": 100,
            "checks": [],
            "updated_at": datetime.utcnow().isoformat()
        }
        return self.records[ip]

    def update_reputation(self, ip, risk_score, reason=None):
        if ip not in self.records:
            self.register_ip(ip)

        self.records[ip]["risk_score"] = risk_score
        self.records[ip]["trust_score"] = max(0, 100 - risk_score)
        if reason:
            self.records[ip]["checks"].append(reason)
        self.records[ip]["updated_at"] = datetime.utcnow().isoformat()
        return self.records[ip]

    def is_trusted(self, ip, minimum_score=70):
        record = self.records.get(ip)
        if not record:
            return False
        return record["trust_score"] >= minimum_score

    def get_best_servers(self, ips):
        return sorted(
            [self.records[ip] for ip in ips if ip in self.records],
            key=lambda item: item["trust_score"],
            reverse=True
        )


ip_reputation_engine = IPReputationEngine()
