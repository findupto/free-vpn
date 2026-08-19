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

APP_VERSION = "3.0.0"
CACHE_TTL = max(30, int(os.getenv("VPN_CACHE_TTL", "600")))
FETCH_TIMEOUT = max(5, int(os.getenv("VPN_FETCH_TIMEOUT", "30")))
CACHE_FILE = Path(os.getenv("VPN_CACHE_FILE", "/tmp/findupto-vpn-cache.json"))
API_KEY = os.getenv("FINDUPTO_API_KEY", "")
SOURCES = [
    "https://www.vpngate.net/api/iphone/",
    "https://download.vpngate.jp/api/iphone/",
    "http://www.vpngate.net/api/iphone/",
]

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


def require_api_key(x_api_key: str = Header(default="")):
    if not API_KEY or x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="invalid API key")


def number(value: str | None, default: float | None = None) -> float | None:
    try:
        return float(value) if value not in (None, "") else default
    except (TypeError, ValueError):
        return default


def parse_csv(payload: bytes, limit: int = 150) -> list[PublicServer]:
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
        if not ip or not country:
            continue
        ping = number(row.get("Ping"))
        speed = number(row.get("Speed"))
        speed_mbps = speed / 1_000_000 if speed is not None else None
        uptime = min(100.0, max(0.0, number(row.get("Uptime"), 0) or 0))
        score_raw = number(row.get("Score"), 0) or 0
        if ping is not None and ping > 900:
            continue
        if speed_mbps is not None and speed_mbps < 0.5:
            continue
        score = (speed_mbps or 0) * 2.5 - (ping if ping is not None else 250) * 0.25 + uptime * 0.2 + score_raw * 0.01
        config = (row.get("OpenVPN_ConfigData_Base64") or "").strip() or None
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


def read_disk_cache() -> list[PublicServer]:
    try:
        data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        return [PublicServer.model_validate(x) for x in data.get("servers", [])]
    except Exception:
        return []


def write_disk_cache(servers: list[PublicServer]):
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = CACHE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps({"time": time.time(), "servers": [x.model_dump() for x in servers]}), encoding="utf-8")
        tmp.replace(CACHE_FILE)
    except OSError:
        pass


async def fetch_source(client: httpx.AsyncClient, url: str):
    try:
        r = await client.get(url)
        r.raise_for_status()
        return await asyncio.to_thread(parse_csv, r.content, 150)
    except (httpx.HTTPError, OSError, ValueError):
        return None


async def get_servers(limit: int = 100) -> list[PublicServer]:
    global _cache
    if _cache[1] and time.monotonic() - _cache[0] < CACHE_TTL:
        return _cache[1][:limit]
    async with _lock:
        if _cache[1] and time.monotonic() - _cache[0] < CACHE_TTL:
            return _cache[1][:limit]
        timeout = httpx.Timeout(FETCH_TIMEOUT, connect=5.0, read=FETCH_TIMEOUT, write=10.0, pool=5.0)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers={"User-Agent": "Findupto-Free-VPN-API/3.0", "Accept": "text/plain,*/*"}) as client:
            tasks = [asyncio.create_task(fetch_source(client, url)) for url in SOURCES]
            for task in asyncio.as_completed(tasks):
                servers = await task
                if servers:
                    _cache = (time.monotonic(), servers)
                    write_disk_cache(servers)
                    for other in tasks:
                        if not other.done():
                            other.cancel()
                    return servers[:limit]
        disk = read_disk_cache()
        if disk:
            _cache = (time.monotonic(), disk)
            return disk[:limit]
        return []


@app.get("/")
def root():
    return {"name": "Findupto Free VPN", "status": "ok", "version": APP_VERSION}


@app.get("/health")
def health():
    return {"status": "healthy", "community_nodes": len(nodes), "cached_servers": len(_cache[1])}


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
