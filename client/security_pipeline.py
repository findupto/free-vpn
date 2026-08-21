"""Integrated policy primitives for authenticated VPN metadata and profiles."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import hmac, time

@dataclass(frozen=True)
class TrustRecord:
    key_id: str
    fingerprint: str
    expires_at: float
    revoked: bool = False

class SecurityPipeline:
    def __init__(self, records: dict[str, TrustRecord] | None = None):
        self.records = records or {}

    def add(self, key_id: str, material: bytes, expires_at: float) -> TrustRecord:
        fp = sha256(material).hexdigest()
        record = TrustRecord(key_id, fp, expires_at)
        self.records[key_id] = record
        return record

    def revoke(self, key_id: str) -> None:
        record = self.records.get(key_id)
        if record:
            self.records[key_id] = TrustRecord(record.key_id, record.fingerprint, record.expires_at, True)

    def verify(self, key_id: str, material: bytes, payload: bytes, signature: str, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        record = self.records.get(key_id)
        if not record or record.revoked or record.expires_at <= now:
            return False
        if not hmac.compare_digest(record.fingerprint, sha256(material).hexdigest()):
            return False
        expected = hmac.new(material, payload, sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    @staticmethod
    def validate_version(version: int, minimum: int = 1, maximum: int = 100) -> bool:
        return minimum <= version <= maximum
