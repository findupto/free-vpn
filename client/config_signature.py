"""Secure VPN configuration signature verification foundation."""

import hashlib
import hmac
import json


class ConfigSignature:
    def __init__(self, signing_key: str):
        self.signing_key = signing_key.encode("utf-8")

    def sign(self, config: dict) -> str:
        payload = json.dumps(config, sort_keys=True).encode("utf-8")
        return hmac.new(self.signing_key, payload, hashlib.sha256).hexdigest()

    def verify(self, config: dict, signature: str) -> bool:
        expected = self.sign(config)
        return hmac.compare_digest(expected, signature)


class SecureConfigValidator:
    def __init__(self, signing_key: str):
        self.signature = ConfigSignature(signing_key)

    def validate(self, config: dict, signature: str) -> bool:
        return self.signature.verify(config, signature)
