"""Realtime server update stream helpers.

Provides a lightweight event stream abstraction for VPN clients to receive
server changes without repeatedly polling the full server registry.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, asdict
from threading import Lock


@dataclass
class ServerEvent:
    event: str
    server_id: str
    payload: dict
    timestamp: int


class RealtimeServerStream:
    def __init__(self):
        self.subscribers = {}
        self.lock = Lock()

    def subscribe(self, client_id: str):
        with self.lock:
            self.subscribers[client_id] = []
        return client_id

    def unsubscribe(self, client_id: str):
        with self.lock:
            self.subscribers.pop(client_id, None)

    def publish(self, event: str, server_id: str, payload: dict):
        message = asdict(ServerEvent(event, server_id, payload, int(time.time())))
        with self.lock:
            for queue in self.subscribers.values():
                queue.append(message)
        return message

    def fetch(self, client_id: str):
        with self.lock:
            events = self.subscribers.get(client_id, [])
            self.subscribers[client_id] = []
        return events


server_stream = RealtimeServerStream()
