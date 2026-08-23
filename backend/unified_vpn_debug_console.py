"""
Unified VPN Debug Console
Live CMD monitoring layer for VPN operations.
"""

import json
import time
from datetime import datetime


class UnifiedVPNDebugConsole:
    def __init__(self):
        self.events = []

    def record(self, category, message, data=None):
        event = {
            "time": datetime.utcnow().isoformat(),
            "category": category,
            "message": message,
            "data": data or {}
        }
        self.events.append(event)
        return event

    def get_history(self, limit=100):
        return self.events[-limit:]

    def dashboard(self):
        return {
            "events": len(self.events),
            "latest": self.get_history(20),
            "status": "running",
            "timestamp": datetime.utcnow().isoformat()
        }

    def cmd_view(self):
        data = self.dashboard()
        print(json.dumps(data, indent=2))

    def watch(self, interval=5):
        while True:
            self.cmd_view()
            time.sleep(interval)


_debug_console = UnifiedVPNDebugConsole()


def debug_log(category, message, data=None):
    return _debug_console.record(category, message, data)
