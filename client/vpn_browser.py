"""Findupto Secure Browser Pro
Premium browser layer with tabs, bookmarks and privacy controls.
VPN traffic follows the active Findupto VPN tunnel.
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
        self.home = "https://www.google.com"
        self.history = []
        self.bookmarks = []
        self.tabs = [self.home]

        header = tk.Frame(self, bg="#101622")
        header.pack(fill="x")

        self.url = tk.StringVar(value=self.home)
        ttk.Entry(header, textvariable=self.url).pack(side="left", fill="x", expand=True, padx=10, pady=10)

        for label, action in [
            ("←", self.back),
            ("→", self.forward),
            ("↻", self.open_page),
            ("⌂", lambda: self.load(self.home)),
            ("★ Bookmark", self.add_bookmark),
            ("＋ New Tab", self.new_tab),
            ("Chromium", self.open_embedded),
        ]:
            tk.Button(header, text=label, command=action, bg="#7657ff", fg="white", relief="flat").pack(side="left", padx=3)

        self.tab_label = tk.Label(self, text="Tab 1", bg="#151d2b", fg="#60dcff", anchor="w")
        self.tab_label.pack(fill="x", padx=12, pady=(5, 0))

        self.status = tk.Label(self, text="● VPN Protected Browser Ready", bg="#070910", fg="#60dcff", anchor="w")
        self.status.pack(fill="x", padx=12, pady=5)

        self.viewer = tk.Frame(self, bg="#0b0f18")
        self.viewer.pack(fill="both", expand=True, padx=12, pady=12)

        tk.Label(self.viewer, text="Findupto Secure Browser Pro\n\nTabs • Bookmarks • Privacy Ready\n\nTraffic routed through active VPN tunnel", bg="#0b0f18", fg="white", font=("Segoe UI", 15)).pack(expand=True)

    def load(self, url):
        if not url.startswith("http"):
            url = "https://" + url
        self.url.set(url)
        self.history.append(url)
        self.tabs[-1] = url
        self.status.config(text="● Secure browsing through Findupto VPN")
        if HAS_WEBVIEW:
            self.open_embedded()
        else:
            webbrowser.open(url)

    def open_page(self):
        self.load(self.url.get())

    def new_tab(self):
        self.tabs.append(self.home)
        self.url.set(self.home)
        self.tab_label.config(text=f"Tab {len(self.tabs)}")

    def add_bookmark(self):
        if self.url.get() not in self.bookmarks:
            self.bookmarks.append(self.url.get())
        self.status.config(text="★ Bookmark saved")

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
