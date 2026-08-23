"""Traffic intelligence engine for adaptive VPN performance."""

from dataclasses import dataclass
from time import time


@dataclass
class TrafficProfile:
    mode: str
    reason: str
    updated_at: float


class TrafficIntelligenceEngine:
    def __init__(self):
        self.history = []

    def analyze(self, latency_ms, packet_loss, bandwidth_mbps):
        if packet_loss > 5:
            mode = "stability"
            reason = "high packet loss detected"
        elif latency_ms > 150:
            mode = "latency"
            reason = "high latency detected"
        elif bandwidth_mbps > 50:
            mode = "throughput"
            reason = "high bandwidth available"
        else:
            mode = "balanced"
            reason = "normal network conditions"

        profile = TrafficProfile(mode, reason, time())
        self.history.append(profile)
        return profile

    def recommended_features(self, profile):
        return {
            "streaming": profile.mode == "throughput",
            "gaming": profile.mode == "latency",
            "reliability": profile.mode == "stability",
            "adaptive_tuning": True,
        }


traffic_intelligence = TrafficIntelligenceEngine()
