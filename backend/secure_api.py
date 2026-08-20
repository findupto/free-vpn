"""Secure API communication foundation for VPN control plane."""

import hashlib
import hmac
import time


class SecureAPI:
    def __init__(self, secret: str):
        self.secret = secret.encode()

    def sign_request(self, payload: str) -> str:
        message = payload.encode()
        return hmac.new(self.secret, message, hashlib.sha256).hexdigest()

    def verify_request(self, payload: str, signature: str) -> bool:
        expected = self.sign_request(payload)
        return hmac.compare_digest(expected, signature)

    def timestamp(self) -> int:
        return int(time.time())
