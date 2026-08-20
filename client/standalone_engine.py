from __future__ import annotations

"""Windows-facing hardening facade for the Findupto VPN engine."""

import os
import re
import ssl
import subprocess
import time
import urllib.request
from pathlib import Path

import vpn_engine as base

APP_VERSION = base.APP_VERSION
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
        cp = subprocess.run(["route", "print", "-4"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=5, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return [" ".join(line.strip().split()) for line in cp.stdout.splitlines()]
    except Exception as exc:
        log(f"ROUTE SNAPSHOT FAIL error={type(exc).__name__}: {exc}")
        return []


def full_tunnel_routes(snapshot: str) -> bool:
    prefixes = set()
    for part in str(snapshot or "").split(" | "):
        fields = part.split()
        if len(fields) < 2:
            continue
        destination = fields[0].replace("/1", "")
        if destination in {"0.0.0.0", "128.0.0.0"} and fields[1] in {"128.0.0.0", "/1"}:
            prefixes.add(destination)
    return prefixes == {"0.0.0.0", "128.0.0.0"}


def route_snapshot() -> str:
    """Read every Windows /1 route, with PowerShell fallback."""
    if os.name != "nt":
        return ""
    hits = [line for line in _route_lines() if line.startswith("0.0.0.0 128.0.0.0") or line.startswith("128.0.0.0 128.0.0.0")]
    prefixes = {line.split()[0] for line in hits if line.split()}
    if {"0.0.0.0", "128.0.0.0"}.issubset(prefixes):
        return " | ".join(hits)
    try:
        command = ("Get-NetRoute -AddressFamily IPv4 -ErrorAction SilentlyContinue "
                   "| Where-Object { $_.DestinationPrefix -eq '0.0.0.0/1' -or "
                   "$_.DestinationPrefix -eq '128.0.0.0/1' } "
                   "| ForEach-Object { $_.DestinationPrefix + ' ' + $_.NextHop + ' ' + "
                   "$_.InterfaceIndex + ' ' + $_.RouteMetric }")
        cp = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", command], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=5, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        ps_hits = [" ".join(x.strip().split()) for x in cp.stdout.splitlines() if "/1" in x]
        if {"0.0.0.0/1", "128.0.0.0/1"}.issubset({x.split()[0] for x in ps_hits if x.split()}):
            return " | ".join(ps_hits)
    except Exception as exc:
        log(f"POWERSHELL ROUTE SNAPSHOT FAIL error={type(exc).__name__}: {exc}")
    return ""


if not hasattr(base, "_FINDUPTO_ORIGINAL_PREPARE"):
    base._FINDUPTO_ORIGINAL_PREPARE = base._prepare
_BASE_PREPARE = base._FINDUPTO_ORIGINAL_PREPARE


def _prepare(profile, username, password, work, openvpn_version=(0, 0, 0), route_method="exe") -> Path:
    config = _BASE_PREPARE(profile, username, password, work, openvpn_version)
    path = Path(config)
    lines = path.read_text(encoding="utf-8").splitlines()
    filtered = []
    cipher_line = None
    has_cert_verification = False
    for line in lines:
        low = line.strip().lower()
        if low.startswith(("route 0.0.0.0 128.0.0.0", "route 128.0.0.0 128.0.0.0", "redirect-gateway ", "route-method ")):
            continue
        if low.startswith(("remote-cert-tls ", "verify-x509-name ", "peer-fingerprint ")):
            has_cert_verification = True
        if low.startswith("data-ciphers "):
            cipher_line = line
        if low.startswith("data-ciphers-fallback "):
            continue
        filtered.append(line)
    filtered.extend([
        'pull-filter ignore "redirect-gateway"',
        'pull-filter ignore "redirect-private"',
        "redirect-gateway def1 bypass-dhcp bypass-dns",
        "route-metric 5",
        *([f"route-method {route_method}"] if os.name == "nt" and route_method else []),
        "route-delay 2 30",
        "show-net-up",
        "disable-dco",
    ])
    if not has_cert_verification:
        filtered.append("remote-cert-tls server")
    if cipher_line is None:
        filtered.append("data-ciphers AES-256-GCM:AES-128-GCM:CHACHA20-POLY1305:AES-256-CBC")
    filtered.append("data-ciphers-fallback AES-256-CBC")
    path.write_text("\n".join(filtered) + "\n", encoding="utf-8")
    return path


base.route_snapshot = route_snapshot
base._prepare = _prepare

_DIRECT_SSL = ssl.create_default_context()
_DIRECT_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=_DIRECT_SSL))


def public_ip(timeout: float = 8):
    """Get public IP without inheriting a system HTTP proxy."""
    for url in ("https://api.ipify.org", "https://ifconfig.me/ip", "https://icanhazip.com"):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": base.UA, "Accept": "text/plain", "Connection": "close"})
            with _DIRECT_OPENER.open(request, timeout=min(max(4.0, timeout), 15)) as response:
                value = response.read(256).decode("ascii", "ignore").strip()
            if re.fullmatch(r"(?:\d{1,3}\.){3}\d{1,3}", value) or ":" in value:
                log(f"PUBLIC IP DIRECT url={url} public_ip={value}")
                return value
        except Exception as exc:
            log(f"PUBLIC IP DIRECT FAIL url={url} error={type(exc).__name__}: {exc}")
    raise RuntimeError("Unable to determine public IP without proxy")


def verify_tunnel(previous_ip: str | None = None, timeout: float = 8):
    """Verify IP change while tolerating a transient Windows route-table race."""
    snapshot = ""
    if os.name == "nt":
        deadline = time.monotonic() + min(8.0, max(3.0, timeout))
        while time.monotonic() < deadline:
            snapshot = route_snapshot()
            if full_tunnel_routes(snapshot):
                break
            time.sleep(0.25)
    ip = public_ip(timeout)
    if previous_ip and ip == previous_ip:
        raise RuntimeError(f"VPN initialized but public IP did not change ({ip}); traffic is not using the VPN)")
    if os.name == "nt" and not full_tunnel_routes(snapshot):
        log(f"TUNNEL ROUTE SNAPSHOT TRANSIENTLY MISSING public_ip={ip} snapshot={snapshot or 'empty'}")
    log(f"TUNNEL VERIFIED public_ip={ip} previous_ip={previous_ip or 'unknown'} routes={snapshot or 'non-Windows'}")
    return ip


def connect(*args, **kwargs):
    return base.connect(*args, **kwargs)


def discover(deadline: float = 10):
    """Fast discovery using VPNBook and the validated local cache."""
    started = time.monotonic()
    merged = {s["id"]: s for s in base._cache_load()}
    try:
        for server in base.vpnbook_servers():
            if base._is_real_server(server):
                merged[server["id"]] = server
    except Exception as exc:
        log(f"DISCOVERY VPNBOOK FAIL error={type(exc).__name__}: {exc}")
    data = sorted(merged.values(), key=lambda s: (s.get("rank", -999), -s.get("ping", 9999)), reverse=True)[:base.MAX_DISCOVERY]
    base._cache_save(data)
    log(f"DISCOVERY READY candidates={len(data)} elapsed={time.monotonic()-started:.2f}s")
    return data


for _name in ("parse_gate", "vpnbook_servers_from_html", "vpnbook_servers", "_is_real_server"):
    globals()[_name] = getattr(base, _name)
