from __future__ import annotations

"""Windows-facing hardening and fast-fail connection facade."""

import os
import re
import ssl
import socket
import struct
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

import vpn_engine as base

APP_VERSION = "13.2.2"
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
        cp = subprocess.run(["route", "print", "-4"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=3, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
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
    """Read Windows /1 routes with a PowerShell fallback."""
    if os.name != "nt":
        return ""
    hits = [line for line in _route_lines() if line.startswith("0.0.0.0 128.0.0.0") or line.startswith("128.0.0.0 128.0.0.0")]
    prefixes = {line.split()[0] for line in hits if line.split()}
    if {"0.0.0.0", "128.0.0.0"}.issubset(prefixes):
        return " | ".join(hits)
    try:
        command = (
            "Get-NetRoute -AddressFamily IPv4 -ErrorAction SilentlyContinue "
            "| Where-Object { $_.DestinationPrefix -eq '0.0.0.0/1' -or "
            "$_.DestinationPrefix -eq '128.0.0.0/1' } "
            "| ForEach-Object { $_.DestinationPrefix + ' ' + $_.NextHop + ' ' + "
            "$_.InterfaceIndex + ' ' + $_.RouteMetric }"
        )
        cp = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", command], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=3, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        ps_hits = [" ".join(x.strip().split()) for x in cp.stdout.splitlines() if "/1" in x]
        if {"0.0.0.0/1", "128.0.0.0/1"}.issubset({x.split()[0] for x in ps_hits if x.split()}):
            return " | ".join(ps_hits)
    except Exception as exc:
        log(f"POWERSHELL ROUTE SNAPSHOT FAIL error={type(exc).__name__}: {exc}")
    return ""


if not hasattr(base, "_FINDUPTO_ORIGINAL_PREPARE"):
    base._FINDUPTO_ORIGINAL_PREPARE = base._prepare
_BASE_PREPARE = base._FINDUPTO_ORIGINAL_PREPARE


def _prepare(profile, username, password, work, openvpn_version=(0, 0, 0), route_method="adaptive") -> Path:
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
        "route-metric 1",
        *([f"route-method {route_method}"] if os.name == "nt" and route_method else []),
        "route-delay 1 8",
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

_BASE_PROFILES = base._profiles
_VPNBOOK_METHODS = (
    ("tcp", "443", "tcp-client"),
    ("tcp", "80", "tcp-client"),
    ("udp", "53", "udp"),
    ("udp", "25000", "udp"),
)


def _vpnbook_method_variants(profile: str) -> list[str]:
    lines = profile.splitlines()
    remote_indexes = [i for i, line in enumerate(lines) if line.strip().lower().startswith("remote ")]
    if not remote_indexes:
        return [profile]
    variants = []
    for proto, port, proto_arg in _VPNBOOK_METHODS:
        variant = list(lines)
        index = remote_indexes[0]
        fields = variant[index].split()
        if len(fields) < 2:
            continue
        host = fields[1]
        variant[index] = f"remote {host} {port} {proto_arg}"
        for i, line in enumerate(variant):
            if line.strip().lower().startswith("proto "):
                variant[i] = f"proto {proto}"
        variants.append("\n".join(variant))
    return variants or [profile]


def _gate_variants(profile: str) -> list[str]:
    """Create one profile per remote endpoint while preserving all other settings."""
    lines = profile.splitlines()
    remotes = [i for i, line in enumerate(lines) if line.strip().lower().startswith("remote ")]
    if len(remotes) <= 1:
        return [profile]
    variants = []
    for selected in remotes:
        variant = []
        for i, line in enumerate(lines):
            if i in remotes and i != selected:
                continue
            variant.append(line)
        variants.append("\n".join(variant))
    return variants


def _multi_profiles(server: dict) -> tuple[list[str], str, str]:
    profiles, username, password = _BASE_PROFILES(server)
    expanded = []
    seen = set()
    for profile in profiles:
        variants = _vpnbook_method_variants(profile) if server.get("kind") == "book" else _gate_variants(profile)
        for variant in variants:
            key = variant.strip()
            if key and key not in seen:
                seen.add(key)
                expanded.append(variant)
    if server.get("kind") == "book":
        log(f"VPNBOOK METHODS expanded={len(expanded)} methods=TCP/443,TCP/80,UDP/53,UDP/25000")
    else:
        log(f"VPNGATE REMOTE FALLBACK variants={len(expanded)}")
    return expanded, username, password


base._profiles = _multi_profiles

_DIRECT_SSL = ssl.create_default_context()
_DIRECT_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=_DIRECT_SSL))


