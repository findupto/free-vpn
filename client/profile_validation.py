"""Validation helpers for downloaded VPN profiles."""
from __future__ import annotations
import re
from dataclasses import dataclass

@dataclass(frozen=True)
class ProfileLimits:
    max_bytes: int = 512_000
    max_directives: int = 256
    max_embedded_blocks: int = 16

class ProfileValidator:
    REMOTE = re.compile(r"^[A-Za-z0-9._:-]+$")
    FORBIDDEN = {"compress", "comp-lzo", "up", "down", "route-up", "down-pre", "plugin", "script-security", "tls-verify"}

    def __init__(self, limits: ProfileLimits | None = None):
        self.limits = limits or ProfileLimits()

    def validate(self, text: str) -> None:
        if len(text.encode("utf-8")) > self.limits.max_bytes:
            raise ValueError("VPN profile exceeds size limit")
        directives = 0
        blocks = 0
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or line.startswith(";"):
                continue
            directives += 1
            if directives > self.limits.max_directives:
                raise ValueError("VPN profile contains too many directives")
            if line.startswith("<") and line.endswith(">"):
                blocks += 1
                if blocks > self.limits.max_embedded_blocks:
                    raise ValueError("VPN profile contains too many embedded blocks")
            name = line.split(None, 1)[0].lower()
            if name in self.FORBIDDEN:
                raise ValueError(f"unsafe VPN directive: {name}")
