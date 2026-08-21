"""Allowlist policy for safely consuming VPN profile metadata."""
from __future__ import annotations
from dataclasses import dataclass

ALLOWED_DIRECTIVES = {
    "client", "dev", "proto", "remote", "resolv-retry", "nobind",
    "persist-key", "persist-tun", "remote-cert-tls", "auth-nocache",
    "auth-user-pass", "verb", "cipher", "data-ciphers", "auth",
}

@dataclass(frozen=True)
class Directive:
    name: str
    value: str

class ProfilePolicy:
    def __init__(self, allowed: set[str] | None = None):
        self.allowed = {x.lower() for x in (allowed or ALLOWED_DIRECTIVES)}

    def parse(self, text: str) -> list[Directive]:
        result: list[Directive] = []
        for number, raw in enumerate(text.splitlines(), 1):
            line = raw.strip()
            if not line or line.startswith("#") or line.startswith(";"):
                continue
            parts = line.split(None, 1)
            name = parts[0].lower()
            if name not in self.allowed:
                raise ValueError(f"unsupported OpenVPN directive at line {number}: {name}")
            result.append(Directive(name, parts[1] if len(parts) == 2 else ""))
        return result
