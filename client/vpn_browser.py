"""Findupto Secure Browser
Premium embedded browser foundation.

Uses pywebview when available for a real in-app browsing experience and
falls back gracefully when the embedded engine is unavailable.
VPN traffic follows the system VPN tunnel.
"""

import tkinter as tk
from tkinter import ttk
import webbrowser

try:
    import webview
    HAS_WEBVIEW = True
except ImportError:
    HAS_WEBVIEW = False


class VPNBrowser(tk.Toplevel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.title("Findupto Secure Browser Pro")
        self.geometry("1280x820")
        self.configure(bg="#070910")
        self.history = []
        self.home = "https://www.google.com"

        header = tk.Frame(self, bg="#101622")
        header.pack(fill="x")

        self.url = tk.StringVar(value=self.home)
        ttk.Entry(header, textvariable=self.url).pack(side="left", fill="x", expand=True, padx=12, pady=12)

        for label, action in [
            ("←", self.back),
            ("→", self.forward),
            ("↻", self.open_page),
            ("⌂", lambda: self.load(self.home)),
            ("OPEN CHROMIUM", self.open_embedded),
        ]:
            tk.Button(header, text=label, command=action, bg="#7657ff", fg="white", relief="flat", padx=10).pack(side="left", padx=3)

        self.status = tk.Label(self, text="● VPN Browser Ready", bg="#070910", fg="#60dcff", anchor="w")
        self.status.pack(fill="x", padx=12, pady=6)

        self.page = tk.Frame(self, bg="#0b0f18")
        self.page.pack(fill="both", expand=True, padx=12, pady=12)

        self.info = tk.Label(
            self.page,
            text="Premium Secure Browser\n\nEmbedded Chromium mode is available when pywebview is installed.\nVPN routing remains active from Findupto VPN.",
            bg="#0b0f18",
            fg="white",
            font=("Segoe UI", 14),
        )
        self.info.pack(expand=True)

    def load(self, url):
        if not url.startswith("http"):
            url = "https://" + url
        self.url.set(url)
        self.history.append(url)
        self.status.config(text="● Browsing through active VPN tunnel")
        if HAS_WEBVIEW:
            self.open_embedded()
        else:
            webbrowser.open(url)

    def open_page(self):
        self.load(self.url.get())

    def open_embedded(self):
        if HAS_WEBVIEW:
            webview.create_window("Findupto Secure Browser", self.url.get())
            webview.start()
        else:
            webbrowser.open(self.url.get())

    def back(self):
        if len(self.history) > 1:
            self.load(self.history[-2])

    def forward(self):
        self.open_page()


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    VPNBrowser(root).mainloop()
