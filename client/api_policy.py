"""API validation, pagination, rate limiting and cancellation helpers."""
from __future__ import annotations
import time
from dataclasses import dataclass

@dataclass(frozen=True)
class RetryDecision:
    retry: bool
    delay: float = 0.0
    reason: str = ""

class RateLimitState:
    def __init__(self): self.retry_at = 0.0
    def apply(self, seconds: float, now: float | None = None):
        now = time.time() if now is None else now
        self.retry_at = max(self.retry_at, now + max(0.0, seconds))
    def available(self, now: float | None = None):
        return (time.time() if now is None else now) >= self.retry_at

class APIPolicy:
    def __init__(self, timeout: float = 10.0, max_retries: int = 3):
        self.timeout = max(.1, timeout); self.max_retries = max(0, max_retries); self.rate_limit = RateLimitState()
    def validate_object(self, value, required: set[str] = frozenset()):
        if not isinstance(value, dict) or not required.issubset(value): raise ValueError("invalid API response schema")
        return value
    def validate_page(self, value, item_key="servers"):
        if not isinstance(value, dict) or not isinstance(value.get(item_key), list): raise ValueError("invalid API page schema")
        return value[item_key]
    def retry_after(self, value):
        try: delay = max(0.0, min(300.0, float(value)))
        except (TypeError, ValueError): delay = 0.0
        self.rate_limit.apply(delay)
        return RetryDecision(delay > 0, delay, "retry_after")
    def decision(self, status: int, attempt: int, retry_after: float | None = None):
        if attempt >= self.max_retries: return RetryDecision(False, 0, "retry_limit")
        if status == 429:
            delay = max(0.0, min(300.0, retry_after or 1.0)); self.rate_limit.apply(delay); return RetryDecision(True, delay, "rate_limited")
        if status in {408, 425, 500, 502, 503, 504}:
            return RetryDecision(True, min(30.0, .5 * (2 ** attempt)), "transient")
        return RetryDecision(False, 0, "non_retryable")
    def deadline(self, started: float | None = None) -> float:
        return (time.monotonic() if started is None else started) + self.timeout
