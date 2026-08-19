from __future__ import annotations

import base64
import csv
import gzip
import html
import io
import json
import os
import re
import shutil
import socket
import ssl
import subprocess
import tempfile
import threading
import time
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

APP_VERSION = "12.0.1"
ROOT = Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir())) / "FinduptoVPN"
LOG = ROOT / "diagnostic.log"
PROFILE_LOGS = ROOT / "openvpn-logs"
CACHE = ROOT / "servers.json"
UA = f"FinduptoVPN/{APP_VERSION}"
GATE_URLS = ("https://www.vpngate.net/api/iphone/", "https://download.vpngate.jp/api/iphone/")
VPNBOOK_PAGE = "https://www.vpnbook.com/freevpn/openvpn"
VPNBOOK_BASE = "https://www.vpnbook.com/free-openvpn-account/"
CACHE_TTL = 30 * 60
MAX_DISCOVERY = 250
_lock = threading.Lock()


def log(msg: str) -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    with _lock:
        with LOG.open("a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")


def _curl() -> str | None:
    for name in ("curl.exe", "curl"):
        found = shutil.which(name)
        if found:
            return found
    return None


def http_get(url: str, timeout: float = 12, limit: int = 10_000_000) -> bytes:
    """Fetch without --compressed: some Windows curl builds advertise curl but do not implement it."""
    started = time.monotonic()
    curl = _curl()
    if curl:
        cmd = [curl, "--fail", "--silent", "--show-error", "--location", "--connect-timeout", str(max(2, int(timeout * 0.4))), "--max-time", str(max(3, int(timeout))), "-A", UA, url]
        try:
            cp = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout + 2, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if cp.returncode:
                raise RuntimeError(f"curl exit {cp.returncode}: {cp.stderr.decode('utf-8', 'replace')[-500:]}")
            data = cp.stdout
            if len(data) > limit:
                raise RuntimeError("response too large")
            log(f"HTTP OK method=curl url={url} bytes={len(data)} elapsed={time.monotonic()-started:.2f}s")
            return data
        except Exception as exc:
            log(f"HTTP CURL FAIL url={url} error={type(exc).__name__}: {exc}; falling back to urllib")
    request = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*", "Connection": "close"})
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


def _valid_ip(value: str) -> bool:
    try:
        socket.inet_aton(value)
        return all(0 <= int(part) <= 255 for part in value.split("."))
    except (OSError, ValueError):
        return False


def _resolve_host(host: str) -> str:
    try:
        return socket.gethostbyname(host)
    except OSError:
        return ""


def parse_gate(raw: bytes) -> list[dict]:
    text = raw.decode("utf-8-sig", "replace").replace("\r", "")
    lines = text.split("\n")
    header_line = next((line for line in lines if line.startswith("#HostName,")), None)
    if not header_line:
        raise RuntimeError("VPN Gate CSV header missing")
    fields = next(csv.reader([header_line[1:]]))
    result = []
    for line in lines:
        if not line or line.startswith("#"):
            continue
        try:
            row = next(csv.reader([line]))
        except Exception:
            continue
        if len(row) < len(fields):
            continue
        item = dict(zip(fields, row))
        ip, host, config = (item.get("IP") or "").strip(), (item.get("HostName") or "").strip(), (item.get("OpenVPN_ConfigData_Base64") or "").strip()
        if not ip or not host or not config or not _valid_ip(ip):
            continue
        def num(name, default):
            try:
                return float(item.get(name) or default)
            except ValueError:
                return float(default)
        ping, speed, uptime, score = num("Ping", 9999), num("Speed", 0) / 1_000_000, num("Uptime", 0) / 86400, num("Score", 0)
        rank = speed * 8 + min(uptime, 100) * 0.08 + score * 0.01 - min(ping, 2000) * 0.35
        result.append({"id": f"gate:{ip}:{host}", "ip": ip, "host": host, "country": item.get("CountryLong") or item.get("CountryShort") or "Unknown", "city": item.get("City") or "Unknown", "ping": ping, "speed": speed, "uptime": uptime, "score": score, "rank": rank, "config": config, "source": "VPN Gate", "kind": "gate"})
    return sorted(result, key=lambda s: s["rank"], reverse=True)


