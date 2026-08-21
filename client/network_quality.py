"""Rolling network quality measurements and server migration signals."""
from __future__ import annotations
from collections import deque
from dataclasses import dataclass
from statistics import mean, pstdev

@dataclass(frozen=True)
class Quality:
    latency_ms: float
    jitter_ms: float
    loss_pct: float
    samples: int

class QualityMonitor:
    def __init__(self, window: int = 20):
        self.latencies = deque(maxlen=max(2, int(window)))
        self.sent = 0; self.lost = 0
    def record(self, latency_ms: float | None) -> Quality:
        self.sent += 1
        if latency_ms is None:
            self.lost += 1
        else:
            if latency_ms < 0: raise ValueError("latency cannot be negative")
            self.latencies.append(float(latency_ms))
        return self.quality()
    def quality(self) -> Quality:
        vals = list(self.latencies)
        return Quality(mean(vals) if vals else float("inf"), pstdev(vals) if len(vals) > 1 else 0.0,
                       (self.lost / self.sent * 100.0) if self.sent else 0.0, len(vals))
    def degraded(self, max_latency=500.0, max_jitter=150.0, max_loss_pct=10.0) -> bool:
        q = self.quality()
        return q.latency_ms > max_latency or q.jitter_ms > max_jitter or q.loss_pct > max_loss_pct
