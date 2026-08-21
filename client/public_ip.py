"""Public-IP change verification without embedding credentials or stateful services."""
from __future__ import annotations
from dataclasses import dataclass
import ipaddress

@dataclass(frozen=True)
class IPCheck:
    before: str | None
    after: str | None
    changed: bool
    valid: bool

class PublicIPVerifier:
    @staticmethod
    def validate(value: str) -> str:
        try:
            return str(ipaddress.ip_address(value))
        except ValueError as exc:
            raise ValueError("invalid public IP") from exc
    @classmethod
    def compare(cls, before: str | None, after: str | None) -> IPCheck:
        b = cls.validate(before) if before else None
        a = cls.validate(after) if after else None
        return IPCheck(b, a, bool(b and a and b != a), bool(a))