def vpnbook_servers_from_html(raw: str) -> list[dict]:
    result, seen = [], set()
    patterns = (r'href=["\']([^"\']*vpnbook-openvpn-([a-z]{2}\d{2,4})\.zip)["\']', r'\b(vpnbook-openvpn-([a-z]{2}\d{2,4})\.zip)\b')
    for pattern in patterns:
        for match in re.finditer(pattern, raw, re.I):
            href, sid_raw = match.group(1), match.group(2)
            sid = sid_raw.lower()
            if sid in seen:
                continue
            seen.add(sid)
            filename = f"vpnbook-openvpn-{sid}.zip"
            bundle = href if href.lower().startswith("http") else VPNBOOK_BASE + filename
            host = f"{sid}.vpnbook.com"
            result.append({"id": f"book:{sid}", "sid": sid, "ip": _resolve_host(host), "host": host, "country": "VPNBook", "city": sid.upper(), "ping": 9999, "speed": 0, "rank": -100, "bundle": bundle, "source": "VPNBook", "kind": "book"})
    return result


def vpnbook_servers() -> list[dict]:
    try:
        raw = http_get(VPNBOOK_PAGE, 8, 5_000_000).decode("utf-8", "replace")
        found = vpnbook_servers_from_html(raw)
        log(f"VPNBOOK CATALOG OK servers={len(found)}")
        return found
    except Exception as exc:
        log(f"VPNBOOK CATALOG FAIL error={type(exc).__name__}: {exc}")
        return []


def _is_real_server(server: dict) -> bool:
    kind, host = server.get("kind"), str(server.get("host") or "")
    if kind == "gate":
        return str(server.get("id", "")).startswith("gate:") and _valid_ip(str(server.get("ip") or "")) and bool(host) and bool(server.get("config"))
    if kind == "book":
        bundle = str(server.get("bundle") or "")
        return str(server.get("id", "")).startswith("book:") and re.fullmatch(r"[a-z]{2}\d{2,4}\.vpnbook\.com", host, re.I) is not None and bundle.startswith(VPNBOOK_BASE)
    return False


def _cache_load() -> list[dict]:
    try:
        data = json.loads(CACHE.read_text(encoding="utf-8"))
        if time.time() - float(data.get("time", 0)) < CACHE_TTL:
            raw_servers = data.get("servers", [])
            servers = [s for s in raw_servers if isinstance(s, dict) and _is_real_server(s)]
            dropped = len(raw_servers) - len(servers)
            if dropped:
                log(f"CACHE CLEANUP removed={dropped} invalid-or-planted entries")
            return servers
    except Exception as exc:
        if CACHE.exists():
            log(f"CACHE LOAD FAIL error={type(exc).__name__}: {exc}")
    return []


def _cache_save(servers: list[dict]) -> None:
    try:
        ROOT.mkdir(parents=True, exist_ok=True)
        clean = [s for s in servers if _is_real_server(s)]
        tmp = CACHE.with_suffix(".tmp")
        tmp.write_text(json.dumps({"time": time.time(), "servers": clean}, separators=(",", ":")), encoding="utf-8")
        tmp.replace(CACHE)
    except Exception as exc:
        log(f"CACHE SAVE FAIL error={type(exc).__name__}: {exc}")


def _discover_source(url: str, timeout: float, limit: int):
    try:
        return url, http_get(url, timeout, limit), None
    except Exception as exc:
        return url, None, exc


