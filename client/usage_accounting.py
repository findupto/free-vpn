"""Crash-tolerant in-memory session accounting primitives."""
from __future__ import annotations
from dataclasses import dataclass
from time import monotonic

@dataclass
class Usage:
    uploaded: int = 0
    downloaded: int = 0
    packets: int = 0
    started: float | None = None

class UsageAccounting:
    def __init__(self): self.usage = Usage()
    def start(self) -> None: self.usage.started = monotonic()
    def add(self, uploaded: int = 0, downloaded: int = 0, packets: int = 0) -> None:
        if min(uploaded, downloaded, packets) < 0: raise ValueError("usage cannot be negative")
        self.usage.uploaded += uploaded; self.usage.downloaded += downloaded; self.usage.packets += packets
    def duration(self) -> float:
        return 0.0 if self.usage.started is None else max(0.0, monotonic() - self.usage.started)
    def snapshot(self) -> dict[str, int | float]:
        return {"uploaded": self.usage.uploaded, "downloaded": self.usage.downloaded, "packets": self.usage.packets, "duration": self.duration()}
