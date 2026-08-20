from __future__ import annotations

"""Compatibility facade for the Findupto VPN engine."""

import os
import re
import ssl
import subprocess
import time
import urllib.request
from pathlib import Path

import vpn_engine as base

APP_VERSION = "13.1.9"
ROOT = base.ROOT
LOG = base.LOG
PROFILE_LOGS = base.PROFILE_LOGS
CACHE = base.CACHE


def log(msg):
    return base.log(msg)


def http_get(url, timeout=10, limit=10_000_000):
    return base.http_get(url, timeout, limit)


def openvpn_exe():
    return base.openvpn_exe()


def _route_lines() -> list[str]:
    if os.name != "nt":
        return []
    try:
        cp = subprocess.run(
            ["route", "print", "-4"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return [" ".join(line.strip().split()) for line in cp.stdout.splitlines()]
    except Exception as exc:
        log(f"ROUTE SNAPSHOT FAIL error={type(exc).__name__}: {exc}")
        return []


def full_tunnel_routes(snapshot: str) -> bool:
    """Return True only when both Windows IPv4 /1 routes are present."""
    prefixes = set()
    for part in str(snapshot or "").split(" | "):
        fields = part.split()
        if len(fields) >= 2 and fields[0] in {"0.0.0.0", "128.0.0.0"} and fields[1] == "128.0.0.0":
            prefixes.add(fields[0])
    return prefixes == {"0.0.0.0", "128.0.0.0"}


def route_snapshot():
    """Return a snapshot only when BOTH Windows IPv4 /1 routes exist."""
    if os.name != "nt":
        return ""

    lines = _route_lines()
    hits = [
        line
        for line in lines
        if line.startswith("0.0.0.0 128.0.0.0")
        or line.startswith("128.0.0.0 128.0.0.0")
    ]
    prefixes = {line.split()[0] for line in hits if line.split()}
    if {"0.0.0.0", "128.0.0.0"}.issubset(prefixes):
        return " | ".join(hits[-8:])

    try:
        command = (
            "Get-NetRoute -AddressFamily IPv4 -ErrorAction SilentlyContinue "
            "| Where-Object { $_.DestinationPrefix -eq '0.0.0.0/1' -or "
            "$_.DestinationPrefix -eq '128.0.0.0/1' } "
            "| ForEach-Object { $_.DestinationPrefix + ' ' + $_.NextHop + ' ' + $_.InterfaceIndex + ' ' + $_.RouteMetric }"
        )
        cp = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        ps_hits = [" ".join(x.strip().split()) for x in cp.stdout.splitlines() if "/1" in x]
        ps_prefixes = {x.split()[0] for x in ps_hits if x.split()}
        if {"0.0.0.0/1", "128.0.0.0/1"}.issubset(ps_prefixes):
            return " | ".join(ps_hits[-8:])
    except Exception as exc:
        log(f"POWERSHELL ROUTE SNAPSHOT FAIL error={type(exc).__name__}: {exc}")

    return ""


# Keep the pristine base helper across reloads. Re-importing this module must
# never capture our already-wrapped _prepare, otherwise repeated launches or
# test reloads can recurse forever.
if not hasattr(base, "_FINDUPTO_ORIGINAL_PREPARE"):
    base._FINDUPTO_ORIGINAL_PREPARE = base._prepare
_BASE_PREPARE = base._FINDUPTO_ORIGINAL_PREPARE


def _prepare(*args, **kwargs):
    """Harden generated profiles for reliable Windows full-tunnel routing."""
    config = _BASE_PREPARE(*args, **kwargs)
    path = Path(config)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
        filtered = []
        cipher_line = None
        for line in lines:
            low = line.strip().lower()
            if low.startswith("route 0.0.0.0 128.0.0.0") or low.startswith("route 128.0.0.0 128.0.0.0"):
                continue
            if low.startswith("redirect-gateway "):
                continue
            if low.startswith("data-ciphers "):
                cipher_line = line
            if low.startswith("data-ciphers-fallback "):
                continue
            filtered.append(line)

        filtered.append("redirect-gateway def1 bypass-dhcp bypass-dns")
        filtered.append("route-metric 5")
        filtered.append("route-method exe")
        filtered.append("route-delay 2 30")
        filtered.append("show-net-up")
        filtered.append("disable-dco")
        if cipher_line is None:
            filtered.append("data-ciphers AES-256-GCM:AES-128-GCM:CHACHA20-POLY1305:AES-256-CBC")
        filtered.append("data-ciphers-fallback AES-256-CBC")

        path.write_text("\n".join(filtered) + "\n", encoding="utf-8")
    except Exception as exc:
        log(f"PROFILE HARDENING FAIL error={type(exc).__name__}: {exc}")
        raise
    return config


base.route_snapshot = route_snapshot
base._prepare = _prepare


_DIRECT_SSL = ssl.create_default_context()
_DIRECT_OPENER = urllib.request.build_opener(
    urllib.request.ProxyHandler({}),
    urllib.request.HTTPSHandler(context=_DIRECT_SSL),
)


def public_ip(timeout: float = 8):
    """Get public IP directly, bypassing HTTP(S) proxy environment settings."""
    for url in ("https://api.ipify.org", "https://ifconfig.me/ip", "https://icanhazip.com"):
        try:
            request = urllib.request.Request(
                url,
                headers={"User-Agent": base.UA, "Accept": "text/plain", "Connection": "close"},
            )
            with _DIRECT_OPENER.open(request, timeout=min(max(4.0, timeout), 15)) as response:
                value = response.read(256).decode("ascii", "ignore").strip()
            if re.fullmatch(r"(?:\d{1,3}\.){3}\d{1,3}", value) or ":" in value:
                log(f"PUBLIC IP DIRECT url={url} public_ip={value}")
                return value
        except Exception as exc:
            log(f"PUBLIC IP DIRECT FAIL url={url} error={type(exc).__name__}: {exc}")
    raise RuntimeError("Unable to determine public IP without proxy")


def verify_tunnel(previous_ip: str | None = None, timeout: float = 8):
    """Verify both full-tunnel routes and a changed public IP."""
    snapshot = route_snapshot()
    if os.name == "nt" and not full_tunnel_routes(snapshot):
        raise RuntimeError("VPN initialized but both Windows full-tunnel /1 routes are missing")
    ip = public_ip(timeout)
    if previous_ip and ip == previous_ip:
        raise RuntimeError(
            f"VPN initialized but public IP did not change ({ip}); traffic is not using the VPN)"
        )
    log(
        f"TUNNEL VERIFIED public_ip={ip} previous_ip={previous_ip or 'unknown'} "
        f"routes={snapshot or 'non-Windows'}"
    )
    return ip


def connect(*args, **kwargs):
    return base.connect(*args, **kwargs)


def discover(deadline: float = 10):
    """Fast discovery using VPNBook; never block on the slow VPN Gate APIs."""
    started = time.monotonic()
    merged = {s["id"]: s for s in base._cache_load()}
    try:
        servers = base.vpnbook_servers()
        for server in servers:
            if base._is_real_server(server):
                merged[server["id"]] = server
        log(f"DISCOVERY VPNBOOK READY servers={len(servers)}")
    except Exception as exc:
        log(f"DISCOVERY VPNBOOK FAIL error={type(exc).__name__}: {exc}")

    data = sorted(
        merged.values(),
        key=lambda s: (s.get("rank", -999), -s.get("ping", 9999)),
        reverse=True,
    )[: base.MAX_DISCOVERY]
    base._cache_save(data)
    log(f"DISCOVERY READY candidates={len(data)} elapsed={time.monotonic()-started:.2f}s")
    return data


for _name in (
    "parse_gate",
    "vpnbook_servers_from_html",
    "vpnbook_servers",
    "full_tunnel_routes",
    "_is_real_server",
):
    if _name not in globals() and hasattr(base, _name):
        globals()[_name] = getattr(base, _name)
