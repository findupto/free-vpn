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

ROOT = Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir())) / "FinduptoVPN"
LOG = ROOT / "diagnostic.log"
PROFILE_LOGS = ROOT / "openvpn-logs"
CACHE = ROOT / "servers.json"
UA = "FinduptoVPN/11.0"
GATE_URLS = ("https://www.vpngate.net/api/iphone/", "https://download.vpngate.jp/api/iphone/")
VPNBOOK_PAGE = "https://www.vpnbook.com/freevpn/openvpn"
CACHE_TTL = 30 * 60
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


def _curl_supports_compressed(curl: str) -> bool:
    try:
        cp = subprocess.run([curl, "--help"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, timeout=3, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return "--compressed" in cp.stdout
    except Exception:
        return False


def http_get(url: str, timeout: float = 12, limit: int = 10_000_000) -> bytes:
    started = time.monotonic()
    curl = _curl()
    if curl:
        cmd = [curl, "--fail", "--silent", "--show-error", "--location",
               "--connect-timeout", str(max(2, int(timeout * 0.4))),
               "--max-time", str(max(3, int(timeout))), "-A", UA, url]
        if _curl_supports_compressed(curl):
            cmd.insert(6, "--compressed")
        try:
            cp = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=timeout + 2,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
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
        with urllib.request.urlopen(request, timeout=min(timeout, 15), context=ssl.create_default_context()) as response:
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
        ip = (item.get("IP") or "").strip()
        host = (item.get("HostName") or "").strip()
        config = (item.get("OpenVPN_ConfigData_Base64") or "").strip()
        if not ip or not host or not config:
            continue
        try: ping = float(item.get("Ping") or 9999)
        except ValueError: ping = 9999
        try: speed = float(item.get("Speed") or 0) / 1_000_000
        except ValueError: speed = 0
        try: uptime = float(item.get("Uptime") or 0) / 86400
        except ValueError: uptime = 0
        try: score = float(item.get("Score") or 0)
        except ValueError: score = 0
        rank = speed * 8 + min(uptime, 100) * 0.08 + score * 0.01 - min(ping, 2000) * 0.35
        result.append({"id": f"gate:{ip}:{host}", "ip": ip, "host": host,
                       "country": item.get("CountryLong") or item.get("CountryShort") or "Unknown",
                       "city": item.get("City") or "Unknown", "ping": ping, "speed": speed,
                       "uptime": uptime, "score": score, "rank": rank, "config": config,
                       "source": "VPN Gate", "kind": "gate"})
    return sorted(result, key=lambda s: s["rank"], reverse=True)


def vpnbook_servers_from_html(raw: str) -> list[dict]:
    published = set(re.findall(r"\b([a-z]{2}\d{2,4})\.vpnbook\.com\b", raw, re.I))
    result = []
    for sid_raw in sorted(published):
        sid = sid_raw.lower()
        host = f"{sid}.vpnbook.com"
        result.append({"id": f"book:{sid}", "sid": sid, "ip": _resolve_host(host), "host": host,
                       "country": "VPNBook", "city": sid.upper(), "ping": 9999, "speed": 0,
                       "rank": -100, "bundle": f"https://www.vpnbook.com/free-openvpn-account/vpnbook-openvpn-{sid}.zip",
                       "source": "VPNBook", "kind": "book"})
    return result


def vpnbook_servers() -> list[dict]:
    try:
        raw = http_get(VPNBOOK_PAGE, 12, 5_000_000).decode("utf-8", "replace")
        found = vpnbook_servers_from_html(raw)
        log(f"VPNBOOK CATALOG OK servers={len(found)}")
        return found
    except Exception as exc:
        log(f"VPNBOOK CATALOG FAIL error={type(exc).__name__}: {exc}")
        return []


def _cache_load() -> list[dict]:
    try:
        data = json.loads(CACHE.read_text(encoding="utf-8"))
        if time.time() - float(data.get("time", 0)) < CACHE_TTL:
            return data.get("servers", [])
    except Exception:
        pass
    return []


def _cache_save(servers: list[dict]) -> None:
    try:
        ROOT.mkdir(parents=True, exist_ok=True)
        tmp = CACHE.with_suffix(".tmp")
        tmp.write_text(json.dumps({"time": time.time(), "servers": servers}, separators=(",", ":")), encoding="utf-8")
        tmp.replace(CACHE)
    except Exception as exc:
        log(f"CACHE SAVE FAIL error={type(exc).__name__}: {exc}")


def _discover_source(url: str, timeout: float, limit: int):
    try:
        raw = http_get(url, timeout, limit)
        return url, raw, None
    except Exception as exc:
        return url, None, exc


def discover(deadline: float = 12) -> list[dict]:
    started = time.monotonic()
    merged = {server["id"]: server for server in _cache_load()}
    log(f"DISCOVERY START cached={len(merged)} deadline={deadline:.1f}s")
    urls = [(url, min(deadline, 10), 8_000_000) for url in GATE_URLS]
    urls.append((VPNBOOK_PAGE, min(deadline, 10), 5_000_000))
    executor = ThreadPoolExecutor(max_workers=len(urls))
    futures = [executor.submit(_discover_source, *item) for item in urls]
    try:
        for future in as_completed(futures, timeout=max(0.1, deadline)):
            url, raw, error = future.result()
            if error:
                log(f"DISCOVERY SOURCE FAIL url={url} error={type(error).__name__}: {error}")
                continue
            try:
                if raw.lstrip().startswith(b"<"):
                    parsed = vpnbook_servers_from_html(raw.decode("utf-8", "replace"))
                else:
                    parsed = parse_gate(raw)
                for server in parsed:
                    merged[server["id"]] = server
                log(f"DISCOVERY SOURCE OK url={url} servers={len(parsed)}")
            except Exception as exc:
                log(f"DISCOVERY PARSE FAIL url={url} error={type(exc).__name__}: {exc}")
    except TimeoutError:
        log(f"DISCOVERY DEADLINE reached unfinished={sum(not f.done() for f in futures)}; using completed sources and cache")
    finally:
        for future in futures:
            if not future.done():
                future.cancel()
        executor.shutdown(wait=False, cancel_futures=True)
    data = sorted(merged.values(), key=lambda s: (s.get("rank", -999), -s.get("ping", 9999)), reverse=True)[:250]
    _cache_save(data)
    log(f"DISCOVERY READY candidates={len(data)} elapsed={time.monotonic()-started:.2f}s")
    return data


def openvpn_exe() -> str | None:
    candidates = [shutil.which("openvpn.exe"), shutil.which("openvpn"),
                  r"C:\Program Files\OpenVPN\bin\openvpn.exe",
                  r"C:\Program Files (x86)\OpenVPN\bin\openvpn.exe"]
    for path in candidates:
        if path and os.path.isfile(path) and path.lower().endswith("openvpn.exe"):
            return path
    return None


def _openvpn_version(exe: str) -> tuple[int, int, int]:
    try:
        cp = subprocess.run([exe, "--version"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, timeout=5, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        match = re.search(r"OpenVPN\s+(\d+)\.(\d+)(?:\.(\d+))?", cp.stdout)
        if match:
            return int(match.group(1)), int(match.group(2)), int(match.group(3) or 0)
    except Exception as exc:
        log(f"OPENVPN VERSION FAIL error={type(exc).__name__}: {exc}")
    return (0, 0, 0)


def _vpnbook_profiles(server: dict) -> list[str]:
    raw = http_get(server["bundle"], 15, 8_000_000)
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
    raw = http_get(VPNBOOK_PAGE, 12, 5_000_000).decode("utf-8", "replace")
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


def _prepare(profile: str, username: str, password: str, work: Path, openvpn_version=(0, 0, 0)) -> Path:
    auth = work / "auth.txt"
    auth.write_text(username + "\n" + password + "\n", encoding="utf-8")
    lines, legacy_cipher, has_compression, has_dev = [], None, False, False
    for original in profile.splitlines():
        stripped, low = original.strip(), original.strip().lower()
        if not stripped or low.startswith(("#", ";")):
            lines.append(original); continue
        if low.startswith("cipher "):
            legacy_cipher = stripped.split(None, 1)[1].strip()
        if low.startswith("compress ") or low.startswith("comp-lzo"):
            has_compression = True
        if low.startswith("dev "):
            has_dev = True
        if low.startswith(("auth-user-pass", "redirect-gateway", "route ", "route-ipv6 ", "route-nopull", "pull-filter", "register-dns", "block-outside-dns", "route-metric ")):
            continue
        lines.append(original)
    if not has_dev:
        lines.append("dev tun")
    lines.extend(["client", "redirect-gateway def1", "route 0.0.0.0 128.0.0.0", "route 128.0.0.0 128.0.0.0",
                  "route-metric 5", f'auth-user-pass "{auth}"', "auth-nocache", "resolv-retry infinite",
                  "connect-retry 2 3", "connect-timeout 10", "persist-key", "persist-tun", "verb 4"])
    if openvpn_version >= (2, 6, 0):
        lines.append("disable-dco")
    if legacy_cipher:
        modern = "AES-256-GCM:AES-128-GCM:CHACHA20-POLY1305"
        if legacy_cipher.upper() not in modern.upper().split(":"):
            lines.append(f"data-ciphers {modern}:{legacy_cipher}")
            lines.append(f"data-ciphers-fallback {legacy_cipher}")
    if has_compression and openvpn_version >= (2, 6, 0):
        lines.append("allow-compression asym")
    if os.name == "nt" and openvpn_version >= (2, 4, 0):
        lines.append("block-outside-dns")
    config = work / "client.ovpn"
    config.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return config


def _classify(text: str, code: int | None) -> str:
    low = text.lower()
    patterns = (("options error", "OpenVPN configuration error"), ("unknown option", "OpenVPN does not support an option in this profile"),
                ("block-outside-dns requires", "administrator permission is required for DNS leak protection"), ("auth_failed", "authentication failed"),
                ("data channel cipher negotiation failed", "server cipher is incompatible"), ("tls error", "TLS handshake failed"),
                ("connection refused", "connection refused"), ("network is unreachable", "network unreachable"),
                ("cannot open tun", "TUN/TAP adapter unavailable"), ("all tap-windows adapters", "TUN/TAP adapter unavailable"),
                ("access is denied", "administrator permission required"), ("route addition failed", "Windows route installation failed"))
    for key, message in patterns:
        if key in low:
            return message
    return f"OpenVPN exited with code {code}" if code is not None else "connection timeout"


def route_snapshot() -> str:
    if os.name != "nt": return ""
    try:
        cp = subprocess.run(["route", "print", "-4"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=5,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        hits = [line.strip() for line in cp.stdout.splitlines() if re.search(r"(^|\s)(0\.0\.0\.0|128\.0\.0\.0)\s+128\.0\.0\.0\s", line)]
        return " | ".join(hits[-4:])
    except Exception as exc:
        log(f"ROUTE SNAPSHOT FAIL error={type(exc).__name__}: {exc}")
        return ""


def _read_log(path: Path) -> str:
    try: return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
    except OSError: return ""


def connect(server: dict, total_deadline: float = 35):
    exe = openvpn_exe()
    if not exe:
        raise RuntimeError("OpenVPN Community is not installed. Install OpenVPN Community and retry.")
    version = _openvpn_version(exe)
    log(f"OPENVPN DETECTED exe={exe} version={'.'.join(map(str, version))}")
    started = time.monotonic(); profiles, username, password = _profiles(server)
    PROFILE_LOGS.mkdir(parents=True, exist_ok=True); last = ""
    for index, profile in enumerate(profiles, 1):
        if time.monotonic() - started >= total_deadline: break
        work = Path(tempfile.mkdtemp(prefix="findupto-vpn-")); config = _prepare(profile, username, password, work, version)
        stamp = int(time.time()); safe = server["host"].replace(":", "_")
        logfile = PROFILE_LOGS / f"{safe}-{stamp}-v{index}.log"; startup_log = PROFILE_LOGS / f"{safe}-{stamp}-v{index}-startup.log"
        process = None; keep_work = False
        try:
            with startup_log.open("w", encoding="utf-8", errors="replace") as stdout_file:
                process = subprocess.Popen([exe, "--config", str(config), "--log", str(logfile), "--log-append"], stdout=stdout_file, stderr=subprocess.STDOUT,
                                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            log(f"OPENVPN START server={server['host']} variant={index}/{len(profiles)} pid={process.pid} log={logfile}")
            deadline = min(started + total_deadline, time.monotonic() + 12)
            while time.monotonic() < deadline:
                text = _read_log(logfile) + "\n" + _read_log(startup_log)
                if "Initialization Sequence Completed" in text:
                    snapshot = route_snapshot()
                    if os.name == "nt" and not snapshot:
                        last = "OpenVPN connected but full-tunnel Windows routes were not installed"; process.terminate(); process.wait(timeout=3); raise RuntimeError(last)
                    keep_work = True
                    log(f"OPENVPN INITIALIZED server={server['host']} variant={index} routes={snapshot or 'non-Windows'}")
                    return process, work, logfile
                if process.poll() is not None:
                    last = _classify(text, process.returncode); break
                time.sleep(0.2)
            if process and process.poll() is None:
                last = "connection timeout"; process.terminate()
                try: process.wait(timeout=3)
                except Exception: process.kill()
            text = _read_log(logfile) + "\n" + _read_log(startup_log)
            if text: last = _classify(text, process.returncode if process else None)
            log(f"OPENVPN ATTEMPT FAIL server={server['host']} variant={index} reason={last}")
        except Exception as exc:
            last = str(exc); log(f"OPENVPN ATTEMPT EXCEPTION server={server['host']} variant={index} error={type(exc).__name__}: {exc}")
        finally:
            if process and process.poll() is None and not keep_work:
                try: process.kill()
                except Exception: pass
            if not keep_work: shutil.rmtree(work, ignore_errors=True)
    raise RuntimeError(last or "all OpenVPN profiles failed; see OpenVPN logs")


def public_ip(timeout: float = 8) -> str:
    for url in ("https://api.ipify.org", "https://ifconfig.me/ip", "https://icanhazip.com"):
        try:
            value = http_get(url, timeout, 256).decode("ascii", "ignore").strip()
            if re.fullmatch(r"(?:\d{1,3}\.){3}\d{1,3}", value) or ":" in value: return value
        except Exception as exc:
            log(f"PUBLIC IP FAIL url={url} error={type(exc).__name__}: {exc}")
    raise RuntimeError("Unable to determine public IP")


def verify_tunnel(previous_ip: str | None = None, timeout: float = 8) -> str:
    snapshot = route_snapshot()
    if os.name == "nt" and not snapshot:
        raise RuntimeError("VPN process connected, but full-tunnel Windows routes are missing")
    ip = public_ip(timeout)
    if previous_ip and ip == previous_ip:
        raise RuntimeError(f"VPN initialized but public IP did not change ({ip}); traffic is not using the VPN")
    log(f"TUNNEL VERIFIED public_ip={ip} previous_ip={previous_ip or 'unknown'}")
    return ip