def _dns_a_records(hostname: str, timeout: float = 3.0) -> list[str]:
    """Resolve an A record without using the Windows resolver."""
    transaction_id = os.urandom(2)
    name = hostname.rstrip(".")
    qname = b"".join(bytes([len(part)]) + part.encode("ascii") for part in name.split(".")) + b"\x00"
    query = transaction_id + b"\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00" + qname + b"\x00\x01\x00\x01"
    for resolver in ("1.1.1.1", "8.8.8.8"):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.settimeout(timeout)
                sock.sendto(query, (resolver, 53))
                packet, _ = sock.recvfrom(4096)
            if packet[:2] != transaction_id or len(packet) < 12:
                continue
            flags, qdcount, ancount = struct.unpack("!HHHH", packet[2:10])
            if not (flags & 0x8000) or not ancount:
                continue
            offset = 12
            for _ in range(qdcount):
                while offset < len(packet) and packet[offset] != 0:
                    offset += packet[offset] + 1
                offset += 5
            answers = []
            for _ in range(ancount):
                if offset + 12 > len(packet):
                    break
                if packet[offset] & 0xC0 == 0xC0:
                    offset += 2
                else:
                    while offset < len(packet) and packet[offset] != 0:
                        offset += packet[offset] + 1
                    offset += 1
                rtype, rclass, ttl, rdlength = struct.unpack("!HHIH", packet[offset:offset + 10])
                offset += 10
                rdata = packet[offset:offset + rdlength]
                offset += rdlength
                if rtype == 1 and rclass == 1 and rdlength == 4:
                    answers.append(socket.inet_ntoa(rdata))
            if answers:
                return answers
        except OSError as exc:
            log(f"DIRECT DNS FAIL host={hostname} resolver={resolver} error={type(exc).__name__}: {exc}")
    return []


_DOH_SSL = {
    "1.1.1.1": ("cloudflare-dns.com", "/dns-query"),
    "8.8.8.8": ("dns.google", "/dns-query"),
}


def _dns_a_records_doh(hostname: str, timeout: float = 4.0) -> list[str]:
    """Resolve A records through DNS-over-HTTPS using fixed resolver IPs."""
    name = hostname.rstrip(".")
    for resolver, (sni, path) in _DOH_SSL.items():
        try:
            query = urllib.parse.quote(name, safe="")
            url = f"https://{resolver}{path}?name={query}&type=A"
            request = urllib.request.Request(
                url,
                headers={
                    "Host": sni,
                    "User-Agent": base.UA,
                    "Accept": "application/dns-json",
                },
            )
            context = ssl.create_default_context()
            with socket.create_connection((resolver, 443), timeout=timeout) as raw:
                with context.wrap_socket(raw, server_hostname=sni) as sock:
                    request_bytes = (
                        f"GET {path}?name={query}&type=A HTTP/1.1\r\n"
                        f"Host: {sni}\r\nUser-Agent: {base.UA}\r\nAccept: application/dns-json\r\n"
                        "Connection: close\r\n\r\n"
                    ).encode("ascii")
                    sock.sendall(request_bytes)
                    chunks = []
                    while True:
                        chunk = sock.recv(4096)
                        if not chunk:
                            break
                        chunks.append(chunk)
                        if sum(map(len, chunks)) > 65536:
                            break
            raw_response = b"".join(chunks)
            _, _, body = raw_response.partition(b"\r\n\r\n")
            payload = json.loads(body.decode("utf-8", "replace"))
            answers = []
            for answer in payload.get("Answer", []):
                if answer.get("type") == 1 and re.fullmatch(r"(?:\d{1,3}\.){3}\d{1,3}", str(answer.get("data", ""))):
                    answers.append(answer["data"])
            if answers:
                log(f"DIRECT DNS-HTTPS OK host={hostname} resolver={resolver} records={len(answers)}")
                return answers
        except Exception as exc:
            log(f"DIRECT DNS-HTTPS FAIL host={hostname} resolver={resolver} error={type(exc).__name__}: {exc}")
    return []


