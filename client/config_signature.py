"""Deterministic HMAC signing for trusted VPN configuration metadata."""

from __future__ import annotations

import hashlib
import hmac
import json


class ConfigSignature:
    def __init__(self, signing_key: str):
        if not signing_key:
            raise ValueError("signing key must not be empty")
        self.signing_key = signing_key.encode("utf-8")

    @staticmethod
    def _canonical(config: dict) -> bytes:
        if not isinstance(config, dict):
            raise TypeError("config must be a dictionary")
        return json.dumps(config, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

    def sign(self, config: dict) -> str:
        return hmac.new(self.signing_key, self._canonical(config), hashlib.sha256).hexdigest()

    def verify(self, config: dict, signature: str) -> bool:
        if not isinstance(signature, str) or not signature:
            return False
        try:
            expected = self.sign(config)
        except (TypeError, ValueError):
            return False
        return hmac.compare_digest(expected, signature)


class SecureConfigValidator:
    def __init__(self, signing_key: str):
        self.signature = ConfigSignature(signing_key)

    def validate(self, config: dict, signature: str) -> bool:
        return self.signature.verify(config, signature)