def discover(deadline: float = 12) -> list[dict]:
    started = time.monotonic()
    merged = {server["id"]: server for server in _cache_load()}
    log(f"DISCOVERY START cached={len(merged)} deadline={deadline:.1f}s")
    urls = [(url, min(deadline, 8), 8_000_000) for url in GATE_URLS] + [(VPNBOOK_PAGE, min(deadline, 8), 5_000_000)]
    executor = ThreadPoolExecutor(max_workers=len(urls), thread_name_prefix="vpn-discovery")
    futures = [executor.submit(_discover_source, *item) for item in urls]
    try:
        for future in as_completed(futures, timeout=max(0.1, deadline)):
            url, raw, error = future.result()
            if error:
                log(f"DISCOVERY SOURCE FAIL url={url} error={type(error).__name__}: {error}")
                continue
            try:
                parsed = vpnbook_servers_from_html(raw.decode("utf-8", "replace")) if raw.lstrip().startswith(b"<") else parse_gate(raw)
                for server in parsed:
                    if _is_real_server(server):
                        merged[server["id"]] = server
                log(f"DISCOVERY SOURCE OK url={url} servers={len(parsed)}")
            except Exception as exc:
                log(f"DISCOVERY PARSE FAIL url={url} error={type(exc).__name__}: {exc}")
    except TimeoutError:
        unfinished = sum(not f.done() for f in futures)
        log(f"DISCOVERY DEADLINE reached unfinished={unfinished}; using completed sources and cache")
    finally:
        for future in futures:
            if not future.done():
                future.cancel()
        executor.shutdown(wait=False, cancel_futures=True)
    data = sorted(merged.values(), key=lambda s: (s.get("rank", -999), -s.get("ping", 9999)), reverse=True)[:MAX_DISCOVERY]
    _cache_save(data)
    log(f"DISCOVERY READY candidates={len(data)} elapsed={time.monotonic()-started:.2f}s")
    return data


def openvpn_exe() -> str | None:
    candidates = [shutil.which("openvpn.exe"), shutil.which("openvpn"), r"C:\Program Files\OpenVPN\bin\openvpn.exe", r"C:\Program Files (x86)\OpenVPN\bin\openvpn.exe"]
    for path in candidates:
        if path and os.path.isfile(path) and path.lower().endswith("openvpn.exe"):
            return path
    return None


