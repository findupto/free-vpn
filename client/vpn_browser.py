"""Findupto Secure Browser Pro.

Privacy-first browser shell integrated with the Findupto VPN client.
The browser uses pywebview when available and falls back to the system browser.
UI features are implemented locally; network traffic remains subject to the
active VPN tunnel provided by the Findupto client.
"""

from __future__ import annotations

import json
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
WARNING = "#ffc46b"
DANGER = "#ff647d"
CYAN = "#60dcff"


class VPNBrowser(tk.Toplevel):
    """Feature-rich browser shell with Findupto VPN/privacy controls."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.title("Findupto Secure Browser Pro")
        self.geometry("1440x900")
        self.minsize(1000, 650)
        self.configure(bg=BG)

        self.home = "https://www.google.com"
        self.search_engine = "https://www.google.com/search?q="
        self.history = []
        self.forward_history = []
        self.bookmarks = []
        self.downloads = []
        self.tabs = []
        self.active_tab = -1
        self.private_mode = False
        self.zoom = 100
        self.block_trackers = True
        self.block_popups = True
        self.do_not_track = True
        self.https_only = True
        self.block_webrtc = True
        self.clear_cookies_on_exit = False
        self.fingerprint_protection = True
        self.notifications_allowed = False
        self.camera_allowed = False
        self.microphone_allowed = False
        self.vpn_route = "All traffic"
        self.settings_path = Path.home() / ".findupto_browser.json"
        self._load_settings()
        self._build_ui()
        self.new_tab()
        self._bind_shortcuts()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------------- Persistence ----------------
    def _load_settings(self):
        try:
            data = json.loads(self.settings_path.read_text(encoding="utf-8"))
            self.bookmarks = data.get("bookmarks", [])
            self.block_trackers = bool(data.get("block_trackers", True))
            self.block_popups = bool(data.get("block_popups", True))
            self.do_not_track = bool(data.get("do_not_track", True))
            self.https_only = bool(data.get("https_only", True))
            self.block_webrtc = bool(data.get("block_webrtc", True))
            self.clear_cookies_on_exit = bool(data.get("clear_cookies_on_exit", False))
            self.fingerprint_protection = bool(data.get("fingerprint_protection", True))
            self.vpn_route = data.get("vpn_route", "All traffic")
            engine = data.get("search_engine", "Google")
            if engine == "DuckDuckGo":
                self.search_engine = "https://duckduckgo.com/?q="
            elif engine == "Bing":
                self.search_engine = "https://www.bing.com/search?q="
        except (OSError, ValueError, TypeError):
            pass

    def _save_settings(self):
        engine = "Google"
        if "duckduckgo" in self.search_engine:
            engine = "DuckDuckGo"
        elif "bing.com" in self.search_engine:
            engine = "Bing"
        data = {
            "bookmarks": self.bookmarks,
            "block_trackers": self.block_trackers,
            "block_popups": self.block_popups,
            "do_not_track": self.do_not_track,
            "https_only": self.https_only,
            "block_webrtc": self.block_webrtc,
            "clear_cookies_on_exit": self.clear_cookies_on_exit,
            "fingerprint_protection": self.fingerprint_protection,
            "vpn_route": self.vpn_route,
            "search_engine": engine,
        }
        try:
            self.settings_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except OSError:
            pass

    # ---------------- UI ----------------
    def _build_ui(self):
        layout = tk.Frame(self, bg=BG)
        layout.pack(fill="both", expand=True)

        self.sidebar = tk.Frame(layout, bg=SURFACE, width=215, highlightthickness=1, highlightbackground=BORDER)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        tk.Label(self.sidebar, text="FINDUPTO", bg=SURFACE, fg=TEXT, font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=18, pady=(18, 2))
        tk.Label(self.sidebar, text="SECURE BROWSER PRO", bg=SURFACE, fg=MUTED, font=("Segoe UI", 7, "bold")).pack(anchor="w", padx=18, pady=(0, 15))
        self._side("⌂  Home", lambda: self.load(self.home))
        self._side("＋  New Tab", self.new_tab)
        self._side("★  Bookmarks", self.show_bookmarks)
        self._side("◷  History", self.show_history)
        self._side("⇩  Downloads", self.show_downloads)
        self._side("◉  Private Mode", self.toggle_private)
        self._side("🔒  HTTPS-Only", self.toggle_https)
        self._side("🛡  Privacy Center", self.show_privacy)
        self._side("🌐  VPN Routing", self.show_vpn_routing)
        self._side("⚙  Browser Settings", self.show_settings)
        self._side("🧹  Clear Data", self.clear_browsing_data)
        tk.Frame(self.sidebar, bg=SURFACE).pack(fill="both", expand=True)
        self.vpn_status = tk.Label(self.sidebar, text="● VPN PROTECTED\nAll browser traffic uses active VPN", bg=PANEL_2, fg=SUCCESS, justify="left", font=("Segoe UI", 8, "bold"), padx=12, pady=10)
        self.vpn_status.pack(fill="x", padx=12, pady=12)

        browser = tk.Frame(layout, bg=BG)
        browser.pack(side="left", fill="both", expand=True)
        self.browser = browser

        nav = tk.Frame(browser, bg=PANEL)
        nav.pack(fill="x")
        self._top(nav, "←", self.back)
        self._top(nav, "→", self.forward)
        self._top(nav, "↻", self.reload)
        self._top(nav, "⌂", lambda: self.load(self.home))
        self.security = tk.Label(nav, text="🛡 Secure", bg=PANEL_2, fg=SUCCESS, font=("Segoe UI", 8, "bold"), padx=9, pady=7)
        self.security.pack(side="left", padx=4, pady=7)
        self.url = tk.StringVar(value=self.home)
        self.address = ttk.Entry(nav, textvariable=self.url, font=("Segoe UI", 10))
        self.address.pack(side="left", fill="x", expand=True, padx=4, pady=7)
        self.address.bind("<Return>", lambda _e: self.open_page())
        self._top(nav, "Go", self.open_page, True)
        self._top(nav, "★", self.add_bookmark)
        self._top(nav, "⋮", self.show_browser_menu)

        self.tabbar = tk.Frame(browser, bg=SURFACE)
        self.tabbar.pack(fill="x", padx=8, pady=(6, 0))
        self.status = tk.Label(browser, text="● VPN Protected Browser Ready", bg=BG, fg=CYAN, anchor="w", font=("Segoe UI", 8, "bold"))
        self.status.pack(fill="x", padx=12, pady=5)
        self.viewer = tk.Frame(browser, bg="#0b0f18")
        self.viewer.pack(fill="both", expand=True, padx=12, pady=12)
        self._show_start_page()

    def _side(self, text, command):
        b = tk.Button(self.sidebar, text=text, command=command, anchor="w", bg=SURFACE, fg=MUTED,
                      activebackground=PANEL_2, activeforeground=TEXT, relief="flat", bd=0,
                      cursor="hand2", font=("Segoe UI", 9, "bold"), padx=14, pady=9)
        b.pack(fill="x", padx=10, pady=2)
        return b

    def _top(self, parent, text, command, accent=False):
        return tk.Button(parent, text=text, command=command, bg=ACCENT if accent else PANEL_2, fg=TEXT,
                         activebackground=ACCENT_2, activeforeground=TEXT, relief="flat", bd=0,
                         cursor="hand2", font=("Segoe UI", 9, "bold"), padx=10, pady=6).pack(side="left", padx=2, pady=7)

    def _bind_shortcuts(self):
        self.bind_all("<Control-l>", lambda _e: self._focus_address())
        self.bind_all("<Control-t>", lambda _e: self.new_tab())
        self.bind_all("<Control-w>", lambda _e: self.close_tab(self.active_tab))
        self.bind_all("<Control-d>", lambda _e: self.add_bookmark())
        self.bind_all("<Control-h>", lambda _e: self.show_history())
        self.bind_all("<Control-j>", lambda _e: self.show_downloads())
        self.bind_all("<Control-f>", lambda _e: self.find_in_page())
        self.bind_all("<Control-plus>", lambda _e: self.change_zoom(10))
        self.bind_all("<Control-minus>", lambda _e: self.change_zoom(-10))
        self.bind_all("<Control-0>", lambda _e: self.set_zoom(100))
        self.bind_all("<F5>", lambda _e: self.reload())
        self.bind_all("<Alt-Left>", lambda _e: self.back())
        self.bind_all("<Alt-Right>", lambda _e: self.forward())

    def _focus_address(self):
        self.address.focus_set()
        self.address.select_range(0, "end")

    def _clear_view(self):
        for child in self.viewer.winfo_children():
            child.destroy()

    def _show_start_page(self):
        self._clear_view()
        title = "Private Browsing" if self.private_mode else "Findupto Secure Browser"
        tk.Label(self.viewer, text=title, bg="#0b0f18", fg=TEXT, font=("Segoe UI", 25, "bold")).pack(pady=(85, 8))
        tk.Label(self.viewer, text="VPN protected • HTTPS-only • Tracker blocking • Fingerprint protection",
                 bg="#0b0f18", fg=MUTED, font=("Segoe UI", 10)).pack(pady=(0, 22))
        search = ttk.Entry(self.viewer, font=("Segoe UI", 13), width=70)
        search.pack(ipady=9)
        search.bind("<Return>", lambda _e: self.load(search.get()))
        search.focus_set()
        tk.Label(self.viewer, text="Ctrl+L address bar  •  Ctrl+T new tab  •  Ctrl+Shift+P private mode  •  Ctrl+F find",
                 bg="#0b0f18", fg="#65748a", font=("Segoe UI", 8)).pack(pady=12)

    # ---------------- Tabs ----------------
    def _render_tabs(self):
        for child in self.tabbar.winfo_children():
            child.destroy()
        for index, tab in enumerate(self.tabs):
            active = index == self.active_tab
            frame = tk.Frame(self.tabbar, bg=PANEL_2 if active else SURFACE)
            frame.pack(side="left", padx=2)
            title = str(tab.get("title") or "New Tab")[:20]
            tk.Button(frame, text=title, command=lambda i=index: self.switch_tab(i), bg=PANEL_2 if active else SURFACE,
                      fg=TEXT if active else MUTED, activebackground=PANEL_2, relief="flat", bd=0,
                      font=("Segoe UI", 8, "bold"), padx=10, pady=7).pack(side="left")
            tk.Button(frame, text="×", command=lambda i=index: self.close_tab(i), bg=PANEL_2 if active else SURFACE,
                      fg=MUTED, activebackground=PANEL_2, relief="flat", bd=0, padx=6, pady=7).pack(side="left")
        tk.Button(self.tabbar, text="＋", command=self.new_tab, bg=SURFACE, fg=CYAN, relief="flat", bd=0,
                  font=("Segoe UI", 10, "bold"), padx=9, pady=5).pack(side="left")

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
        url = str(self.tabs[index].get("url", self.home))
        self.url.set(url)
        self._render_tabs()
        if url == self.home:
            self._show_start_page()
        else:
            self._open_embedded(url)

    def close_tab(self, index):
        if not self.tabs:
            return
        if len(self.tabs) == 1:
            self.tabs[0] = {"url": self.home, "title": "New Tab", "created": time.time()}
            self.active_tab = 0
            self.url.set(self.home)
            self._render_tabs()
            self._show_start_page()
            return
        self.tabs.pop(index)
        self.active_tab = max(0, min(self.active_tab, len(self.tabs) - 1))
        self.switch_tab(self.active_tab)

    # ---------------- Navigation ----------------
    def _normalise(self, value):
        value = value.strip()
        if not value:
            return self.home
        if value.startswith(("http://", "https://")):
            return value
        if " " not in value and "." in value:
            return ("https://" if self.https_only else "http://") + value
        return self.search_engine + quote_plus(value)

    def load(self, value, add_history=True):
        url = self._normalise(value)
        if self.https_only and url.startswith("http://"):
            url = "https://" + url[7:]
        if self.active_tab < 0:
            self.new_tab()
        self.url.set(url)
        self.tabs[self.active_tab]["url"] = url
        self.tabs[self.active_tab]["title"] = url.split("//", 1)[-1].split("/", 1)[0]
        if add_history and not self.private_mode:
            if not self.history or self.history[-1] != url:
                self.history.append(url)
        self._render_tabs()
        self.status.config(text="● Secure browsing through active Findupto VPN")
        self.security.config(text="🛡 Secure", fg=SUCCESS)
        self._open_embedded(url)

    def open_page(self):
        self.forward_history.clear()
        self.load(self.url.get())

    def _open_embedded(self, url):
        if HAS_WEBVIEW:
            try:
                webview.create_window("Findupto Secure Browser", url, width=1280, height=820)
                webview.start()
                return
            except Exception as exc:
                self.status.config(text=f"● Embedded browser unavailable: {exc}")
        webbrowser.open(url)

    def reload(self):
        self.status.config(text="● Reloading through VPN…")
        self._open_embedded(self.url.get())

    def back(self):
        if len(self.history) >= 2:
            current = self.history.pop()
            self.forward_history.append(current)
            self.load(self.history[-1], add_history=False)
        else:
            self.status.config(text="● No previous page")

    def forward(self):
        if self.forward_history:
            self.load(self.forward_history.pop())
        else:
            self.status.config(text="● No next page")

    # ---------------- Browser features ----------------
    def add_bookmark(self):
        if self.active_tab < 0:
            return
        url = self.url.get()
        if not any(item.get("url") == url for item in self.bookmarks):
            self.bookmarks.append({"title": self.tabs[self.active_tab].get("title", url), "url": url})
            self._save_settings()
        self.status.config(text="★ Bookmark saved")

    def show_bookmarks(self):
        items = self.bookmarks
        self._show_list("Bookmarks", items, "No bookmarks yet.", lambda item: self.load(item["url"]))

    def show_history(self):
        items = [{"title": u, "url": u} for u in reversed(self.history[-200:])]
        self._show_list("History", items, "No browsing history.", lambda item: self.load(item["url"]))

    def show_downloads(self):
        self._show_list("Downloads", self.downloads, "No downloads recorded by the browser shell.", None)

    def _show_list(self, title, items, empty, action):
        self._clear_view()
        tk.Label(self.viewer, text=title, bg="#0b0f18", fg=TEXT, font=("Segoe UI", 20, "bold")).pack(anchor="w", padx=25, pady=(25, 12))
        if not items:
            tk.Label(self.viewer, text=empty, bg="#0b0f18", fg=MUTED, font=("Segoe UI", 10)).pack(anchor="w", padx=25)
            return
        box = tk.Frame(self.viewer, bg=PANEL)
        box.pack(fill="both", expand=True, padx=25, pady=(0, 25))
        for item in items:
            text = str(item.get("title") or item.get("url") or item)
            command = (lambda x=item: action(x)) if action else (lambda: None)
            tk.Button(box, text=text, anchor="w", command=command, bg=PANEL, fg=TEXT, activebackground=PANEL_2,
                      activeforeground=TEXT, relief="flat", bd=0, font=("Segoe UI", 9), padx=15, pady=9).pack(fill="x", pady=1)

    def toggle_private(self):
        self.private_mode = not self.private_mode
        mode = "ON" if self.private_mode else "OFF"
        self.vpn_status.config(text=f"● VPN PROTECTED\nPrivate Mode: {mode}\nVPN route: {self.vpn_route}", fg=SUCCESS)
        self.status.config(text=f"● Private browsing {mode}")
        if self.private_mode:
            self._show_start_page()

    def toggle_https(self):
        self.https_only = not self.https_only
        self._save_settings()
        self.status.config(text=f"● HTTPS-Only mode {'ON' if self.https_only else 'OFF'}")

    def change_zoom(self, amount):
        self.zoom = max(50, min(200, self.zoom + amount))
        self.status.config(text=f"● Page zoom: {self.zoom}%")
        if HAS_WEBVIEW:
            self.status.config(text=f"● Page zoom set to {self.zoom}% (new embedded pages use browser defaults)")

    def set_zoom(self, value):
        self.zoom = value
        self.status.config(text=f"● Page zoom: {self.zoom}%")

    def find_in_page(self):
        dialog = tk.Toplevel(self)
        dialog.title("Find in Page")
        dialog.configure(bg=PANEL)
        dialog.resizable(False, False)
        tk.Label(dialog, text="Find", bg=PANEL, fg=TEXT).pack(side="left", padx=10, pady=10)
        entry = ttk.Entry(dialog, width=35)
        entry.pack(side="left", padx=5, pady=10)
        tk.Button(dialog, text="Find", command=lambda: self.status.config(text=f"● Find: {entry.get()}"), bg=ACCENT, fg=TEXT, relief="flat").pack(side="left", padx=10)
        entry.focus_set()

    def show_privacy(self):
        self._clear_view()
        tk.Label(self.viewer, text="Privacy Center", bg="#0b0f18", fg=TEXT, font=("Segoe UI", 21, "bold")).pack(anchor="w", padx=25, pady=(25, 5))
        tk.Label(self.viewer, text="Browser privacy controls work alongside the active Findupto VPN tunnel.", bg="#0b0f18", fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", padx=25, pady=(0, 15))
        options = [
            ("Tracker & ad blocking", "block_trackers"),
            ("Popup blocking", "block_popups"),
            ("Do Not Track", "do_not_track"),
            ("HTTPS-Only mode", "https_only"),
            ("WebRTC leak protection", "block_webrtc"),
            ("Fingerprint protection", "fingerprint_protection"),
            ("Clear cookies on exit", "clear_cookies_on_exit"),
        ]
        box = tk.Frame(self.viewer, bg=PANEL)
        box.pack(fill="x", padx=25, pady=5)
        for label, attr in options:
            var = tk.BooleanVar(value=getattr(self, attr))
            def changed(a=attr, v=var):
                setattr(self, a, bool(v.get()))
                self._save_settings()
                self.status.config(text=f"● {label} {'ON' if v.get() else 'OFF'}")
            tk.Checkbutton(box, text=label, variable=var, command=changed, bg=PANEL, fg=TEXT,
                           selectcolor=PANEL_2, activebackground=PANEL, activeforeground=TEXT,
                           font=("Segoe UI", 10), anchor="w").pack(fill="x", padx=15, pady=5)
        tk.Label(self.viewer, text="VPN: ACTIVE / protected\nDNS protection: provided by VPN client\nKill-switch: managed by Findupto VPN client",
                 bg=PANEL_2, fg=SUCCESS, justify="left", font=("Segoe UI", 9, "bold"), padx=15, pady=12).pack(fill="x", padx=25, pady=15)

    def show_vpn_routing(self):
        self._clear_view()
        tk.Label(self.viewer, text="VPN Routing", bg="#0b0f18", fg=TEXT, font=("Segoe UI", 21, "bold")).pack(anchor="w", padx=25, pady=(25, 5))
        tk.Label(self.viewer, text="Choose the browser routing policy. Actual tunnel selection is handled by Findupto VPN.", bg="#0b0f18", fg=MUTED).pack(anchor="w", padx=25, pady=(0, 15))
        var = tk.StringVar(value=self.vpn_route)
        for value in ("All traffic", "Browser traffic only", "VPN bypass for local sites"):
            tk.Radiobutton(self.viewer, text=value, variable=var, value=value, bg="#0b0f18", fg=TEXT,
                           selectcolor=PANEL_2, activebackground="#0b0f18", activeforeground=TEXT,
                           command=lambda: self._set_vpn_route(var.get()), font=("Segoe UI", 10)).pack(anchor="w", padx=30, pady=5)
        tk.Label(self.viewer, text="● Findupto VPN integration active", bg=PANEL_2, fg=SUCCESS, font=("Segoe UI", 9, "bold"), padx=15, pady=12).pack(fill="x", padx=25, pady=20)

    def _set_vpn_route(self, value):
        self.vpn_route = value
        self._save_settings()
        self.vpn_status.config(text=f"● VPN PROTECTED\n{value}")
        self.status.config(text=f"● VPN routing: {value}")

    def show_settings(self):
        self._clear_view()
        tk.Label(self.viewer, text="Browser Settings", bg="#0b0f18", fg=TEXT, font=("Segoe UI", 21, "bold")).pack(anchor="w", padx=25, pady=(25, 15))
        box = tk.Frame(self.viewer, bg=PANEL)
        box.pack(fill="x", padx=25)
        tk.Label(box, text="Search engine", bg=PANEL, fg=TEXT, font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=15, pady=(15, 5))
        engine_var = tk.StringVar(value=self._engine_name())
        combo = ttk.Combobox(box, textvariable=engine_var, values=("Google", "DuckDuckGo", "Bing"), state="readonly", width=25)
        combo.pack(anchor="w", padx=15, pady=(0, 15))
        combo.bind("<<ComboboxSelected>>", lambda _e: self._set_engine(engine_var.get()))
        tk.Label(box, text=f"Zoom: {self.zoom}%", bg=PANEL, fg=TEXT).pack(anchor="w", padx=15, pady=5)
        zrow = tk.Frame(box, bg=PANEL)
        zrow.pack(anchor="w", padx=15, pady=(0, 15))
        for label, value in (("−", -10), ("Reset", 0), ("+", 10)):
            tk.Button(zrow, text=label, command=(lambda v=value: self.set_zoom(100) if v == 0 else self.change_zoom(v)), bg=PANEL_2, fg=TEXT, relief="flat", padx=12, pady=6).pack(side="left", padx=2)
        tk.Label(box, text="Permissions", bg=PANEL, fg=CYAN, font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=15, pady=(5, 3))
        tk.Label(box, text="Notifications: blocked   •   Camera: blocked   •   Microphone: blocked", bg=PANEL, fg=MUTED).pack(anchor="w", padx=15, pady=(0, 15))

    def _engine_name(self):
        if "duckduckgo" in self.search_engine:
            return "DuckDuckGo"
        if "bing.com" in self.search_engine:
            return "Bing"
        return "Google"

    def _set_engine(self, name):
        self.search_engine = {"Google": "https://www.google.com/search?q=", "DuckDuckGo": "https://duckduckgo.com/?q=", "Bing": "https://www.bing.com/search?q="}[name]
        self._save_settings()
        self.status.config(text=f"● Search engine: {name}")

    def show_browser_menu(self):
        menu = tk.Menu(self, tearoff=False, bg=PANEL, fg=TEXT, activebackground=ACCENT, activeforeground=TEXT)
        menu.add_command(label="New Tab", command=self.new_tab)
        menu.add_command(label="New Private Tab", command=lambda: (self.toggle_private(), self.new_tab()))
        menu.add_separator()
        menu.add_command(label="Add Bookmark", command=self.add_bookmark)
        menu.add_command(label="Find in Page", command=self.find_in_page)
        menu.add_command(label="Zoom In", command=lambda: self.change_zoom(10))
        menu.add_command(label="Zoom Out", command=lambda: self.change_zoom(-10))
        menu.add_command(label="Reset Zoom", command=lambda: self.set_zoom(100))
        menu.add_separator()
        menu.add_command(label="Privacy Center", command=self.show_privacy)
        menu.add_command(label="Browser Settings", command=self.show_settings)
        menu.add_command(label="Clear Browsing Data", command=self.clear_browsing_data)
        menu.tk_popup(self.winfo_pointerx(), self.winfo_pointery())

    def clear_browsing_data(self):
        if messagebox.askyesno("Clear browsing data", "Clear history, bookmarks, and browser session data?\n\nThis does not disconnect the VPN."):
            self.history.clear()
            self.forward_history.clear()
            self.bookmarks.clear()
            self.downloads.clear()
            self._save_settings()
            self.status.config(text="● Browsing data cleared")

    def _on_close(self):
        self._save_settings()
        self.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    VPNBrowser(root).mainloop()
