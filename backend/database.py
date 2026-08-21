"""Small durable SQLite persistence layer for control-plane metadata."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from threading import RLock
from typing import Any


class Database:
    """Persist server/device metadata without requiring an external database."""

    def __init__(self, path: str | Path = ":memory:"):
        self.path = str(path)
        self._lock = RLock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS servers (id TEXT PRIMARY KEY, data TEXT NOT NULL)"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS devices (id TEXT PRIMARY KEY, data TEXT NOT NULL)"
        )
        self._conn.commit()

    def save_server(self, server_id: str, data: dict[str, Any]) -> None:
        payload = json.dumps(data, separators=(",", ":"), sort_keys=True)
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO servers(id,data) VALUES(?,?) "
                "ON CONFLICT(id) DO UPDATE SET data=excluded.data",
                (server_id, payload),
            )

    def get_servers(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute("SELECT id,data FROM servers").fetchall()
        return {server_id: json.loads(data) for server_id, data in rows}

    def register_device(self, device_id: str, data: dict[str, Any]) -> None:
        payload = json.dumps(data, separators=(",", ":"), sort_keys=True)
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO devices(id,data) VALUES(?,?) "
                "ON CONFLICT(id) DO UPDATE SET data=excluded.data",
                (device_id, payload),
            )

    def close(self) -> None:
        with self._lock:
            self._conn.close()