def _openvpn_version(exe: str) -> tuple[int, int, int]:
    try:
        cp = subprocess.run([exe, "--version"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=5, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        match = re.search(r"OpenVPN\s+(\d+)\.(\d+)(?:\.(\d+))?", cp.stdout)
        if match:
            return tuple(int(match.group(i) or 0) for i in (1, 2, 3))
    except Exception as exc:
        log(f"OPENVPN VERSION FAIL error={type(exc).__name__}: {exc}")
    return (0, 0, 0)


def _vpnbook_profiles(server: dict) -> list[str]:
    raw = http_get(server["bundle"], 10, 8_000_000)
    if not raw.startswith(b"PK"):
        raise RuntimeError(f"VPNBook returned invalid configuration bundle ({len(raw)} bytes)")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = [n for n in archive.namelist() if n.lower().endswith(".ovpn")]
        if not names:
            raise RuntimeError("VPNBook bundle contains no OpenVPN profiles")
        order = ("tcp443", "tcp80", "udp53", "udp25000")
        names.sort(key=lambda n: next((i for i, token in enumerate(order) if token in n.lower()), 99))
        return [archive.read(n).decode("utf-8-sig", "replace") for n in names]


def _vpnbook_password() -> str:
    raw = http_get(VPNBOOK_PAGE, 8, 5_000_000).decode("utf-8", "replace")
    text = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", raw)))
    match = re.search(r"\bPassword\s*[:\-]?\s*([A-Za-z0-9]{6,32})\b", text, re.I)
    if not match:
        raise RuntimeError("VPNBook current password was not found on its official page")
    value = match.group(1)
    if value.lower() in {"password", "username", "updated", "vpnbook", "credentials", "service"}:
        raise RuntimeError("VPNBook page did not expose a valid current password")
    log(f"VPNBOOK AUTH source=official-page length={len(value)}")
    return value


def _profiles(server: dict) -> tuple[list[str], str, str]:
    if server["kind"] == "gate":
        config = base64.b64decode(server["config"] + "===").decode("utf-8-sig", "replace")
        return [config], "vpn", "vpn"
    return _vpnbook_profiles(server), "vpnbook", _vpnbook_password()


def _ovpn_path(path: Path) -> str:
    return path.resolve().as_posix()


def _prepare(profile: str, username: str, password: str, work: Path, openvpn_version=(0, 0, 0)) -> Path:
    auth = work / "auth.txt"
    auth.write_text(username + "\n" + password + "\n", encoding="utf-8")
    lines, legacy_cipher = [], None
    has_compression, has_dev = False, False
    for original in profile.splitlines():
        stripped, low = original.strip(), original.strip().lower()
        if not stripped or low.startswith(("#", ";")):
            lines.append(original)
            continue
        if low.startswith("cipher "):
            legacy_cipher = stripped.split(None, 1)[1].strip()
        if low.startswith("compress ") or low.startswith("comp-lzo"):
            has_compression = True
            continue
        if low.startswith("fast-io") or low.startswith("persist-key"):
            continue
        if low.startswith("dev "):
            has_dev = True
        if low.startswith(("auth-user-pass", "redirect-gateway", "route ", "route-ipv6 ", "route-nopull", "pull-filter", "register-dns", "block-outside-dns", "route-metric ")):
            continue
        lines.append(original)
    if not has_dev:
        lines.append("dev tun")
    lines.extend(["client", "redirect-gateway def1", "route 0.0.0.0 128.0.0.0", "route 128.0.0.0 128.0.0.0", "route-metric 5", f'auth-user-pass "{_ovpn_path(auth)}"', "auth-nocache", "resolv-retry infinite", "connect-retry 2 3", "connect-timeout 10", "persist-tun", "verb 3"])
    if openvpn_version >= (2, 6, 0):
        lines.append("disable-dco")
    if legacy_cipher:
        modern = "AES-256-GCM:AES-128-GCM:CHACHA20-POLY1305"
        if legacy_cipher.upper() not in modern.upper().split(":"):
            lines.append(f"data-ciphers {modern}:{legacy_cipher}")
            lines.append(f"data-ciphers-fallback {legacy_cipher}")
    if has_compression and openvpn_version >= (2, 6, 0):
        lines.extend(["allow-compression asym", "comp-lzo"])
    if os.name == "nt" and os.environ.get("FINDUPTO_BLOCK_OUTSIDE_DNS") == "1":
        lines.append("block-outside-dns")
    config = work / "client.ovpn"
    config.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return config


def _classify(text: str, code: int | None) -> str:
    low = text.lower()
    patterns = (("bad backslash", "OpenVPN configuration contains an invalid Windows backslash path"), ("options error", "OpenVPN configuration error"), ("unknown option", "OpenVPN does not support an option in this profile"), ("auth_failed", "authentication failed"), ("data channel cipher negotiation failed", "server cipher is incompatible"), ("tls error", "TLS handshake failed"), ("connection refused", "connection refused"), ("network is unreachable", "network unreachable"), ("cannot open tun", "TUN/TAP adapter unavailable"), ("all tap-windows adapters", "TUN/TAP adapter unavailable"), ("access is denied", "administrator permission required"), ("route addition failed", "Windows route installation failed"))
    for key, message in patterns:
        if key in low:
            return message
    return f"OpenVPN exited with code {code}" if code is not None else "connection timeout"


def route_snapshot() -> str:
    if os.name != "nt":
        return ""
    try:
        cp = subprocess.run(["route", "print", "-4"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=5, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        hits = [line.strip() for line in cp.stdout.splitlines() if re.search(r"(^|\s)(0\.0\.0\.0|128\.0\.0\.0)\s+128\.0\.0\.0\s", line)]
        return " | ".join(hits[-4:])
    except Exception as exc:
        log(f"ROUTE SNAPSHOT FAIL error={type(exc).__name__}: {exc}")
        return ""


def _read_log(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
    except OSError:
        return ""


def _write_failure_log(server: dict, text: str) -> None:
    PROFILE_LOGS.mkdir(parents=True, exist_ok=True)
    for old in PROFILE_LOGS.glob("*.log"):
        try:
            old.unlink()
        except OSError:
            pass
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", server.get("host", "server"))
    (PROFILE_LOGS / f"{safe}-last-failure.log").write_text(text[-100_000:], encoding="utf-8", errors="replace")


def connect(server: dict, total_deadline: float = 35):
    if not _is_real_server(server):
        raise RuntimeError("Refusing to connect to an invalid or non-discovered server entry")
    exe = openvpn_exe()
    if not exe:
        raise RuntimeError("OpenVPN Community is not installed. Install OpenVPN Community and retry.")
    version = _openvpn_version(exe)
    log(f"OPENVPN DETECTED exe={exe} version={'.'.join(map(str, version))}")
    started = time.monotonic()
    profiles, username, password = _profiles(server)
    last = ""
    for index, profile in enumerate(profiles, 1):
        if time.monotonic() - started >= total_deadline:
            break
        work = Path(tempfile.mkdtemp(prefix="findupto-vpn-"))
        process = None
        try:
            config = _prepare(profile, username, password, work, version)
            logfile = work / "openvpn.log"
            process = subprocess.Popen([exe, "--config", str(config), "--log", str(logfile)], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            log(f"OPENVPN START server={server['host']} profile={index}/{len(profiles)} pid={process.pid}")
            deadline = min(started + total_deadline, time.monotonic() + 12)
            while time.monotonic() < deadline:
                text = _read_log(logfile)
                if "Initialization Sequence Completed" in text:
                    snapshot = route_snapshot()
                    if os.name == "nt" and not snapshot:
                        last = "OpenVPN connected but full-tunnel Windows routes were not installed"
                        process.terminate()
                        try:
                            process.wait(timeout=3)
                        except Exception:
                            process.kill()
                        raise RuntimeError(last)
                    log(f"OPENVPN INITIALIZED server={server['host']} profile={index} routes={snapshot or 'non-Windows'}")
                    return process, work, logfile
                if process.poll() is not None:
                    last = _classify(text, process.returncode)
                    break
                time.sleep(0.2)
            if process and process.poll() is None:
                last = "connection timeout"
                process.terminate()
                try:
                    process.wait(timeout=3)
                except Exception:
                    process.kill()
            text = _read_log(logfile)
            if text:
                last = _classify(text, process.returncode if process else None)
            log(f"OPENVPN ATTEMPT FAIL server={server['host']} profile={index} reason={last}")
            _write_failure_log(server, text or last)
        except Exception as exc:
            last = str(exc)
            text = _read_log(work / "openvpn.log")
            if text:
                _write_failure_log(server, text)
            log(f"OPENVPN ATTEMPT EXCEPTION server={server['host']} profile={index} error={type(exc).__name__}: {exc}")
        finally:
            if process and process.poll() is None:
                try:
                    process.kill()
                except Exception:
                    pass
            shutil.rmtree(work, ignore_errors=True)
    raise RuntimeError(last or "all OpenVPN profiles failed; see the latest OpenVPN failure log")


def public_ip(timeout: float = 8) -> str:
    for url in ("https://api.ipify.org", "https://ifconfig.me/ip", "https://icanhazip.com"):
        try:
            value = http_get(url, timeout, 256).decode("ascii", "ignore").strip()
            if re.fullmatch(r"(?:\d{1,3}\.){3}\d{1,3}", value) or ":" in value:
                return value
        except Exception as exc:
            log(f"PUBLIC IP FAIL url={url} error={type(exc).__name__}: {exc}")
    raise RuntimeError("Unable to determine public IP")


def verify_tunnel(previous_ip: str | None = None, timeout: float = 8) -> str:
    snapshot = route_snapshot()
    if os.name == "nt" and not snapshot:
        raise RuntimeError("VPN process connected, but full-tunnel Windows routes are missing")
    ip = public_ip(timeout)
    if previous_ip and ip == previous_ip:
        raise RuntimeError(f"VPN initialized but public IP did not change ({ip}); traffic is not using the VPN)")
    log(f"TUNNEL VERIFIED public_ip={ip} previous_ip={previous_ip or 'unknown'}")
    return ip
