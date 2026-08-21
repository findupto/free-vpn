"""Findupto Secure Browser launcher.

Uses the optional Chromium/QtWebEngine browser engine for real embedded web
content. If QtWebEngine is unavailable, the existing lightweight Tk shell is
used as a safe fallback.
"""
from __future__ import annotations

import tkinter as tk
import webbrowser

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
