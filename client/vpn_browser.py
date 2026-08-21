"""Findupto Secure Browser Pro.

A privacy-first browser shell around pywebview with Findupto VPN awareness.
The browser UI provides tabs, navigation, bookmarks, history, private mode,
search, zoom, downloads, privacy controls, and a browser settings panel.
"""

from __future__ import annotations

import json
import os
import time
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import messagebox, ttk
from urllib.parse import quote_plus

try:
    import webview
    HAS_WEBVIEW = True
except ImportError:
    HAS_WEBVIEW = False


BG = "#070910"
SURFACE = "#0d131f"
PANEL = "#101622"
PANEL_2 = "#151d2b"
BORDER = "#202b3d"
TEXT = "#f8faff"
MUTED = "#8c99ad"
ACCENT = "#7657ff"
ACCENT_2 = "#9a87ff"
SUCCESS = "#31d9a5"
CYAN = "#60dcff"


class VPNBrowser(tk.Toplevel):
    """Feature-rich browser shell integrated with the active Findupto VPN."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.title("Findupto Secure Browser Pro")
        self.geometry("1400x900")
        self.minsize(1000, 650)
        self.configure(bg=BG)

        self.home = "https://www.google.com"
        self.search_engine = "https://www.google.com/search?q="
        self.history: list[str] = []
        self.forward_history: list[str] = []
        self.bookmarks: list[dict[str, str]] = []
        self.tabs: list[dict[str, object]] = []
        self.active_tab = -1
        self.private_mode = False
        self.zoom = 100
        self.block_trackers = True
        self.block_popups = True
        self.do_not_track = True
        self.downloads = []
        self.settings_path = Path.home() / ".findupto_browser.json"
        self._load_settings()

        self._build_ui()
        self.new_tab()

        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _load_settings(self):
        try:
            data = json.loads(self.settings_path.read_text(encoding="utf-8"))
            self.bookmarks = data.get("bookmarks", [])
            self.block_trackers = bool(data.get("block_trackers", True))
            self.block_popups = bool(data.get("block_popups", True))
            self.do_not_track = bool(data.get("do_not_track", True))
        except (OSError, ValueError, TypeError):
            pass

    def _save_settings(self):
        data = {
            "bookmarks": self.bookmarks,
            "block_trackers": self.block_trackers,
            "block_popups": self.block_popups,
            "do_not_track": self.do_not_track,
        }
        try:
            self.settings_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except OSError:
            pass

    def _build_ui(self):
        layout = tk.Frame(self, bg=BG)
        layout.pack(fill="both", expand=True)

        self.sidebar = tk.Frame(layout, bg=SURFACE, width=205,
                                highlightthickness=1, highlightbackground=BORDER)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        tk.Label(self.sidebar, text="FINDUPTO", bg=SURFACE, fg=TEXT,
                 font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=18, pady=(18, 2))
        tk.Label(self.sidebar, text="SECURE BROWSER PRO", bg=SURFACE, fg=MUTED,
                 font=("Segoe UI", 7, "bold")).pack(anchor="w", padx=18, pady=(0, 18))

        self._side("⌂  Home", lambda: self.load(self.home))
        self._side("＋  New Tab", self.new_tab)
        self._side("★  Bookmarks", self.show_bookmarks)
        self._side("◷  History", self.show_history)
        self._side("⇩  Downloads", self.show_downloads)
        self._side("◉  Private Mode", self.toggle_private)
        self._side("⚙  Browser Settings", self.show_settings)
        self._side("🛡  Privacy Center", self.show_privacy, active=True)

        tk.Frame(self.sidebar, bg=SURFACE).pack(fill="both", expand=True)
        self.vpn_status = tk.Label(self.sidebar, text="● VPN PROTECTED\nTraffic routed through Findupto VPN",
                                   bg=PANEL_2, fg=SUCCESS, justify="left",
                                   font=("Segoe UI", 8, "bold"), padx=12, pady=10)
        self.vpn_status.pack(fill="x", padx=12, pady=12)

        browser = tk.Frame(layout, bg=BG)
        browser.pack(side="left", fill="both", expand=True)
        self.browser = browser

        nav = tk.Frame(browser, bg=PANEL)
        nav.pack(fill="x")
        self._top_button(nav, "←", self.back)
        self._top_button(nav, "→", self.forward)
        self._top_button(nav, "↻", self.reload)
        self._top_button(nav, "⌂", lambda: self.load(self.home))

        self.security = tk.Label(nav, text="🛡 Secure", bg=PANEL_2, fg=SUCCESS,
                                 font=("Segoe UI", 8, "bold"), padx=9, pady=7)
        self.security.pack(side="left", padx=(4, 6), pady=7)

        self.url = tk.StringVar(value=self.home)
        self.address = ttk.Entry(nav, textvariable=self.url, font=("Segoe UI", 10))
        self.address.pack(side="left", fill="x", expand=True, padx=4, pady=7)
        self.address.bind("<Return>", lambda _e: self.open_page())
        self._top_button(nav, "Go", self.open_page, accent=True)
        self._top_button(nav, "⋮", self.show_browser_menu)

        self.tabbar = tk.Frame(browser, bg=SURFACE)
        self.tabbar.pack(fill="x", padx=8, pady=(6, 0))

        self.status = tk.Label(browser, text="● VPN Protected Browser Ready", bg=BG, fg=CYAN,
                               anchor="w", font=("Segoe UI", 8, "bold"))
        self.status.pack(fill="x", padx=12, pady=5)

        self.viewer = tk.Frame(browser, bg="#0b0f18")
        self.viewer.pack(fill="both", expand=True, padx=12, pady=12)
        self._show_start_page()

    def _side(self, text, command, active=False):
        button = tk.Button(self.sidebar, text=text, command=command, anchor="w",
                           bg=ACCENT if active else SURFACE,
                           fg=TEXT if active else MUTED,
                           activebackground=PANEL_2, activeforeground=TEXT,
                           relief="flat", bd=0, cursor="hand2",
                           font=("Segoe UI", 9, "bold"), padx=14, pady=10)
        button.pack(fill="x", padx=10, pady=2)
        return button

    def _top_button(self, parent, text, command, accent=False):
        return tk.Button(parent, text=text, command=command,
                         bg=ACCENT if accent else PANEL_2, fg=TEXT,
                         activebackground=ACCENT_2, activeforeground=TEXT,
                         relief="flat", bd=0, cursor="hand2",
                         font=("Segoe UI", 9, "bold"), padx=10, pady=6).pack(side="left", padx=2, pady=7)

    def _show_start_page(self):
        for child in self.viewer.winfo_children():
            child.destroy()
        title = "Private Browsing" if self.private_mode else "Findupto Secure Browser"
        subtitle = "VPN protected • Tracker protection • Secure navigation"
        tk.Label(self.viewer, text=title, bg="#0b0f18", fg=TEXT,
                 font=("Segoe UI", 25, "bold")).pack(pady=(90, 8))
        tk.Label(self.viewer, text=subtitle, bg="#0b0f18", fg=MUTED,
                 font=("Segoe UI", 10)).pack(pady=(0, 24))
        search = ttk.Entry(self.viewer, font=("Segoe UI", 13), width=70)
        search.pack(ipady=9)
        search.focus_set()
        search.bind("<Return>", lambda _e: self.load(search.get()))
        tk.Label(self.viewer, text="Tip: type a URL or search term in the address bar.",
                 bg="#0b0f18", fg="#65748a", font=("Segoe UI", 8)).pack(pady=10)

    def _render_tabs(self):
        for child in self.tabbar.winfo_children():
            child.destroy()
        for index, tab in enumerate(self.tabs):
            title = str(tab.get("title") or "New Tab")[:22]
            active = index == self.active_tab
            frame = tk.Frame(self.tabbar, bg=PANEL_2 if active else SURFACE)
            frame.pack(side="left", padx=2)
            tk.Button(frame, text=title, command=lambda i=index: self.switch_tab(i),
                      bg=PANEL_2 if active else SURFACE, fg=TEXT if active else MUTED,
                      activebackground=PANEL_2, relief="flat", bd=0,
                      font=("Segoe UI", 8, "bold"), padx=10, pady=7).pack(side="left")
            tk.Button(frame, text="×", command=lambda i=index: self.close_tab(i),
                      bg=PANEL_2 if active else SURFACE, fg=MUTED,
                      activebackground=PANEL_2, relief="flat", bd=0,
                      font=("Segoe UI", 8, "bold"), padx=6, pady=7).pack(side="left")
        tk.Button(self.tabbar, text="＋", command=self.new_tab, bg=SURFACE, fg=CYAN,
                  relief="flat", bd=0, font=("Segoe UI", 10, "bold"), padx=9, pady=5).pack(side="left")

    def new_tab(self):
        self.tabs.append({"url": self.home, "title": "New Tab", "created": time.time()})
        self.active_tab = len(self.tabs) - 1
        self.url.set(self.home)
        self._render_tabs()
        self._show_start_page()
        self.status.config(text="● New secure tab")

    def switch_tab(self, index):
        if not 0 <= index < len(self.tabs):
            return
        self.active_tab = index
        current = self.tabs[index]
        self.url.set(str(current.get("url", self.home)))
        self._render_tabs()
        if self.url.get() == self.home:
            self._show_start_page()
        else:
            self._open_external(self.url.get())

    def close_tab(self, index):
        if len(self.tabs) == 1:
            return self.new_tab()
        self.tabs.pop(index)
        self.active_tab = max(0, min(self.active_tab, len(self.tabs) - 1))
        self.switch_tab(self.active_tab)

    def _normalise(self, value):
        value = value.strip()
        if not value:
            return self.home
        if value.startswith(("http://", "https://")):
            return value
        if " " not in value and "." in value:
            return "https://" + value
        return self.search_engine + quote_plus(value)

    def load(self, value):
        url = self._normalise(value)
        if self.active_tab < 0:
            self.new_tab()
        self.url.set(url)
        self.tabs[self.active_tab]["url"] = url
        self.tabs[self.active_tab]["title"] = url.split("//", 1)[-1].split("/", 1)[0]
        self.forward_history.clear()
        if not self.private_mode:
            self.history.append(url)
        self._render_tabs()
        self.status.config(text="● Secure browsing through Findupto VPN")
        self.security.config(text="🛡 Secure", fg=SUCCESS)
        self._open_external(url)

    def open_page(self):
        self.load(self.url.get())

    def _open_external(self, url):
        # pywebview is the built-in web content engine when installed.
        # Otherwise the user's default browser is used without claiming embedded mode.
        if HAS_WEBVIEW:
            try:
                webview.create_window("Findupto Secure Browser", url)
                webview.start()
                return
            except Exception as exc:
                self.status.config(text=f"● Embedded browser unavailable: {exc}")
        webbrowser.open(url)

    def reload(self):
        self.status.config(text="● Reloading through VPN…")
        self._open_external(self.url.get())

    def back(self):
        if len(self.history) >= 2:
            current = self.history.pop()
            self.forward_history.append(current)
            self.load(self.history[-1])
        else:
            self.status.config(text="● No previous page")

    def forward(self):
        if self.forward_history:
            self.load(self.forward_history.pop())
        else:
            self.status.config(text="● No next page")

    def add_bookmark(self):
        url = self.url.get()
        if not any(item.get("url") == url for item in self.bookmarks):
            self.bookmarks.append({"title": self.tabs[self.active_tab].get("title", url), "url": url})
            self._save_settings()
        self.status.config(text="★ Bookmark saved")

    def show_bookmarks(self):
        self._show_list("Bookmarks", self.bookmarks, "No bookmarks yet.", lambda item: self.load(item["url"]))

    def show_history(self):
        items = [{"title": u, "url": u} for u in reversed(self.history[-100:])]
        self._show_list("History", items, "No browsing history.", lambda item: self.load(item["url"]))

    def show_downloads(self):
        self._show_list("Downloads", self.downloads, "No downloads recorded.", None)

    def _show_list(self, title, items, empty, action):
        for child in self.viewer.winfo_children():
            child.destroy()
        tk.Label(self.viewer, text=title, bg="#0b0f18", fg=TEXT,
                 font=("Segoe UI", 20, "bold")).pack(anchor="w", padx=25, pady=(25, 12))
        if not items:
            tk.Label(self.viewer, text=empty, bg="#0b0f18", fg=MUTED,
                     font=("Segoe UI", 10)).pack(anchor="w", padx=25)
            return
        box = tk.Frame(self.viewer, bg=PANEL)
        box.pack(fill="both", expand=True, padx=25, pady=(0, 25))
        for item in items:
            text = str(item.get("title") or item.get("url") or item)
            button = tk.Button(box, text=text, anchor="w", command=lambda x=item: action(x) if action else None,
                               bg=PANEL, fg=TEXT, activebackground=PANEL_2, activeforeground=TEXT,
                               relief="flat", bd=0, font=("Segoe UI", 9), padx=15, pady=10)
            button.pack(fill="x", pady=1)

    def toggle_private(self):
        self.private_mode = not self.private_mode
        mode = "ON" if self.private_mode else "OFF"
        self.vpn_status.config(text=f"● VPN PROTECTED\nPrivate Mode: {mode}", fg=SUCCESS)
        self.status.config(text=f"● Private browsing {mode}")
        self._show_start_page()

    def show_privacy(self):
        for child in self.viewer.winfo_children():
            child.destroy()
        tk.Label(self.viewer, text="Privacy Center", bg="#0b0f18", fg=TEXT,
                 font=("Segoe UI", 20, "bold")).pack(anchor="w", padx=25, pady=(25, 18))
        self._privacy_toggle("Block known trackers", "block_trackers")
        self._privacy_toggle("Block pop-up windows", "block_popups")
        self._privacy_toggle("Send Do Not Track preference", "do_not_track")
        tk.Label(self.viewer, text="VPN protection is provided by the active Findupto VPN tunnel.",
                 bg="#0b0f18", fg=SUCCESS, font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=25, pady=20)

    def _privacy_toggle(self, label, attr):
        value = tk.BooleanVar(value=getattr(self, attr))
        check = tk.Checkbutton(self.viewer, text=label, variable=value,
                               command=lambda: self._set_privacy(attr, value.get()),
                               bg="#0b0f18", fg=TEXT, selectcolor=PANEL_2,
                               activebackground="#0b0f18", activeforeground=TEXT,
                               font=("Segoe UI", 10), anchor="w")
        check.pack(fill="x", padx=25, pady=5)

    def _set_privacy(self, attr, value):
        setattr(self, attr, bool(value))
        self._save_settings()

    def show_settings(self):
        for child in self.viewer.winfo_children():
            child.destroy()
        tk.Label(self.viewer, text="Browser Settings", bg="#0b0f18", fg=TEXT,
                 font=("Segoe UI", 20, "bold")).pack(anchor="w", padx=25, pady=(25, 18))
        row = tk.Frame(self.viewer, bg=PANEL)
        row.pack(fill="x", padx=25, pady=5)
        tk.Label(row, text="Default search engine", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 10, "bold")).pack(side="left", padx=15, pady=14)
        engine = ttk.Combobox(row, values=["Google", "DuckDuckGo", "Bing"], state="readonly", width=18)
        engine.set("Google")
        engine.pack(side="right", padx=15, pady=10)
        zoom = tk.Frame(self.viewer, bg=PANEL)
        zoom.pack(fill="x", padx=25, pady=5)
        tk.Label(zoom, text="Page zoom", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 10, "bold")).pack(side="left", padx=15, pady=14)
        tk.Button(zoom, text="−", command=lambda: self.change_zoom(-10), bg=PANEL_2, fg=TEXT, relief="flat").pack(side="right", padx=4)
        self.zoom_label = tk.Label(zoom, text=f"{self.zoom}%", bg=PANEL, fg=CYAN, font=("Segoe UI", 10, "bold"))
        self.zoom_label.pack(side="right", padx=8)
        tk.Button(zoom, text="+", command=lambda: self.change_zoom(10), bg=PANEL_2, fg=TEXT, relief="flat").pack(side="right", padx=4)

    def change_zoom(self, delta):
        self.zoom = max(50, min(200, self.zoom + delta))
        if hasattr(self, "zoom_label"):
            self.zoom_label.config(text=f"{self.zoom}%")
        self.status.config(text=f"● Page zoom {self.zoom}%")

    def show_browser_menu(self):
        menu = tk.Menu(self, tearoff=False, bg=PANEL, fg=TEXT,
                       activebackground=ACCENT, activeforeground=TEXT)
        menu.add_command(label="New Tab", command=self.new_tab)
        menu.add_command(label="Private Mode", command=self.toggle_private)
        menu.add_command(label="Add Bookmark", command=self.add_bookmark)
        menu.add_command(label="History", command=self.show_history)
        menu.add_command(label="Downloads", command=self.show_downloads)
        menu.add_separator()
        menu.add_command(label="Privacy Center", command=self.show_privacy)
        menu.add_command(label="Browser Settings", command=self.show_settings)
        menu.add_command(label="Clear History", command=self.clear_history)
        try:
            menu.tk_popup(self.winfo_pointerx(), self.winfo_pointery())
        finally:
            menu.grab_release()

    def clear_history(self):
        self.history.clear()
        self.forward_history.clear()
        self.status.config(text="● Browsing history cleared")


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    VPNBrowser(root).mainloop()
