"""Findupto Secure Browser launcher.

Starts the optional QtWebEngine browser after the VPN client has verified its
tunnel. Chromium networking flags are normalized before QtWebEngine starts so
Windows builds do not inherit an overly restrictive network configuration.
"""
from __future__ import annotations

import os
import tkinter as tk
import webbrowser


def _prepare_qt_network_flags() -> None:
    """Keep privacy-critical Chromium flags without breaking normal HTTPS."""
    current = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "").split()
    remove = {
        "--disable-background-networking",
        "--disable-domain-reliability",
        "--disable-features=PreconnectToSearch",
    }
    current = [flag for flag in current if flag not in remove]
    required = [
        "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
        "--disable-webrtc-multiple-routes",
        "--disable-quic",
    ]
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = " ".join(dict.fromkeys(current + required))


_prepare_qt_network_flags()

try:
    from browser_engine import launch as launch_chromium
except ImportError:
    launch_chromium = None


class VPNBrowser(tk.Toplevel):
    """Open the Findupto Chromium browser from the VPN client."""

    def __init__(self, parent=None, home="https://www.google.com", proxy=""):
        super().__init__(parent)
        self.withdraw()
        self.home = home
        self.proxy = proxy
        self.title("Findupto Secure Browser Pro")
        self._launched = False
        self.after(10, self._launch)

    def _launch(self):
        _prepare_qt_network_flags()
        if launch_chromium:
            try:
                self._launched = bool(launch_chromium(self.home, self.proxy))
            except Exception:
                self._launched = False
        if not self._launched:
            webbrowser.open(self.home)
        self.destroy()


def open_browser(parent=None, home="https://www.google.com", proxy=""):
    """Convenience API used by the VPN dashboard."""
    _prepare_qt_network_flags()
    if launch_chromium:
        try:
            if launch_chromium(home, proxy):
                return True
        except Exception:
            pass
    webbrowser.open(home)
    return False


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    VPNBrowser(root).mainloop()