def _https_get_via_ip(hostname: str, ip: str, timeout: float = 5.0) -> str:
    """HTTPS request with DNS bypassed while retaining TLS SNI and Host."""
    with socket.create_connection((ip, 443), timeout=timeout) as raw_sock:
        with _DIRECT_SSL.wrap_socket(raw_sock, server_hostname=hostname) as sock:
            request = (
                f"GET / HTTP/1.1\r\nHost: {hostname}\r\n"
                f"User-Agent: {base.UA}\r\nAccept: text/plain\r\nConnection: close\r\n\r\n"
            ).encode("ascii")
            sock.sendall(request)
            chunks = []
            total = 0
            while total < 4096:
                chunk = sock.recv(min(1024, 4096 - total))
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
    response = b"".join(chunks)
    head, _, body = response.partition(b"\r\n\r\n")
    status = re.search(rb"^HTTP/\d(?:\.\d)?\s+(\d+)", head)
    if not status or status.group(1) not in {b"200", b"204"}:
        raise RuntimeError(f"HTTP status {status.group(1).decode() if status else 'unknown'}")
    return body.decode("ascii", "ignore").strip()


def _direct_public_ip_without_system_dns(timeout: float) -> str | None:
    for hostname in ("api.ipify.org", "ifconfig.me", "icanhazip.com"):
        addresses = _dns_a_records(hostname, min(2.5, max(1.0, timeout / 2)))
        if not addresses:
            addresses = _dns_a_records_doh(hostname, min(4.0, max(2.0, timeout)))
        for ip in addresses:
            try:
                value = _https_get_via_ip(hostname, ip, min(5.0, max(2.0, timeout)))
                if re.fullmatch(r"(?:\d{1,3}\.){3}\d{1,3}", value) or ":" in value:
                    log(f"PUBLIC IP DIRECT DNS-BYPASS host={hostname} ip={ip} public_ip={value}")
                    return value
            except Exception as exc:
                log(f"PUBLIC IP DNS-BYPASS FAIL host={hostname} ip={ip} error={type(exc).__name__}: {exc}")
    return None


def public_ip(timeout: float = 8):
    """Get public IP directly, bypassing configured HTTP proxies and Windows DNS."""
    errors = []
    for url in ("https://api.ipify.org", "https://ifconfig.me/ip", "https://icanhazip.com"):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": base.UA, "Accept": "text/plain", "Connection": "close"})
            with _DIRECT_OPENER.open(request, timeout=min(max(3.0, timeout), 10)) as response:
                value = response.read(256).decode("ascii", "ignore").strip()
            if re.fullmatch(r"(?:\d{1,3}\.){3}\d{1,3}", value) or ":" in value:
                log(f"PUBLIC IP DIRECT url={url} public_ip={value}")
                return value
        except Exception as exc:
            errors.append(f"{url}: {type(exc).__name__}: {exc}")
            log(f"PUBLIC IP DIRECT FAIL url={url} error={type(exc).__name__}: {exc}")
    fallback = _direct_public_ip_without_system_dns(timeout)
    if fallback:
        return fallback
    raise RuntimeError("Unable to determine public IP without proxy or system DNS: " + " | ".join(errors[-2:]))


def verify_tunnel(previous_ip: str | None = None, timeout: float = 8):
    snapshot = ""
    if os.name == "nt":
        deadline = time.monotonic() + min(6.0, max(2.0, timeout))
        while time.monotonic() < deadline:
            snapshot = route_snapshot()
            if full_tunnel_routes(snapshot):
                break
            time.sleep(0.2)
        if not full_tunnel_routes(snapshot):
            raise RuntimeError("VPN process connected, but both full-tunnel Windows /1 routes are missing")
    ip = public_ip(timeout)
    if previous_ip and ip == previous_ip:
        raise RuntimeError(f"VPN initialized but public IP did not change ({ip}); traffic is not using the VPN")
    log(f"TUNNEL VERIFIED public_ip={ip} previous_ip={previous_ip or 'unknown'} routes={snapshot or 'non-Windows'}")
    return ip


