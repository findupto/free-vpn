from __future__ import annotations

import base64
import concurrent.futures
import gzip
import json
import os
import re
import threading
import time
import urllib.request
import zlib
from pathlib import Path

UA = "Findupto-Free-VPN/5.0"
DATA_DIR = Path(os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))) / "Findupto"
CACHE_FILE = DATA_DIR / "servers.json"
API_URL = os.environ.get("FINDUPTO_API_URL", "").strip()
LIVE_TIMEOUT = max(3.0, float(os.environ.get("VPN_LIVE_TIMEOUT", "8")))
SOURCE_TIMEOUT = max(2.5, float(os.environ.get("VPN_SOURCE_TIMEOUT", "5.5")))
STALE_MAX_AGE = max(3600, int(os.environ.get("VPN_STALE_MAX_AGE", str(7 * 86400))))

VPN_GATE_SOURCES = (
    "https://www.vpngate.net/api/iphone/",
    "https://download.vpngate.jp/api/iphone/",
    "http://www.vpngate.net/api/iphone/",
)

VPNBOOK_PAGE = "https://www.vpnbook.com/freevpn/openvpn"
VPNBOOK_FALLBACK_BUNDLES = (
    "US1", "US2", "CA1", "CA2", "UK1", "UK2", "DE1", "DE2", "FR1", "FR2"
)
VPNBOOK_BUNDLE_TEMPLATE = "https://www.vpnbook.com/free-openvpn-account/VPNBook.com-OpenVPN-{name}.zip"

_refresh_lock = threading.Lock()


def _log(message: str):
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with (DATA_DIR / "findupto.log").open("a", encoding="utf-8", errors="replace") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] resilient: {message}\n")
    except OSError:
        pass


def _decode_body(data: bytes, encoding: str) -> bytes:
    enc = (encoding or "").lower()
    try:
        if "gzip" in enc:
            return gzip.decompress(data)
        if "deflate" in enc:
            return zlib.decompress(data)
    except Exception:
        pass
    return data


