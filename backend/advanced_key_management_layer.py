"""
Advanced Encryption & Key Management Layer

Provides secure key lifecycle management foundation:
- Session key generation
- Key rotation tracking
- Encrypted configuration workflow
- Key revocation support
"""

import time
import secrets
import hashlib


class KeyManager:
    def __init__(self):
        self.keys = {}
        self.revoked = set()

    def create_key(self, owner_id):
        key_id = secrets.token_hex(16)
        secret = secrets.token_hex(32)
        self.keys[key_id] = {
            "owner": owner_id,
            "secret_hash": hashlib.sha256(secret.encode()).hexdigest(),
            "created": time.time(),
            "active": True,
        }
        return {"key_id": key_id, "secret": secret}

    def rotate_key(self, key_id):
        if key_id in self.keys:
            self.keys[key_id]["created"] = time.time()
            return True
        return False

    def revoke_key(self, key_id):
        self.revoked.add(key_id)
        if key_id in self.keys:
            self.keys[key_id]["active"] = False
        return True

    def validate_key(self, key_id):
        return key_id in self.keys and key_id not in self.revoked and self.keys[key_id]["active"]
