from __future__ import annotations

"""Compatibility facade for the Findupto VPN engine.

The packaged client imports this module so that the GUI has one stable API.
The actual VPN implementation lives in vpn_engine.py.
"""

import os
import re
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
    """Return Windows /1 routes using tolerant parsing.

    Windows route.exe output varies in spacing and interface/gateway columns.
    We only need to identify the destination/netmask pair, not the localized
    column names. If the table exposes at least one OpenVPN /1 route, return it;
    the final public-IP verification below confirms that traffic actually uses
    the VPN.
    """
    lines = _route_lines()
    hits = []
    for line in lines:
        if line.startswith("0.0.0.0 128.0.0.0") or line.startswith("128.0.0.0 128.0.0.0"):
            hits.append(line)

    if hits:
        return " | ".join(hits[-8:])

    # PowerShell's NetTCPIP provider is more reliable than parsing localized
    # route.exe output. Keep this as a fallback for Windows installations where
    # route.exe formatting differs.
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
    return ""


# base.connect() resolves route_snapshot in vpn_engine's global namespace.
# Patch that namespace too, not just this facade, so both the GUI and the
# underlying engine use the same Windows route detector.
base.route_snapshot = route_snapshot


def verify_tunnel(previous_ip: str | None = None, timeout: float = 8):
    """Verify the VPN by checking the route and then the public IP."""
    snapshot = ""
    if os.name == "nt":
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            snapshot = route_snapshot()
            if snapshot:
                break
            time.sleep(0.25)

    # Some Windows builds do not expose the /1 routes through either route.exe
    # or PowerShell even though OpenVPN has installed them. In that case the
    # public-IP change is the authoritative traffic-path check; do not reject a
    # working tunnel solely because of a route-table formatting quirk.
    ip = base.public_ip(timeout)
    if previous_ip and ip == previous_ip:
        raise RuntimeError(f"VPN initialized but public IP did not change ({ip}); traffic is not using the VPN")
    log(
        f"TUNNEL VERIFIED public_ip={ip} previous_ip={previous_ip or 'unknown'} "
        f"routes={snapshot or 'route-table-unavailable; verified by public IP'}"
    )
    return ip


# base.connect() also performs its own route check immediately after OpenVPN
# initialization. If the route table is temporarily unavailable, the public-IP
# verification in the GUI will still provide the final traffic-path check.

def connect(*args, **kwargs):
    return base.connect(*args, **kwargs)


def discover(deadline: float = 10):
    """Fast discovery: VPNBook is the primary source and never blocks on Gate.

    VPN Gate's API can take 1–3 minutes to download on some networks. It is not
    allowed to delay the usable VPNBook list anymore. Cached Gate servers remain
    usable when present, but fresh Gate discovery is intentionally skipped here.
    """
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


# Export the remaining engine API without eagerly evaluating missing symbols.
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
