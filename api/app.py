import asyncio
import csv
import json
import os
import time
from pathlib import Path
from typing import List

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, Field

APP_VERSION = "4.0.0"
CACHE_TTL = max(30, int(os.getenv("VPN_CACHE_TTL", "300")))
FETCH_TIMEOUT = max(4, int(os.getenv("VPN_FETCH_TIMEOUT", "9")))
STALE_MAX_AGE = max(3600, int(os.getenv("VPN_STALE_MAX_AGE", str(7 * 86400))))
CACHE_FILE = Path(os.getenv("VPN_CACHE_FILE", "/tmp/findupto-vpn-cache.json"))
API_KEY = os.getenv("FINDUPTO_API_KEY", "")
SOURCES = (
    "https://www.vpngate.net/api/iphone/",
    "https://download.vpngate.jp/api/iphone/",
    "http://www.vpngate.net/api/iphone/",
)

app = FastAPI(title="Findupto Free VPN Directory", version=APP_VERSION)


class Node(BaseModel):
    id: str = Field(min_length=3, max_length=80)
    country: str = Field(min_length=2, max_length=80)
    city: str = Field(default="Unknown", max_length=80)
    endpoint: str = Field(min_length=3, max_length=255)
    public_key: str = Field(min_length=20, max_length=100)
    protocol: str = "wireguard"
    active: bool = True
    last_seen: float = 0
    config_url: str | None = None


class PublicServer(BaseModel):
    id: str
    country: str
    city: str
    hostname: str
    ip: str
    protocol: str
    ping_ms: float | None = None
    speed_mbps: float | None = None
    score: float
    source: str
    config_b64: str | None = None
    config_url: str | None = None


nodes: dict[str, Node] = {}
_cache: tuple[float, list[PublicServer]] = (0, [])
_lock = asyncio.Lock()
_refresh_task: asyncio.Task | None = None


def require_api_key(x_api_key: str = Header(default="")):
    if not API_KEY or x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="invalid API key")


def number(value: str | None, default: float | None = None) -> float | None:
    try:
        return float(value) if value not in (None, "") else default
    except (TypeError, ValueError):
        return default


def parse_csv(payload: bytes, limit: int = 160) -> list[PublicServer]:
    text = payload.decode("utf-8-sig", errors="replace")
    lines = text.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    header = next((i for i, line in enumerate(lines) if line.startswith("#HostName,")), None)
    if header is None:
        raise ValueError("VPN Gate CSV header not found")
    reader = csv.DictReader([lines[header][1:]] + [x for x in lines[header + 1:] if x.strip() and not x.startswith(("#", "*"))])
    result: list[PublicServer] = []
    for row in reader:
        ip = (row.get("IP") or "").strip()
        country = (row.get("CountryLong") or row.get("CountryShort") or "").strip()
        config = (row.get("OpenVPN_ConfigData_Base64") or "").strip() or None
        if not ip or not country or not config:
            continue
        ping = number(row.get("Ping"))
        speed = number(row.get("Speed"))
        speed_mbps = speed / 1_000_000 if speed is not None else None
        uptime = min(100.0, max(0.0, number(row.get("Uptime"), 0) or 0))
        gate_score = number(row.get("Score"), 0) or 0
        if ping is not None and ping > 900:
            continue
        if speed_mbps is not None and speed_mbps < 0.5:
            continue
        score = (speed_mbps or 0) * 2.5 - (ping if ping is not None else 250) * 0.25 + uptime * 0.2 + gate_score * 0.01
        result.append(PublicServer(
            id=f"vpngate-{ip}-{row.get('HostName','').strip()}",
            country=country,
            city=(row.get("City") or "Unknown").strip() or "Unknown",
            hostname=(row.get("HostName") or "").strip(),
            ip=ip,
            protocol="openvpn",
            ping_ms=ping,
            speed_mbps=round(speed_mbps, 2) if speed_mbps is not None else None,
            score=round(score, 2),
            source="VPN Gate",
            config_b64=config,
            config_url=f"https://www.vpngate.net/common/openvpn_download.aspx?ip={ip}",
        ))
    result.sort(key=lambda x: x.score, reverse=True)
    return result[:limit]


def read_disk_cache() -> tuple[list[PublicServer], float]:
    try:
        data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        stamp = float(data.get("time", 0))
        return [PublicServer.model_validate(x) for x in data.get("servers", [])], stamp
    except Exception:
        return [], 0


def write_disk_cache(servers: list[PublicServer]):
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = CACHE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps({"time": time.time(), "servers": [x.model_dump() for x in servers]}, separators=(",", ":")), encoding="utf-8")
        tmp.replace(CACHE_FILE)
    except OSError:
        pass


