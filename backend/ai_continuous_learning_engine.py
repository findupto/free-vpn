"""
AI Continuous Learning Engine
Learns from VPN connection attempts, performance results,
errors and repairs to improve future decisions.
"""

import json
import time
from pathlib import Path


class AIContinuousLearningEngine:
    def __init__(self, storage="ai_learning_history.json"):
        self.storage = Path(storage)
        self.memory = self._load()

    def _load(self):
        if self.storage.exists():
            try:
                return json.loads(self.storage.read_text())
            except Exception:
                pass
        return []

    def record_result(self, event, result, metadata=None):
        self.memory.append({
            "time": time.time(),
            "event": event,
            "result": result,
            "metadata": metadata or {}
        })
        self.storage.write_text(json.dumps(self.memory, indent=2))

    def analyze_pattern(self):
        scores = {}
        for item in self.memory:
            key = item.get("event", "unknown")
            scores[key] = scores.get(key, 0) + 1
        return {
            "total_events": len(self.memory),
            "patterns": scores
        }

    def recommend(self, event):
        history = [x for x in self.memory if x.get("event") == event]
        failures = sum(1 for x in history if x.get("result") == "failed")
        if failures > len(history) / 2 and history:
            return "apply_alternative_strategy"
        return "continue_normal_strategy"
