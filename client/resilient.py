from __future__ import annotations

import concurrent.futures
import gzip
import json
import os
import threading
import time
import urllib.error
import urllib.request
import zlib
from pathlib import Path

UA = "Findupto-Free-VPN/4.0"
DATA_DIR = Path(os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))) / "Findupto"
CACHE_FILE = DATA_DIR / "servers.json"
API_URL = os.environ.get("FINDUPTO_API_URL", "").strip()
LIVE_TIMEOUT = max(4.0, float(os.environ.get("VPN_LIVE_TIMEOUT", "9")))
STALE_MAX_AGE = max(3600, int(os.environ.get("VPN_STALE_MAX_AGE", str(7 * 86400))))

VPN_GATE_SOURCES = (
    "https://www.vpngate.net/api/iphone/",
    "https://download.vpngate.jp/api/iphone/",
    "http://www.vpngate.net/api/iphone/",
)

_refresh_lock = threading.Lock()
_refreshing = False


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
    except zlib.error:
        pass
    return data


def _get(url: str, timeout: float) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "application/json,text/plain,*/*",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "close",
            "Cache-Control": "no-cache",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return _decode_body(r.read(), r.headers.get("Content-Encoding", ""))


def _valid_servers(items) -> list[dict]:
    result = []
    for item in items or []:
        if not isinstance(item, dict) or not item.get("ip") or not item.get("config_b64"):
            continue
        result.append(item)
    result.sort(key=lambda x: float(x.get("score", 0) or 0), reverse=True)
    return result[:160]


def _api_servers() -> list[dict]:
    if not API_URL:
        return []
    data = json.loads(_get(API_URL.rstrip("/") + "/api/v1/public/servers?limit=100", 4.0).decode("utf-8"))
    return _valid_servers(data)


def _vpngate_servers(url: str) -> list[dict]:
    # Reuse the application's proven parser so the resilience layer does not duplicate CSV rules.
    from app import parse_servers
    return _valid_servers(parse_servers(_get(url, LIVE_TIMEOUT)))


def _load_cache() -> tuple[list[dict], float]:
    try:
        data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        stamp = float(data.get("time", 0))
        servers = _valid_servers(data.get("servers", []))
        return servers, stamp
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
    sources = list(VPN_GATE_SOURCES)
    if API_URL:
        sources.insert(0, API_URL)

    def worker(source: str):
        try:
            servers = _api_servers() if source == API_URL and API_URL else _vpngate_servers(source)
            return source, servers, None
        except Exception as exc:
            return source, [], str(exc)

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=len(sources), thread_name_prefix="vpn-source")
    futures = [executor.submit(worker, source) for source in sources]
    deadline = time.monotonic() + LIVE_TIMEOUT
    best: list[dict] = []
    errors = []
    try:
        pending = set(futures)
        while pending and time.monotonic() < deadline:
            remaining = max(0.05, deadline - time.monotonic())
            done, pending = concurrent.futures.wait(pending, timeout=remaining, return_when=concurrent.futures.FIRST_COMPLETED)
            for future in done:
                try:
                    source, servers, error = future.result()
                except Exception as exc:
                    errors.append(str(exc))
                    continue
                if servers:
                    # Keep collecting already-finished sources, but never wait for a slow mirror.
                    best.extend(servers)
                elif error:
                    errors.append(f"{source}: {error}")
            if best:
                break
        merged = {str(x.get("id") or f"{x.get('ip')}-{x.get('hostname')}"): x for x in best}
        result = sorted(merged.values(), key=lambda x: float(x.get("score", 0) or 0), reverse=True)[:160]
        if result:
            _save_cache(result)
            _log(f"live discovery: {len(result)} servers; {len(errors)} source failures")
        else:
            _log("live discovery failed: " + " | ".join(errors[-3:]))
        return result
    finally:
        # Critical: never use a ThreadPoolExecutor context manager here. It waits for timed-out futures.
        for future in futures:
            if not future.done():
                future.cancel()
        executor.shutdown(wait=False, cancel_futures=True)


def fetch_servers() -> list[dict]:
    """Fast, non-blocking discovery with live race + stale cache fallback."""
    global _refreshing
    cached, stamp = _load_cache()
    if cached and time.time() - stamp < 300:
        return cached

    if _refresh_lock.acquire(blocking=False):
        try:
            _refreshing = True
            live = _refresh_live()
            if live:
                return live
            if cached and time.time() - stamp <= STALE_MAX_AGE:
                _log("using stale cache after live discovery failure")
                return cached
            return []
        finally:
            _refreshing = False
            _refresh_lock.release()

    # Another refresh is already running. Never queue/wait behind it.
    if cached and time.time() - stamp <= STALE_MAX_AGE:
        _log("refresh already running; returning cached servers immediately")
        return cached
    return []
