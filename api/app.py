import asyncio
import csv
import os
import secrets
import time
from typing import Dict, List

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, Field

app = FastAPI(title="Findupto Free VPN Directory", version="0.4.0")
API_KEY = os.getenv("FINDUPTO_API_KEY", "change-me")
VPN_GATE_CSV = "https://www.vpngate.net/api/iphone/"
CACHE_TTL = max(15, int(os.getenv("VPN_CACHE_TTL", "300")))
FETCH_TIMEOUT = max(3, int(os.getenv("VPN_FETCH_TIMEOUT", "8")))


class Node(BaseModel):
    id: str = Field(min_length=3, max_length=80)
    country: str = Field(min_length=2, max_length=80)
    city: str = Field(min_length=1, max_length=80)
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
    config_url: str | None = None


nodes: Dict[str, Node] = {}
_cache: tuple[float, list[PublicServer]] = (0, [])
_cache_lock = asyncio.Lock()


def require_api_key(x_api_key: str = Header(default="")):
    if not secrets.compare_digest(x_api_key, API_KEY):
        raise HTTPException(status_code=401, detail="invalid API key")


def as_float(value: str | None):
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def fetch_vpngate_servers(limit: int = 100) -> list[PublicServer]:
    headers = {"User-Agent": "Findupto-Free-VPN/0.4"}
    try:
        with httpx.Client(timeout=httpx.Timeout(FETCH_TIMEOUT, connect=3), follow_redirects=True, headers=headers) as client:
            response = client.get(VPN_GATE_CSV)
            response.raise_for_status()
            text = response.content.decode("utf-8-sig", errors="replace")
    except (httpx.HTTPError, OSError):
        return []

    lines = text.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    header_index = next((i for i, line in enumerate(lines) if line.startswith("#HostName,")), None)
    if header_index is None:
        return []

    reader = csv.DictReader([lines[header_index][1:]] + [line for line in lines[header_index + 1:] if line.strip() and not line.startswith("#") and not line.startswith("*")])
    rows: list[PublicServer] = []
    for row in reader:
        ip = (row.get("IP") or "").strip()
        country = (row.get("CountryLong") or row.get("CountryShort") or "").strip()
        if not ip or not country:
            continue
        ping = as_float(row.get("Ping"))
        speed_bps = as_float(row.get("Speed"))
        speed = speed_bps / 1_000_000 if speed_bps is not None else None
        uptime = min(as_float(row.get("Uptime")) or 0, 100)
        if ping is not None and ping > 500:
            continue
        if speed is not None and speed < 1:
            continue
        score = (speed or 0) * 2 - (ping or 250) * 0.35 + uptime * 0.15
        rows.append(PublicServer(
            id=f"vpngate-{ip}-{row.get('HostName', '')}",
            country=country,
            city=(row.get("City") or "Unknown").strip() or "Unknown",
            hostname=(row.get("HostName") or "").strip(),
            ip=ip,
            protocol="openvpn",
            ping_ms=ping,
            speed_mbps=speed,
            score=round(score, 2),
            source="VPN Gate",
            config_url=f"https://www.vpngate.net/common/openvpn_download.aspx?ip={ip}",
        ))
    rows.sort(key=lambda item: item.score, reverse=True)
    return rows[:limit]


async def get_vpngate_servers(limit: int = 100) -> list[PublicServer]:
    global _cache
    now = time.monotonic()
    if _cache[1] and now - _cache[0] < CACHE_TTL:
        return _cache[1][:limit]
    async with _cache_lock:
        now = time.monotonic()
        if _cache[1] and now - _cache[0] < CACHE_TTL:
            return _cache[1][:limit]
        servers = await asyncio.to_thread(fetch_vpngate_servers, 100)
        if servers:
            _cache = (time.monotonic(), servers)
        return _cache[1][:limit]


@app.get("/")
def root():
    return {"name": "Findupto Free VPN", "status": "ok", "version": app.version}


@app.get("/health")
def health():
    return {"status": "healthy", "community_nodes": len(nodes), "cached_servers": len(_cache[1])}


@app.get("/api/v1/nodes", response_model=List[Node])
def list_nodes(country: str | None = None):
    now = time.time()
    healthy = [n for n in nodes.values() if n.active and now - n.last_seen < 300]
    if country:
        healthy = [n for n in healthy if n.country.lower() == country.lower()]
    healthy.sort(key=lambda n: (n.country.lower(), n.city.lower()))
    return healthy


@app.get("/api/v1/public/servers", response_model=List[PublicServer])
async def public_servers(country: str | None = None, limit: int = Query(default=30, ge=1, le=100)):
    servers = await get_vpngate_servers(100)
    if country:
        servers = [s for s in servers if s.country.lower() == country.lower()]
    return servers[:limit]


@app.get("/api/v1/public/best", response_model=PublicServer | None)
async def best_public_server(country: str | None = None):
    servers = await get_vpngate_servers(100)
    if country:
        servers = [s for s in servers if s.country.lower() == country.lower()]
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
