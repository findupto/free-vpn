"""Privacy helpers for diagnostics and logs.

Logs must never become a second place where VPN credentials or secrets are stored.
"""

from __future__ import annotations

import re

_SECRET_PATTERNS = (
    re.compile(r"(?i)(password|passwd|token|secret|authorization|proxy-pass)(\s*[:=]\s*)([^\s,;]+)"),
    re.compile(r"(?i)(auth-user-pass)(\s+)([^\s]+)"),
    re.compile(r"-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----", re.DOTALL),
)


def redact_log_message(message: str) -> str:
    value = str(message)
    for pattern in _SECRET_PATTERNS:
        value = pattern.sub(lambda m: f"{m.group(1)}{m.group(2)}[REDACTED]" if m.lastindex and m.lastindex >= 2 else "[REDACTED]", value)
    return value
