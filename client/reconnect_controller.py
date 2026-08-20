"""Automatic VPN reconnect controller.

Provides retry, backoff and recovery lifecycle for VPN connections.
"""

import time
from enum import Enum


class ConnectionState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    FAILED = "failed"


class ReconnectController:
    def __init__(self, max_attempts=5, base_delay=2):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.state = ConnectionState.DISCONNECTED
        self.attempts = 0

    def mark_connected(self):
        self.state = ConnectionState.CONNECTED
        self.attempts = 0

    def mark_disconnected(self):
        self.state = ConnectionState.DISCONNECTED

    def reconnect(self, connect_callback):
        self.state = ConnectionState.CONNECTING

        while self.attempts < self.max_attempts:
            self.attempts += 1

            try:
                if connect_callback():
                    self.mark_connected()
                    return True
            except Exception:
                pass

            time.sleep(self.base_delay * self.attempts)

        self.state = ConnectionState.FAILED
        return False

    def status(self):
        return {
            "state": self.state.value,
            "attempts": self.attempts,
        }
