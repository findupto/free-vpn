"""Network diagnostics used to verify VPN state without storing traffic data."""

from __future__ import annotations

import ipaddress
import socket
import urllib.request
from typing import Iterable

PUBLIC_IP_ENDPOINTS = (
    "https://api.ipify.org",
    "https://ifconfig.me/ip",
)


def fetch_public_ip(timeout: float = 5.0, endpoints: Iterable[str] = PUBLIC_IP_ENDPOINTS) -> str | None:
    for url in endpoints:
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "FinduptoVPN/14.0.0", "Accept": "text/plain"})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                value = response.read(128).decode("ascii", "ignore").strip()
            address = ipaddress.ip_address(value)
            if address.is_global:
                return str(address)
        except (OSError, ValueError):
            continue
    return None


def ipv6_connectivity(timeout: float = 2.0) -> bool:
    try:
        infos = socket.getaddrinfo("ipv6.google.com", 443, socket.AF_INET6, socket.SOCK_STREAM)
    except OSError:
        return False
    for family, socktype, proto, _, address in infos:
        sock = socket.socket(family, socktype, proto)
        try:
            sock.settimeout(timeout)
            sock.connect(address)
            return True
        except OSError:
            continue
        finally:
            sock.close()
    return False


def public_ip_changed(before: str | None, after: str | None) -> bool:
    return bool(before and after and before != after)
