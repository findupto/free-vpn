"""API response validation, pagination and retry-after helpers."""
from __future__ import annotations
import time
from dataclasses import dataclass

@dataclass(frozen=True)
class RetryDecision:
    retry: bool
    delay: float = 0.0

class APIPolicy:
    def __init__(self, timeout: float = 10.0): self.timeout = max(.1, timeout)
    def validate_object(self, value, required: set[str] = frozenset()):
        if not isinstance(value, dict) or not required.issubset(value):
            raise ValueError("invalid API response schema")
        return value
    def retry_after(self, value: str | int | float | None) -> RetryDecision:
        try: delay = max(0.0, min(300.0, float(value)))
        except (TypeError, ValueError): delay = 0.0
        return RetryDecision(delay > 0, delay)
    def deadline(self, started: float | None = None) -> float:
        return (time.monotonic() if started is None else started) + self.timeout
