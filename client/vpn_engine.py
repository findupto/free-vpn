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

APP_VERSION = "13.1.3"
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
    """Fetch a URL with practical Windows timeouts and urllib fallback."""
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
    """Parse both the legacy ZIP-link HTML and VPNBook's current JS/server page."""
    result, seen = [], set()
    # Current VPNBook pages expose server hostnames in the rendered HTML but
    # may no longer expose the old vpnbook-openvpn-*.zip hrefs.
    ids = set(re.findall(r"\b([a-z]{2}\d{2,4})\.vpnbook\.com\b", raw, re.I))
    ids.update(re.findall(r"\bvpnbook-openvpn-([a-z]{2}\d{2,4})\.zip\b", raw, re.I))
    for sid_raw in sorted(ids):
        sid = sid_raw.lower()
        if sid in seen:
            continue
        seen.add(sid)
        filename = f"vpnbook-openvpn-{sid}.zip"
        # The legacy endpoint remains the documented bundle naming scheme.
        bundle = VPNBOOK_BASE + filename
        host = f"{sid}.vpnbook.com"
        result.append({
            "id": f"book:{sid}",
            "sid": sid,
            "ip": _resolve_host(host),
            "host": host,
            "country": "VPNBook",
            "city": sid.upper(),
            "ping": 9999,
            "speed": 0,
            "rank": -100,
            "bundle": bundle,
            "source": "VPNBook",
            "kind": "book",
        })
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


def discover(deadline: float = 10) -> list[dict]:
    started = time.monotonic()
    merged = {server["id"]: server for server in _cache_load()}
    log(f"DISCOVERY START cached={len(merged)} deadline={deadline:.1f}s")
    # VPNBook is the fast/reliable baseline. VPN Gate is supplementary and can
    # be very slow from some networks, so it must never block the UI refresh.
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
                if url == VPNBOOK_PAGE:
                    parsed = vpnbook_servers_from_html(raw.decode("utf-8", "replace"))
                else:
                    parsed = parse_gate(raw)
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
