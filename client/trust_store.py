"""Small provider/server trust store with key rotation and revocation."""
from __future__ import annotations
from dataclasses import dataclass
import hashlib

@dataclass(frozen=True)
class TrustedKey:
    key_id: str
    fingerprint: str
    revoked: bool = False

class TrustStore:
    def __init__(self): self._keys: dict[str, TrustedKey] = {}
    @staticmethod
    def fingerprint(key_material: str) -> str:
        return hashlib.sha256(key_material.encode()).hexdigest()
    def add(self, key_id: str, key_material: str) -> TrustedKey:
        key = TrustedKey(key_id, self.fingerprint(key_material))
        self._keys[key_id] = key
        return key
    def revoke(self, key_id: str) -> None:
        key = self._keys[key_id]
        self._keys[key_id] = TrustedKey(key.key_id, key.fingerprint, True)
    def trusted(self, key_id: str, key_material: str) -> bool:
        key = self._keys.get(key_id)
        return bool(key and not key.revoked and key.fingerprint == self.fingerprint(key_material))
