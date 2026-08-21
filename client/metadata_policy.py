"""Validation primitives for authenticated server/provider metadata."""
from __future__ import annotations
import hashlib, hmac, json, time
from dataclasses import dataclass

@dataclass(frozen=True)
class MetadataEnvelope:
    payload: dict
    key_id: str
    signature: str
    expires_at: float

class MetadataPolicy:
    def __init__(self, trusted_keys: dict[str, bytes]):
        self.trusted_keys = dict(trusted_keys)
        self.revoked: set[str] = set()

    @staticmethod
    def canonical(payload: dict) -> bytes:
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()

    def verify(self, envelope: MetadataEnvelope, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        if envelope.key_id in self.revoked or envelope.expires_at <= now:
            return False
        key = self.trusted_keys.get(envelope.key_id)
        if key is None:
            return False
        expected = hmac.new(key, self.canonical(envelope.payload), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, envelope.signature)

    def revoke(self, key_id: str) -> None:
        self.revoked.add(key_id)

    def rotate(self, key_id: str, key: bytes) -> None:
        if not key_id or not key:
            raise ValueError("key id and key are required")
        self.trusted_keys[key_id] = key