def _get(url: str, timeout: float) -> bytes:
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,text/plain,application/zip,*/*",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "close",
        "Cache-Control": "no-cache",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return _decode_body(r.read(), r.headers.get("Content-Encoding", ""))


def _valid_servers(items) -> list[dict]:
    result = []
    for item in items or []:
        if not isinstance(item, dict) or not item.get("ip") or not item.get("config_b64"):
            continue
        result.append(item)
    result.sort(key=lambda x: float(x.get("score", 0) or 0), reverse=True)
    return result[:180]


def _api_servers() -> list[dict]:
    if not API_URL:
        return []
    from app import parse_servers
    raw = _get(API_URL.rstrip("/") + "/api/v1/public/servers?limit=120", 3.5)
    return _valid_servers(parse_servers(raw))


def _vpngate_servers(url: str) -> list[dict]:
    from app import parse_servers
    return _valid_servers(parse_servers(_get(url, SOURCE_TIMEOUT)))


def _vpnbook_credentials(page: bytes) -> tuple[str, str]:
    text = page.decode("utf-8", errors="replace")
    user = re.search(r"Username\s*</[^>]+>\s*(?:<[^>]+>\s*)*`?([A-Za-z0-9_-]{3,32})", text, re.I)
    password = re.search(r"Password\s*</[^>]+>\s*(?:<[^>]+>\s*)*`?([A-Za-z0-9_-]{5,32})", text, re.I)
    # Current VPNBook page exposes the values in rendered HTML as well as plain text.
    if not user:
        user = re.search(r">\s*(vpnbook)\s*<", text, re.I)
    if not password:
        password = re.search(r">\s*([A-Za-z0-9]{6,16})\s*<", text[text.lower().find("password"):], re.I)
    return (user.group(1) if user else "vpnbook", password.group(1) if password else "")


def _vpnbook_bundle_urls(page: bytes) -> list[tuple[str, str]]:
    text = page.decode("utf-8", errors="replace")
    found = []
    for href in re.findall(r"href=[\"']([^\"']+)[\"']", text, re.I):
        if "free-openvpn-account" not in href.lower() or not href.lower().endswith(".zip"):
            continue
        match = re.search(r"OpenVPN-([A-Za-z0-9_-]+)\.zip", href, re.I)
        if match:
            name = match.group(1).upper()
            url = href if href.lower().startswith("http") else "https://www.vpnbook.com" + (href if href.startswith("/") else "/" + href)
            found.append((name, url))
    if not found:
        found = [(name, VPNBOOK_BUNDLE_TEMPLATE.format(name=name)) for name in VPNBOOK_FALLBACK_BUNDLES]
    unique = {}
    for name, url in found:
        unique[name] = url
    return list(unique.items())[:12]


def _vpnbook_servers() -> list[dict]:
    # VPNBook is an independent bootstrap path. Its bundles are tiny compared with
    # VPN Gate's ~1.3 MB CSV, so discovery remains fast even on poor connections.
    page = _get(VPNBOOK_PAGE, SOURCE_TIMEOUT)
    username, password = _vpnbook_credentials(page)
    bundles = _vpnbook_bundle_urls(page)
    if not password:
        raise RuntimeError("VPNBook credentials were not found")

    def fetch_bundle(pair):
        name, url = pair
        try:
            import io
            import zipfile
            raw = _get(url, SOURCE_TIMEOUT)
            if raw[:2] != b"PK":
                raise RuntimeError("invalid VPNBook bundle")
            servers = []
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                for filename in archive.namelist():
                    if not filename.lower().endswith(".ovpn"):
                        continue
                    config = archive.read(filename).decode("utf-8-sig", errors="replace")
                    if "client" not in config.lower() or "remote " not in config.lower():
                        continue
                    # Keep credentials inside the profile so the existing OpenVPN
                    # engine does not accidentally use the old vpn/vpn placeholder.
                    config = re.sub(r"(?im)^auth-user-pass.*$", "", config)
                    config += f"\n<auth-user-pass>\n{username}\n{password}\n</auth-user-pass>\n"
                    remote = re.search(r"(?im)^remote\s+([^\s]+)\s+(\d+)", config)
                    if not remote:
                        continue
                    host, port = remote.group(1), int(remote.group(2))
                    proto = "udp" if re.search(r"(?im)^proto\s+udp", config) else "tcp"
                    region = name[:2].upper()
                    score = (45 if port in (443, 80, 53) else 35) + (12 if proto == "tcp" and port == 443 else 0)
                    servers.append({
                        "id": f"vpnbook-{name}-{filename}",
                        "ip": host,
                        "hostname": host,
                        "country": region,
                        "city": name,
                        "ping_ms": None,
                        "speed_mbps": 0.0,
                        "uptime": 99.0,
                        "score": score,
                        "config_b64": base64.b64encode(config.encode()).decode(),
                        "source": "VPNBook",
                    })
            return servers
        except Exception as exc:
            _log(f"VPNBook {name}: {exc}")
            return []

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(bundles)), thread_name_prefix="vpnbook")
    futures = [executor.submit(fetch_bundle, pair) for pair in bundles]
    result = []
    try:
        for future in concurrent.futures.as_completed(futures, timeout=LIVE_TIMEOUT):
            result.extend(future.result())
            if len(result) >= 12:
                break
    except concurrent.futures.TimeoutError:
        pass
    finally:
        for future in futures:
            if not future.done():
                future.cancel()
        executor.shutdown(wait=False, cancel_futures=True)
    return _valid_servers(result)


def _load_cache() -> tuple[list[dict], float]:
    try:
        data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        stamp = float(data.get("time", 0))
        return _valid_servers(data.get("servers", [])), stamp
    except Exception:
        return [], 0


def _save_cache(servers: list[dict]):
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        tmp = CACHE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps({"time": time.time(), "servers": servers}, separators=(",", ":")), encoding="utf-8")
        tmp.replace(CACHE_FILE)
    except OSError:
        pass


def _refresh_live() -> list[dict]:
    sources = []
    if API_URL:
        sources.append(("Findupto API", _api_servers))
    sources.append(("VPNBook", _vpnbook_servers))
    sources.extend((url, lambda u=url: _vpngate_servers(u)) for url in VPN_GATE_SOURCES)

    def worker(item):
        name, fn = item
        try:
            return name, fn(), None
        except Exception as exc:
            return name, [], str(exc)

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=len(sources), thread_name_prefix="vpn-discovery")
    futures = [executor.submit(worker, item) for item in sources]
    deadline = time.monotonic() + LIVE_TIMEOUT
    collected = []
    errors = []
    try:
        pending = set(futures)
        while pending and time.monotonic() < deadline:
            done, pending = concurrent.futures.wait(
                pending,
                timeout=max(0.05, deadline - time.monotonic()),
                return_when=concurrent.futures.FIRST_COMPLETED,
            )
            for future in done:
                try:
                    name, servers, error = future.result()
                except Exception as exc:
                    errors.append(str(exc))
                    continue
                if servers:
                    collected.extend(servers)
                    # One healthy independent source is enough to populate the UI.
                    # Do not wait for VPN Gate's slow 1.3 MB endpoint.
                    if any(s.get("source") == "VPNBook" for s in servers):
                        pending.clear()
                elif error:
                    errors.append(f"{name}: {error}")
            if collected:
                break
        dedup = {}
        for server in collected:
            key = str(server.get("id") or f"{server.get('ip')}-{server.get('hostname')}")
            old = dedup.get(key)
            if old is None or float(server.get("score", 0)) > float(old.get("score", 0)):
                dedup[key] = server
        result = sorted(dedup.values(), key=lambda x: float(x.get("score", 0) or 0), reverse=True)[:180]
        if result:
            _save_cache(result)
            _log(f"live discovery: {len(result)} servers")
        else:
            _log("live discovery failed: " + " | ".join(errors[-5:]))
        return result
    finally:
        for future in futures:
            if not future.done():
                future.cancel()
        executor.shutdown(wait=False, cancel_futures=True)


def _bootstrap_servers() -> list[dict]:
    # Always provide a visible bootstrap catalog even when public discovery APIs are
    # blocked. Configs are still downloaded/validated before an actual tunnel starts.
    rows = [
        ("US", "US16", "us16.vpnbook.com"), ("US", "US178", "us178.vpnbook.com"),
        ("CA", "CA149", "ca149.vpnbook.com"), ("CA", "CA196", "ca196.vpnbook.com"),
        ("GB", "UK205", "uk205.vpnbook.com"), ("GB", "UK68", "uk68.vpnbook.com"),
        ("DE", "DE20", "de20.vpnbook.com"), ("DE", "DE220", "de220.vpnbook.com"),
        ("FR", "FR200", "fr200.vpnbook.com"), ("FR", "FR2311", "fr2311.vpnbook.com"),
    ]
    result = []
    for country, name, host in rows:
        bundle = name[:2] + ("1" if name[-2:] in ("16", "49", "05", "20", "00") else "2")
        url = VPNBOOK_BUNDLE_TEMPLATE.format(name=bundle)
        # Use an empty placeholder only for display; connect path resolves it.
        result.append({
            "id": f"vpnbook-bootstrap-{name}", "ip": host, "hostname": host,
            "country": country, "city": name, "ping_ms": None,
            "speed_mbps": 0.0, "uptime": 99.0, "score": 20.0,
            "config_b64": base64.b64encode(b"bootstrap").decode(),
            "config_url": url, "source": "VPNBook bootstrap",
        })
    return result


def fetch_servers() -> list[dict]:
    cached, stamp = _load_cache()
    if cached and time.time() - stamp < 300:
        return cached
    if _refresh_lock.acquire(blocking=False):
        try:
            live = _refresh_live()
            if live:
                return live
            if cached and time.time() - stamp <= STALE_MAX_AGE:
                return cached
            bootstrap = _bootstrap_servers()
            _save_cache(bootstrap)
            return bootstrap
        finally:
            _refresh_lock.release()
    if cached and time.time() - stamp <= STALE_MAX_AGE:
        return cached
    return _bootstrap_servers()
