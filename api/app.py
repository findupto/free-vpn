import os
import secrets
import time
from typing import Dict, List

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="Findupto Free VPN Directory", version="0.1.0")
API_KEY = os.getenv("FINDUPTO_API_KEY", "change-me")

class Node(BaseModel):
    id: str = Field(min_length=3, max_length=80)
    country: str = Field(min_length=2, max_length=80)
    city: str = Field(min_length=1, max_length=80)
    endpoint: str = Field(min_length=3, max_length=255)
    public_key: str = Field(min_length=20, max_length=100)
    protocol: str = "wireguard"
    active: bool = True
    last_seen: float = 0

nodes: Dict[str, Node] = {}


def require_api_key(x_api_key: str = Header(default="")):
    if not secrets.compare_digest(x_api_key, API_KEY):
        raise HTTPException(status_code=401, detail="invalid API key")


@app.get("/")
def root():
    return {"name": "Findupto Free VPN", "status": "ok"}


@app.get("/health")
def health():
    return {"status": "healthy", "nodes": len(nodes)}


@app.get("/api/v1/nodes", response_model=List[Node])
def list_nodes(country: str | None = None):
    now = time.time()
    healthy = [n for n in nodes.values() if n.active and now - n.last_seen < 300]
    if country:
        healthy = [n for n in healthy if n.country.lower() == country.lower()]
    return healthy


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
