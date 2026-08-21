"""Configurable provider/country/transport failover policy."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class FailoverPolicy:
    providers: tuple[str, ...] = ()
    countries: tuple[str, ...] = ()
    transports: tuple[str, ...] = ("udp", "tcp")
    max_attempts: int = 3

    def ordered_providers(self, current: str | None = None) -> list[str]:
        return [p for p in self.providers if p != current]

    def ordered_countries(self, current: str | None = None) -> list[str]:
        return [c for c in self.countries if c != current]

    def ordered_transports(self, current: str | None = None) -> list[str]:
        return [t for t in self.transports if t != current]

    def validate(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        if not self.transports:
            raise ValueError("at least one transport is required")