async def fetch_source(client: httpx.AsyncClient, url: str):
    try:
        r = await client.get(url)
        r.raise_for_status()
        servers = await asyncio.to_thread(parse_csv, r.content, 160)
        return url, servers, None
    except Exception as exc:
        return url, [], str(exc)


async def refresh_live() -> list[PublicServer]:
    timeout = httpx.Timeout(FETCH_TIMEOUT, connect=3.5, read=FETCH_TIMEOUT, write=5.0, pool=3.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers={"User-Agent": "Findupto-Free-VPN-API/4.0", "Accept": "text/plain,*/*", "Accept-Encoding": "gzip, deflate"}) as client:
        tasks = [asyncio.create_task(fetch_source(client, url)) for url in SOURCES]
        pending = set(tasks)
        deadline = asyncio.get_running_loop().time() + FETCH_TIMEOUT
        collected: list[PublicServer] = []
        while pending and asyncio.get_running_loop().time() < deadline:
            timeout_left = max(0.05, deadline - asyncio.get_running_loop().time())
            done, pending = await asyncio.wait(pending, timeout=timeout_left, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                try:
                    _, servers, _ = task.result()
                    collected.extend(servers)
                except Exception:
                    pass
            if collected:
                break
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        merged = {x.id: x for x in collected}
        result = sorted(merged.values(), key=lambda x: x.score, reverse=True)[:160]
        if result:
            write_disk_cache(result)
        return result


async def get_servers(limit: int = 100) -> list[PublicServer]:
    global _cache, _refresh_task
    now = time.monotonic()
    if _cache[1] and now - _cache[0] < CACHE_TTL:
        return _cache[1][:limit]

    async with _lock:
        now = time.monotonic()
        if _cache[1] and now - _cache[0] < CACHE_TTL:
            return _cache[1][:limit]
        disk, stamp = read_disk_cache()
        if disk and time.time() - stamp <= STALE_MAX_AGE:
            _cache = (now, disk)
            # Serve immediately from disk; refresh in the background.
            if _refresh_task is None or _refresh_task.done():
                _refresh_task = asyncio.create_task(refresh_live())
                def done(task):
                    global _cache
                    try:
                        result = task.result()
                        if result:
                            _cache = (time.monotonic(), result)
                    except Exception:
                        pass
                _refresh_task.add_done_callback(done)
            return disk[:limit]

        result = await refresh_live()
        if result:
            _cache = (time.monotonic(), result)
            return result[:limit]
        return []


@app.get("/")
def root():
    return {"name": "Findupto Free VPN", "status": "ok", "version": APP_VERSION}


@app.get("/health")
def health():
    return {"status": "healthy", "community_nodes": len(nodes), "cached_servers": len(_cache[1]), "refreshing": bool(_refresh_task and not _refresh_task.done())}


@app.get("/api/v1/nodes", response_model=List[Node])
def list_nodes(country: str | None = None):
    cutoff = time.time() - 300
    result = [n for n in nodes.values() if n.active and n.last_seen >= cutoff]
    if country:
        result = [n for n in result if n.country.casefold() == country.casefold()]
    return sorted(result, key=lambda n: (n.country.casefold(), n.city.casefold()))


@app.get("/api/v1/public/servers", response_model=List[PublicServer])
async def public_servers(country: str | None = None, limit: int = Query(30, ge=1, le=100)):
    servers = await get_servers(100)
    if country:
        servers = [x for x in servers if x.country.casefold() == country.casefold()]
    return servers[:limit]


@app.get("/api/v1/public/best", response_model=PublicServer | None)
async def best_public_server(country: str | None = None):
    servers = await get_servers(100)
    if country:
        servers = [x for x in servers if x.country.casefold() == country.casefold()]
    return servers[0] if servers else None


@app.post("/api/v1/nodes", dependencies=[Depends(require_api_key)])
def register_node(node: Node):
    node.last_seen = time.time()
    nodes[node.id] = node
    return {"ok": True, "node": node}


@app.post("/api/v1/nodes/{node_id}/heartbeat", dependencies=[Depends(require_api_key)])
def heartbeat(node_id: str):
    node = nodes.get(node_id)
    if not node:
        raise HTTPException(status_code=404, detail="node not found")
    node.last_seen = time.time()
    node.active = True
    return {"ok": True, "last_seen": node.last_seen}


@app.delete("/api/v1/nodes/{node_id}", dependencies=[Depends(require_api_key)])
def remove_node(node_id: str):
    if node_id not in nodes:
        raise HTTPException(status_code=404, detail="node not found")
    del nodes[node_id]
    return {"ok": True}
