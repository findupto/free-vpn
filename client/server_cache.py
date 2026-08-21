"""Validated, expiring local cache for VPN server metadata."""
from __future__ import annotations
import hashlib, json, time
from dataclasses import dataclass

@dataclass
class CacheEntry:
    payload: dict
    expires_at: float
    digest: str

class ServerCache:
    def __init__(self, ttl_seconds: int = 900):
        self.ttl_seconds = max(1, int(ttl_seconds))
        self._entry: CacheEntry | None = None

    @staticmethod
    def _digest(payload: dict) -> str:
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        return hashlib.sha256(raw).hexdigest()

    def put(self, payload: dict, now: float | None = None) -> None:
        if not isinstance(payload, dict):
            raise TypeError("server metadata must be a dictionary")
        now = time.time() if now is None else now
        self._entry = CacheEntry(dict(payload), now + self.ttl_seconds, self._digest(payload))

    def get(self, now: float | None = None) -> dict | None:
        if self._entry is None:
            return None
        now = time.time() if now is None else now
        if now >= self._entry.expires_at:
            self._entry = None
            return None
        if self._digest(self._entry.payload) != self._entry.digest:
            self._entry = None
            return None
        return dict(self._entry.payload)

    def clear(self) -> None:
        self._entry = None
