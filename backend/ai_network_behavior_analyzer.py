"""AI-style network behavior analyzer for VPN optimization."""

from statistics import mean


class NetworkBehaviorAnalyzer:
    def __init__(self):
        self.history = {}

    def record_session(self, user_id, metrics):
        self.history.setdefault(user_id, []).append(metrics)

    def analyze(self, user_id, current_metrics=None):
        sessions = self.history.get(user_id, [])
        combined = sessions[-20:]
        if current_metrics:
            combined.append(current_metrics)

        if not combined:
            return {
                "recommendation": "balanced",
                "confidence": 0
            }

        latency = mean(x.get("latency", 100) for x in combined)
        loss = mean(x.get("packet_loss", 0) for x in combined)
        speed = mean(x.get("speed", 0) for x in combined)

        if loss > 5:
            mode = "stability"
        elif latency < 50 and speed > 50:
            mode = "performance"
        elif latency > 150:
            mode = "low_latency_priority"
        else:
            mode = "balanced"

        return {
            "recommendation": mode,
            "latency": latency,
            "packet_loss": loss,
            "speed": speed,
            "confidence": min(len(combined) * 5, 100)
        }
