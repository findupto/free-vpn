"""Cancellable reconnect controller with bounded exponential backoff and jitter."""

from __future__ import annotations

import random
import time
from enum import Enum


class ConnectionState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    FAILED = "failed"


class ReconnectController:
    def __init__(self, max_attempts=5, base_delay=2, max_delay=30, jitter=0.25):
        self.max_attempts = max(1, int(max_attempts))
        self.base_delay = max(0.0, float(base_delay))
        self.max_delay = max(self.base_delay, float(max_delay))
        self.jitter = max(0.0, min(float(jitter), 1.0))
        self.state = ConnectionState.DISCONNECTED
        self.attempts = 0
        self.last_error = None

    def mark_connected(self):
        self.state = ConnectionState.CONNECTED
        self.attempts = 0
        self.last_error = None

    def mark_disconnected(self):
        self.state = ConnectionState.DISCONNECTED

    def reconnect(self, connect_callback, cancel_callback=None, sleep=time.sleep):
        self.state = ConnectionState.CONNECTING
        self.last_error = None
        for attempt in range(1, self.max_attempts + 1):
            self.attempts = attempt
            if cancel_callback and cancel_callback():
                self.state = ConnectionState.DISCONNECTED
                return False
            try:
                if connect_callback():
                    self.mark_connected()
                    return True
            except Exception as exc:
                self.last_error = f"{type(exc).__name__}: {exc}"
            if attempt < self.max_attempts:
                delay = min(self.max_delay, self.base_delay * (2 ** (attempt - 1)))
                delay *= 1 + random.uniform(-self.jitter, self.jitter)
                sleep(max(0.0, delay))
        self.state = ConnectionState.FAILED
        return False

    def status(self):
        return {"state": self.state.value, "attempts": self.attempts, "last_error": self.last_error}
