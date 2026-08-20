class ThreatIntelligence:
    def __init__(self):
        self.blocklist = set()

    def block(self, domain):
        self.blocklist.add(domain)

    def is_blocked(self, domain):
        return domain in self.blocklist
