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

APP_VERSION = "13.1.9"
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
    started = time.monotonic()
    curl = _curl()
    if curl:
        connect_timeout = max(4, min(10, int(timeout * 0.7)))
        cmd = [curl, "--fail", "--silent", "--show-error", "--location", "--connect-timeout", str(connect_timeout), "--max-time", str(max(8, int(timeout))), "-A", UA, url]
        try:
            cp = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=max(timeout + 3, 12), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
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
        with urllib.request.urlopen(request, timeout=min(max(4.0, timeout), 20), context=ssl.create_default_context()) as response:
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
    ids = set(re.findall(r"\b([a-z]{2}\d{2,4})\.vpnbook\.com\b", raw, re.I))
    ids.update(re.findall(r"\bvpnbook-openvpn-([a-z]{2}\d{2,4})\.zip\b", raw, re.I))
    for sid_raw in sorted(ids):
        sid = sid_raw.lower()
        if sid in seen:
            continue
        seen.add(sid)
        filename = f"vpnbook-openvpn-{sid}.zip"
        bundle = VPNBOOK_BASE + filename
        host = f"{sid}.vpnbook.com"
        result.append({"id": f"book:{sid}", "sid": sid, "ip": _resolve_host(host), "host": host, "country": "VPNBook", "city": sid.upper(), "ping": 9999, "speed": 0, "rank": -100, "bundle": bundle, "source": "VPNBook", "kind": "book"})
    return result


def vpnbook_servers() -> list[dict]:
    try:
        raw = http_get(VPNBOOK_PAGE, 10, 5_000_000).decode("utf-8", "replace")
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
            return [s for s in raw_servers if isinstance(s, dict) and _is_real_server(s)]
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


def discover(deadline: float = 10) -> list[dict]:
    started = time.monotonic()
    merged = {server["id"]: server for server in _cache_load()}
    log(f"DISCOVERY START cached={len(merged)} deadline={deadline:.1f}s")
    sources = [(VPNBOOK_PAGE, 10, 5_000_000)] + [(url, 12, 8_000_000) for url in GATE_URLS]
    executor = ThreadPoolExecutor(max_workers=len(sources), thread_name_prefix="vpn-discovery")
    futures = [executor.submit(_discover_source, *item) for item in sources]
    try:
        for future in as_completed(futures, timeout=max(1.0, deadline)):
            url, raw, error = future.result()
            if error:
                log(f"DISCOVERY SOURCE FAIL url={url} error={type(error).__name__}: {error}")
                continue
            try:
                parsed = vpnbook_servers_from_html(raw.decode("utf-8", "replace")) if url == VPNBOOK_PAGE else parse_gate(raw)
                for server in parsed:
                    if _is_real_server(server):
                        merged[server["id"]] = server
                log(f"DISCOVERY SOURCE OK url={url} servers={len(parsed)}")
            except Exception as exc:
                log(f"DISCOVERY PARSE FAIL url={url} error={type(exc).__name__}: {exc}")
    except TimeoutError:
        log("DISCOVERY DEADLINE reached; using completed sources and cache")
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
        method_tokens = (("tcp443", "TCP/443"), ("tcp80", "TCP/80"), ("udp53", "UDP/53"), ("udp25000", "UDP/25000"))
        selected: list[tuple[str, str]] = []
        used: set[str] = set()
        for token, label in method_tokens:
            candidates = [n for n in names if token in n.lower()]
            if not candidates:
                continue
            candidates.sort(key=lambda n: (len(n), n.lower()))
            selected.append((label, candidates[0]))
            used.add(candidates[0])
        # Keep an unknown-format profile only when the archive does not expose
        # the standard VPNBook transport names. This prevents 16 duplicate
        # attempts from burning the whole connection deadline.
        if not selected:
            selected = [("PROFILE", n) for n in sorted(names, key=str.lower)[:4]]
        profiles = [archive.read(name).decode("utf-8-sig", "replace") for _, name in selected]
        log("VPNBOOK METHODS selected=" + ",".join(label for label, _ in selected))
        return profiles


