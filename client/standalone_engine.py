from __future__ import annotations

import gzip
import os
import re
import shutil
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import vpn_engine as base

APP_VERSION = "13.1.0"
ROOT, LOG, PROFILE_LOGS, CACHE = base.ROOT, base.LOG, base.PROFILE_LOGS, base.CACHE


def log(msg):
    base.log(msg)


def http_get(url, timeout=10, limit=10_000_000):
    """Small stdlib-only HTTP client used by the packaged application."""
    started = time.monotonic()
    request = urllib.request.Request(
        url,
        headers={"User-Agent": f"FinduptoVPN/{APP_VERSION}", "Accept": "*/*", "Connection": "close"},
    )
    try:
        with urllib.request.urlopen(request, timeout=min(max(2.0, timeout), 15), context=ssl.create_default_context()) as response:
            data = response.read(limit + 1)
            if len(data) > limit:
                raise RuntimeError("response too large")
            if "gzip" in (response.headers.get("Content-Encoding") or "").lower():
                data = gzip.decompress(data)
            log(f"HTTP OK method=urllib url={url} bytes={len(data)} elapsed={time.monotonic()-started:.2f}s")
            return data
    except Exception as exc:
        log(f"HTTP FAIL url={url} error={type(exc).__name__}: {exc}")
        raise


def openvpn_exe():
    return base.openvpn_exe()


def route_snapshot():
    return base.route_snapshot()


def _prepare(*args, **kwargs):
    return base._prepare(*args, **kwargs)


def connect(*args, **kwargs):
    return base.connect(*args, **kwargs)


def verify_tunnel(*args, **kwargs):
    return base.verify_tunnel(*args, **kwargs)


# Export the public engine API without eagerly evaluating missing attributes.
# The previous globals().get(..., getattr(...)) evaluated getattr() even when
# the local override already existed, causing startup to crash when older
# vpn_engine.py files did not provide full_tunnel_routes.
for _name in (
    "APP_VERSION",
    "ROOT",
    "LOG",
    "PROFILE_LOGS",
    "CACHE",
    "parse_gate",
    "vpnbook_servers_from_html",
    "vpnbook_servers",
    "discover",
    "public_ip",
    "full_tunnel_routes",
    "route_snapshot",
    "openvpn_exe",
    "connect",
    "verify_tunnel",
    "log",
    "http_get",
    "_prepare",
):
    if _name in globals():
        continue
    if hasattr(base, _name):
        globals()[_name] = getattr(base, _name)