def _read_log(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
    except OSError:
        return ""


def _kill(process, timeout=2.0):
    if process is None:
        return
    try:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=timeout)
    except Exception:
        try:
            process.kill()
            process.wait(timeout=1)
        except Exception:
            pass


def _attempt_timeout(profile: str) -> float:
    """Short timeout for dead transports, slightly longer for TLS/auth startup."""
    low = profile.lower()
    if "proto udp" in low:
        return 8.0
    if "remote " in low:
        return 9.0
    return 8.0


def _fast_connect(server: dict, total_deadline: float):
    if not base._is_real_server(server):
        raise RuntimeError("invalid server entry")
    exe = openvpn_exe()
    if not exe:
        raise RuntimeError("OpenVPN Community is not installed")
    version = base._openvpn_version(exe)
    started = time.monotonic()
    profiles, username, password = base._profiles(server)
    log(f"FAST FAILOVER PLAN server={server['host']} attempts={len(profiles)} deadline={total_deadline:.1f}s")
    last = "all connection methods failed"
    for index, profile in enumerate(profiles, 1):
        remaining = total_deadline - (time.monotonic() - started)
        if remaining <= 0.2:
            break
        work = Path(tempfile.mkdtemp(prefix="findupto-vpn-"))
        process = None
        logfile = work / "openvpn.log"
        try:
            config = _prepare(profile, username, password, work, version)
            timeout = min(_attempt_timeout(profile), max(2.0, remaining - 0.5))
            process = subprocess.Popen(
                [exe, "--config", str(config), "--log", str(logfile)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            log(f"OPENVPN START server={server['host']} profile={index}/{len(profiles)} pid={process.pid} timeout={timeout:.1f}s")
            deadline = time.monotonic() + timeout
            initialized = False
            while time.monotonic() < deadline:
                text = _read_log(logfile)
                if "Initialization Sequence Completed" in text:
                    initialized = True
                    break
                if process.poll() is not None:
                    last = base._classify(text, process.returncode)
                    break
                time.sleep(0.15)
            if not initialized:
                if process.poll() is None:
                    last = "transport startup timeout"
                text = _read_log(logfile)
                if text:
                    classified = base._classify(text, process.returncode if process.poll() is not None else None)
                    if classified != "connection timeout":
                        last = classified
                log(f"OPENVPN ATTEMPT FAIL server={server['host']} profile={index}/{len(profiles)} reason={last}; trying next method")
                _kill(process)
                process = None
                import shutil
                shutil.rmtree(work, ignore_errors=True)
                continue
            snapshot = route_snapshot()
            if os.name == "nt" and not full_tunnel_routes(snapshot):
                route_deadline = time.monotonic() + min(3.0, max(1.0, deadline - time.monotonic()))
                while time.monotonic() < route_deadline and not full_tunnel_routes(snapshot):
                    time.sleep(0.15)
                    snapshot = route_snapshot()
                if not full_tunnel_routes(snapshot):
                    raise RuntimeError("initialization completed but full-tunnel routes were not installed")
            log(f"OPENVPN INITIALIZED server={server['host']} profile={index} routes={snapshot or 'non-Windows'}")
            return process, work, logfile
        except Exception as exc:
            last = str(exc)
            text = _read_log(logfile)
            if text:
                base._write_failure_log(server, text)
            log(f"OPENVPN ATTEMPT EXCEPTION server={server['host']} profile={index}/{len(profiles)} error={type(exc).__name__}: {exc}; trying next method")
            _kill(process)
            process = None
            import shutil
            shutil.rmtree(work, ignore_errors=True)
        finally:
            if process is None:
                import shutil
                shutil.rmtree(work, ignore_errors=True)
    raise RuntimeError(last)


def connect(server, total_deadline: float = 60):
    # GUI historically supplied 45s per server. Cap it so a dead public server
    # cannot monopolize the entire candidate queue.
    return _fast_connect(server, min(float(total_deadline), 30.0))


def discover(deadline: float = 10):
    return base.discover(deadline)


for _name in ("parse_gate", "vpnbook_servers_from_html", "vpnbook_servers", "_is_real_server"):
    globals()[_name] = getattr(base, _name)
