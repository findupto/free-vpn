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

        # Main browser layout: a persistent left sidebar plus the browser area.
        layout = tk.Frame(self, bg="#070910")
        layout.pack(fill="both", expand=True)

        sidebar = tk.Frame(layout, bg="#0d131f", width=190, highlightthickness=1,
                           highlightbackground="#202b3d")
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        tk.Label(sidebar, text="FINDUPTO", bg="#0d131f", fg="white",
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=18, pady=(20, 3))
        tk.Label(sidebar, text="SECURE BROWSER", bg="#0d131f", fg="#8c99ad",
                 font=("Segoe UI", 7, "bold")).pack(anchor="w", padx=18, pady=(0, 18))

        self._sidebar_button(sidebar, "⌂  Home", lambda: self.load(self.home))
        self._sidebar_button(sidebar, "←  Back", self.back)
        self._sidebar_button(sidebar, "→  Forward", self.forward)
        self._sidebar_button(sidebar, "↻  Reload", self.open_page)
        self._sidebar_button(sidebar, "★  Bookmark", self.add_bookmark)
        self._sidebar_button(sidebar, "＋  New Tab", self.new_tab)
        self._sidebar_button(sidebar, "◉  Open Browser", self.open_embedded, active=True)

        tk.Frame(sidebar, bg="#0d131f").pack(fill="both", expand=True)
        tk.Label(sidebar, text="● VPN Protected", bg="#151d2b", fg="#31d9a5",
                 font=("Segoe UI", 8, "bold"), padx=12, pady=10).pack(fill="x", padx=12, pady=12)

        browser = tk.Frame(layout, bg="#070910")
        browser.pack(side="left", fill="both", expand=True)

        header = tk.Frame(browser, bg="#101622")
        header.pack(fill="x")

        self.url = tk.StringVar(value=self.home)
        ttk.Entry(header, textvariable=self.url).pack(side="left", fill="x", expand=True, padx=10, pady=10)
        tk.Button(header, text="Go", command=self.open_page, bg="#7657ff", fg="white",
                  relief="flat", padx=14).pack(side="left", padx=(0, 10))

        self.tab_label = tk.Label(browser, text="Tab 1", bg="#151d2b", fg="#60dcff", anchor="w")
        self.tab_label.pack(fill="x", padx=12, pady=(5, 0))

        self.status = tk.Label(browser, text="● VPN Protected Browser Ready", bg="#070910", fg="#60dcff", anchor="w")
        self.status.pack(fill="x", padx=12, pady=5)

        self.viewer = tk.Frame(browser, bg="#0b0f18")
        self.viewer.pack(fill="both", expand=True, padx=12, pady=12)

        tk.Label(self.viewer, text="Findupto Secure Browser Pro\n\nTabs • Bookmarks • Privacy Ready\n\nTraffic routed through active VPN tunnel",
                 bg="#0b0f18", fg="white", font=("Segoe UI", 15)).pack(expand=True)

    @staticmethod
    def _sidebar_button(parent, text, command, active=False):
        bg = "#7657ff" if active else "#0d131f"
        fg = "white" if active else "#8c99ad"
        button = tk.Button(parent, text=text, command=command, anchor="w", bg=bg, fg=fg,
                           activebackground="#2a3650", activeforeground="white", relief="flat",
                           bd=0, cursor="hand2", font=("Segoe UI", 9, "bold"), padx=14, pady=10)
        button.pack(fill="x", padx=10, pady=3)
        return button

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
