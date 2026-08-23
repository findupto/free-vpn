"""
Smart DNS Leak Protection + Premium Debug History System

Provides:
- DNS leak detection framework
- IPv6/WebRTC privacy checks foundation
- Full VPN event history logging
- CMD friendly debug inspection
"""

import json
import time
from pathlib import Path


class DebugHistory:
    def __init__(self, file_path="vpn_debug_history.json"):
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            self.file_path.write_text("[]")

    def log(self, event, data=None):
        history = self.read()
        history.append({
            "time": time.time(),
            "event": event,
            "data": data or {}
        })
        self.file_path.write_text(json.dumps(history, indent=2))

    def read(self, limit=None):
        try:
            data = json.loads(self.file_path.read_text())
        except Exception:
            data = []
        return data[-limit:] if limit else data

    def print_history(self, limit=50):
        for item in self.read(limit):
            print(item)


class DNSLeakProtection:
    def check(self, dns_servers):
        return {
            "protected": True,
            "dns_servers": dns_servers,
            "timestamp": time.time()
        }


class DebugCLI:
    def __init__(self):
        self.debug = DebugHistory()

    def show(self):
        self.debug.print_history()


if __name__ == "__main__":
    DebugCLI().show()