def _vpnbook_password() -> str:
    raw = http_get(VPNBOOK_PAGE, 10, 5_000_000).decode("utf-8", "replace")
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
    if legacy_cipher and not any(x.lower().startswith("data-ciphers ") for x in lines):
        lines.append(f"data-ciphers {legacy_cipher}:AES-256-GCM:AES-128-GCM")
    if not any(x.lower().startswith("auth-user-pass") for x in lines):
        lines.append(f"auth-user-pass {_ovpn_path(auth)}")
    # Make every transport self-failing instead of hanging after a TCP connect
    # or TLS handshake. The outer loop then advances to the next transport.
    lines.extend([
        "auth-nocache",
        "verb 3",
        "route-method exe",
        "route-delay 2 10",
        "route 0.0.0.0 128.0.0.0",
        "route 128.0.0.0 128.0.0.0",
        "connect-timeout 8",
        "server-poll-timeout 8",
        "resolv-retry 3",
        "ping 10",
        "ping-restart 30",
        "tls-timeout 8",
    ])
    if has_compression:
        lines.append("allow-compression yes")
    config = work / "client.ovpn"
    config.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return config


def _classify(text: str, code: int | None) -> str:
    low = text.lower()
    patterns = (("bad backslash", "OpenVPN configuration contains an invalid Windows backslash path"), ("options error", "OpenVPN configuration error"), ("unknown option", "OpenVPN does not support an option in this profile"), ("auth_failed", "authentication failed"), ("data channel cipher negotiation failed", "server cipher is incompatible"), ("tls error", "TLS handshake failed"), ("connection refused", "connection refused"), ("network is unreachable", "network unreachable"), ("cannot open tun", "TUN/TAP adapter unavailable"), ("all tap-windows adapters", "TUN/TAP adapter unavailable"), ("access is denied", "administrator permission required"), ("route addition failed", "Windows route installation failed"), ("push_request", "server did not complete the OpenVPN control-channel push exchange"))
    for key, message in patterns:
        if key in low:
            return message
    return f"OpenVPN exited with code {code}" if code is not None else "connection timeout"


def route_snapshot() -> str:
    if os.name != "nt":
        return ""
    try:
        cp = subprocess.run(["route", "print", "-4"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=5, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        hits = []
        for line in cp.stdout.splitlines():
            normalized = " ".join(line.strip().split())
            if re.match(r"^0\.0\.0\.0 128\.0\.0\.0\s+\S+\s+\S+", normalized) or re.match(r"^128\.0\.0\.0 128\.0\.0\.0\s+\S+\s+\S+", normalized):
                hits.append(normalized)
        return " | ".join(hits[-8:])
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


def connect(server: dict, total_deadline: float = 60):
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
    log(f"OPENVPN FALLBACK PLAN server={server['host']} attempts={len(profiles)} per_attempt=12s")
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
                    snapshot = ""
                    route_deadline = time.monotonic() + 5
                    while time.monotonic() < route_deadline:
                        snapshot = route_snapshot()
                        if os.name != "nt" or ("0.0.0.0 128.0.0.0" in snapshot and "128.0.0.0 128.0.0.0" in snapshot):
                            break
                        time.sleep(0.25)
                    if os.name == "nt" and not ("0.0.0.0 128.0.0.0" in snapshot and "128.0.0.0 128.0.0.0" in snapshot):
                        last = "OpenVPN connected but both full-tunnel Windows /1 routes were not installed"
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
            log(f"OPENVPN ATTEMPT FAIL server={server['host']} profile={index}/{len(profiles)} reason={last}; trying next method")
            _write_failure_log(server, text or last)
        except Exception as exc:
            last = str(exc)
            text = _read_log(work / "openvpn.log")
            if text:
                _write_failure_log(server, text)
            log(f"OPENVPN ATTEMPT EXCEPTION server={server['host']} profile={index}/{len(profiles)} error={type(exc).__name__}: {exc}; trying next method")
        finally:
            if process and process.poll() is None:
                try:
                    process.kill()
                except Exception:
                    pass
            shutil.rmtree(work, ignore_errors=True)
    raise RuntimeError(last or "all OpenVPN transport methods failed; see the latest OpenVPN failure log")


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
    snapshot = ""
    if os.name == "nt":
        route_deadline = time.monotonic() + 5
        while time.monotonic() < route_deadline:
            snapshot = route_snapshot()
            if "0.0.0.0 128.0.0.0" in snapshot and "128.0.0.0 128.0.0.0" in snapshot:
                break
            time.sleep(0.25)
        if not ("0.0.0.0 128.0.0.0" in snapshot and "128.0.0.0 128.0.0.0" in snapshot):
            raise RuntimeError("VPN process connected, but both full-tunnel Windows /1 routes are missing")
    ip = public_ip(timeout)
    if previous_ip and ip == previous_ip:
        raise RuntimeError(f"VPN initialized but public IP did not change ({ip}); traffic is not using the VPN")
    log(f"PUBLIC IP VPN url=https://api.ipify.org public_ip={ip}")
    return ip
