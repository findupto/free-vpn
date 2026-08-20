from __future__ import annotations

"""Compatibility facade for the Findupto VPN engine."""

import os
import subprocess
import time

import vpn_engine as base

APP_VERSION = getattr(base, "APP_VERSION", "13.1.5")
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


def route_snapshot():
    """Find OpenVPN /1 routes without depending on localized column spacing."""
    lines = _route_lines()
    hits = [
        line for line in lines
        if line.startswith("0.0.0.0 128.0.0.0")
        or line.startswith("128.0.0.0 128.0.0.0")
    ]
    if hits:
        return " | ".join(hits[-8:])

    if os.name == "nt":
        try:
            command = (
                "Get-NetRoute -AddressFamily IPv4 -ErrorAction SilentlyContinue "
                "| Where-Object { $_.DestinationPrefix -eq '0.0.0.0/1' -or "
                "$_.DestinationPrefix -eq '128.0.0.0/1' } "
                "| ForEach-Object { $_.DestinationPrefix + ' ' + $_.NextHop + ' ' + $_.InterfaceIndex }"
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
            if ps_hits:
                return " | ".join(ps_hits[-8:])
        except Exception as exc:
            log(f"POWERSHELL ROUTE SNAPSHOT FAIL error={type(exc).__name__}: {exc}")

    # OpenVPN has already reported Initialization Sequence Completed at this
    # point. Windows can occasionally hide the /1 routes from both route.exe
    # and Get-NetRoute. Returning a non-empty marker lets the subsequent public
    # IP verification decide whether traffic really crossed the VPN.
    return "OpenVPN initialized; Windows route table unavailable"


# base.connect() resolves route_snapshot in vpn_engine's own global namespace.
base.route_snapshot = route_snapshot


def verify_tunnel(previous_ip: str | None = None, timeout: float = 8):
    """Verify traffic by checking the public IP after OpenVPN initialization."""
    snapshot = route_snapshot()
    ip = base.public_ip(timeout)
    if previous_ip and ip == previous_ip:
        raise RuntimeError(
            f"VPN initialized but public IP did not change ({ip}); traffic is not using the VPN"
        )
    log(
        f"TUNNEL VERIFIED public_ip={ip} previous_ip={previous_ip or 'unknown'} "
        f"routes={snapshot}"
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


def _prepare(*args, **kwargs):
    return base._prepare(*args, **kwargs)


# Export optional API names without eager getattr() evaluation.
for _name in (
    "parse_gate",
    "vpnbook_servers_from_html",
    "vpnbook_servers",
    "public_ip",
    "full_tunnel_routes",
    "_is_real_server",
):
    if _name not in globals() and hasattr(base, _name):
        globals()[_name] = getattr(base, _name)
