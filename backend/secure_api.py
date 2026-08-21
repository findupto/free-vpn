"""Replay-resistant request signing for the control plane."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from collections import OrderedDict


class SecureAPI:
    def __init__(self, secret: str, max_age_seconds: int = 60, max_nonces: int = 4096):
        if not secret:
            raise ValueError("signing secret must not be empty")
        self.secret = secret.encode("utf-8")
        self.max_age_seconds = max(1, int(max_age_seconds))
        self.max_nonces = max(128, int(max_nonces))
        self._seen_nonces: OrderedDict[str, float] = OrderedDict()

    def sign_request(self, payload: str) -> str:
        return hmac.new(self.secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()

    def verify_request(self, payload: str, signature: str) -> bool:
        expected = self.sign_request(payload)
        return hmac.compare_digest(expected, signature)

    def timestamp(self) -> int:
        return int(time.time())

    def create_envelope(self, payload: dict) -> dict:
        envelope = {
            "timestamp": self.timestamp(),
            "nonce": secrets.token_urlsafe(18),
            "payload": payload,
        }
        canonical = json.dumps(envelope, separators=(",", ":"), sort_keys=True)
        envelope["signature"] = self.sign_request(canonical)
        return envelope

    def verify_envelope(self, envelope: dict, now: int | None = None) -> bool:
        if not isinstance(envelope, dict):
            return False
        signature = envelope.get("signature")
        timestamp = envelope.get("timestamp")
        nonce = envelope.get("nonce")
        if not isinstance(signature, str) or not isinstance(timestamp, int) or not isinstance(nonce, str):
            return False
        current = self.timestamp() if now is None else int(now)
        if abs(current - timestamp) > self.max_age_seconds:
            return False
        if nonce in self._seen_nonces:
            return False
        unsigned = {k: envelope[k] for k in ("timestamp", "nonce", "payload") if k in envelope}
        canonical = json.dumps(unsigned, separators=(",", ":"), sort_keys=True)
        if not self.verify_request(canonical, signature):
            return False
        self._seen_nonces[nonce] = float(current)
        while len(self._seen_nonces) > self.max_nonces:
            self._seen_nonces.popitem(last=False)
        return True
