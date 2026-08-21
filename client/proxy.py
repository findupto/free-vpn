"""Validated HTTP CONNECT and SOCKS5 proxy configuration primitives."""
from __future__ import annotations
from dataclasses import dataclass
from urllib.parse import urlsplit

@dataclass(frozen=True)
class ProxyConfig:
    scheme: str
    host: str
    port: int
    username: str | None = None
    password: str | None = None

    @classmethod
    def parse(cls, value: str) -> "ProxyConfig":
        parsed = urlsplit(value)
        scheme = parsed.scheme.lower()
        if scheme not in {"http", "https", "socks5"}:
            raise ValueError("proxy scheme must be http, https, or socks5")
        if not parsed.hostname or not (1 <= (parsed.port or 0) <= 65535):
            raise ValueError("invalid proxy endpoint")
        return cls(scheme, parsed.hostname, parsed.port, parsed.username, parsed.password)

    def redacted(self) -> str:
        auth = f"{self.username}:<redacted>@" if self.username else ""
        return f"{self.scheme}://{auth}{self.host}:{self.port}"
