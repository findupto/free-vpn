"""Credential lifecycle and safe temporary-profile policies."""
from __future__ import annotations
from dataclasses import dataclass
import os, stat, tempfile

@dataclass(frozen=True)
class CredentialRecord:
    name: str
    expires_at: float | None = None
    failures: int = 0
    quarantined: bool = False

class CredentialPolicy:
    def __init__(self, max_failures: int = 5):
        self.max_failures = max(1, max_failures)
        self.records: dict[str, CredentialRecord] = {}

    def register(self, name: str, expires_at: float | None = None) -> None:
        self.records[name] = CredentialRecord(name, expires_at)

    def failure(self, name: str) -> None:
        old = self.records.get(name, CredentialRecord(name))
        failures = old.failures + 1
        self.records[name] = CredentialRecord(name, old.expires_at, failures, failures >= self.max_failures)

    def success(self, name: str) -> None:
        old = self.records.get(name, CredentialRecord(name))
        self.records[name] = CredentialRecord(name, old.expires_at)

    def usable(self, name: str, now: float) -> bool:
        item = self.records.get(name)
        return bool(item and not item.quarantined and (item.expires_at is None or item.expires_at > now))

class SecureTempProfile:
    def __init__(self, content: str):
        self.path = None
        fd, path = tempfile.mkstemp(prefix="freevpn-", suffix=".ovpn")
        self.path = path
        os.fchmod(fd, stat.S_IRUSR | stat.S_IWUSR)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)

    def cleanup(self) -> None:
        if self.path:
            try:
                os.remove(self.path)
            except FileNotFoundError:
                pass
            self.path = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.cleanup()
