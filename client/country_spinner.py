from __future__ import annotations

import random
import threading
import time


class CountrySpinner:
    """Automatic premium VPN route rotation controller.

    The UI layer supplies connect/disconnect callbacks and a verified server
    list. This component handles safe rotation decisions.
    """

    def __init__(self, connect_callback, disconnect_callback):
        self.connect_callback = connect_callback
        self.disconnect_callback = disconnect_callback
        self.enabled = False
        self.interval = 3
        self.thread = None
        self.stop_event = threading.Event()
        self.history = []
        self.current_country = None

    def enable(self, servers_provider, interval=3):
        self.interval = max(3, int(interval))
        self.enabled = True
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._loop, args=(servers_provider,), daemon=True)
        self.thread.start()

    def disable(self):
        self.enabled = False
        self.stop_event.set()

    def _loop(self, servers_provider):
        while not self.stop_event.wait(self.interval):
            servers = [s for s in servers_provider() if s.get("available")]
            if not servers:
                continue

            choices = [s for s in servers if s.get("country") != self.current_country]
            target = random.choice(choices or servers)

            self.disconnect_callback()
            time.sleep(0.5)
            self.connect_callback([target])

            self.current_country = target.get("country")
            self.history.append({
                "country": target.get("country"),
                "city": target.get("city"),
                "time": time.time(),
            })
            self.history = self.history[-20:]
