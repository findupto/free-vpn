"""Cross-platform DNS configuration verification helpers."""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass


@dataclass
class DNSStatus:
    enabled: bool = False
    protected_dns: str | None = None
    leak_check_passed: bool = False
    observed_servers: tuple[str, ...] = ()
    reason: str = "not checked"


class DNSLeakGuard:
    def __init__(self, dns_server="1.1.1.1"):
        self.dns_server = dns_server
        self.status = DNSStatus()

    def enable(self):
        self.status.enabled = True
        self.status.protected_dns = self.dns_server
        return self.status

    def disable(self):
        self.status = DNSStatus()
        return self.status

    def _observed_servers(self) -> tuple[str, ...]:
        if os.name == "nt":
            try:
                output = subprocess.check_output(
                    ["ipconfig", "/all"], text=True, errors="replace", timeout=4,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            except (OSError, subprocess.SubprocessError):
                return ()
            return tuple(dict.fromkeys(re.findall(r"(?:DNS Servers|DNS-Server)[ .]*:?[ \t]+([0-9a-fA-F:.]+)", output)))
        try:
            text = open("/etc/resolv.conf", encoding="utf-8", errors="replace").read()
        except OSError:
            return ()
        return tuple(dict.fromkeys(re.findall(r"^\s*nameserver\s+([^\s#]+)", text, re.MULTILINE)))

    def verify(self):
        if not self.status.enabled or not self.dns_server:
            self.status.leak_check_passed = False
            self.status.reason = "DNS protection is not enabled"
            return self.status
        observed = self._observed_servers()
        self.status.observed_servers = observed
        self.status.leak_check_passed = bool(observed) and set(observed) == {self.dns_server}
        self.status.reason = "resolver configuration matches protected DNS" if self.status.leak_check_passed else "system resolver configuration differs from protected DNS"
        return self.status

    def get_status(self):
        return self.status
