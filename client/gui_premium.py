from __future__ import annotations

import queue
import time
import tkinter as tk
from tkinter import ttk, messagebox

from gui import App as EngineApp

BG = "#080a0f"
SURFACE = "#0d1017"
PANEL = "#121722"
PANEL_2 = "#181e2a"
BORDER = "#252d3b"
TEXT = "#f5f7fb"
MUTED = "#8792a5"
ACCENT = "#765cff"
ACCENT_HI = "#9885ff"
SUCCESS = "#31d7a4"
DANGER = "#ff647d"
CYAN = "#5bdcff"
FONT = "Segoe UI"


class App(EngineApp):
    """Premium consumer VPN UI with legacy-engine compatibility."""

    def __init__(self):
        self._ui_state = "ready"
        self._connected_at = None
        super().__init__()
        self.after(100, self._premium_pump)
        self.bind("<Configure>", self._resize)

    def _configure_styles(self):
        s = ttk.Style(self)
        try:
            s.theme_use("clam")
        except tk.TclError:
            pass
        s.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=TEXT, rowheight=42, borderwidth=0, relief="flat", font=(FONT, 9))
        s.configure("Treeview.Heading", background=PANEL_2, foreground=MUTED, relief="flat", font=(FONT, 8, "bold"), padding=(10, 8))
        s.map("Treeview", background=[("selected", "#29223f")], foreground=[("selected", TEXT)])

    def _card(self, parent, bg=PANEL):
        return tk.Frame(parent, bg=bg, highlightthickness=1, highlightbackground=BORDER)

    def _btn(self, parent, text, command, kind="secondary", compact=False):
        colors = {"primary": (ACCENT, "white", ACCENT_HI), "secondary": (PANEL_2, TEXT, "#252d3c"), "danger": (DANGER, "#080a0f", "#ff8296"), "ghost": (SURFACE, MUTED, PANEL_2)}
        bg, fg, active = colors[kind]
        return tk.Button(parent, text=text, command=command, bg=bg, fg=fg, activebackground=active, activeforeground=fg, relief="flat", bd=0, highlightthickness=1, highlightbackground=BORDER, font=(FONT, 8 if compact else 9, "bold"), cursor="hand2", padx=11 if compact else 16, pady=6 if compact else 8)

    def _build(self):
        self.configure(bg=BG)
        # Compatibility with the inherited discovery worker: it updates this variable.
        # Define it before EngineApp can invoke refresh() during construction.
        self.side_status = tk.StringVar(value="Ready to connect")
        self._connected = False
        self.geometry("1240x780")
        self.minsize(980, 650)

        root = tk.Frame(self, bg=BG); root.pack(fill="both", expand=True)
        self.sidebar = tk.Frame(root, bg=SURFACE, width=72, highlightthickness=1, highlightbackground=BORDER)
        self.sidebar.pack(side="left", fill="y"); self.sidebar.pack_propagate(False)
        tk.Label(self.sidebar, text="F", bg=ACCENT, fg="white", width=2, font=(FONT, 18, "bold")).pack(pady=(22, 28))
        for icon, command in (("⌂", self._home), ("⌕", self._focus_search), ("⚡", self._fast), ("⚙", self._settings)):
            tk.Button(self.sidebar, text=icon, command=command, bg=SURFACE, fg=MUTED, activebackground=PANEL_2, activeforeground=TEXT, relief="flat", bd=0, font=("Segoe UI Symbol", 18), cursor="hand2").pack(fill="x", padx=10, pady=8)
        tk.Frame(self.sidebar, bg=SURFACE).pack(fill="both", expand=True)
        tk.Label(self.sidebar, text="●", bg=SURFACE, fg=SUCCESS, font=(FONT, 12)).pack()
        tk.Label(self.sidebar, text="SAFE", bg=SURFACE, fg=MUTED, font=(FONT, 7, "bold")).pack(pady=(0, 18))

        self.content = tk.Frame(root, bg=BG); self.content.pack(side="left", fill="both", expand=True, padx=28, pady=22)
        self.content.columnconfigure(0, weight=1); self.content.rowconfigure(3, weight=1)
        header = tk.Frame(self.content, bg=BG); header.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        tk.Label(header, text="FINDUPTO VPN", bg=BG, fg=TEXT, font=(FONT, 13, "bold")).pack(side="left")
        self.status = tk.StringVar(value="Ready")
        tk.Label(header, textvariable=self.status, bg=BG, fg=MUTED, font=(FONT, 9)).pack(side="left", padx=12)
        self.status_pill = tk.Label(header, text="● OFF", bg=PANEL_2, fg=MUTED, padx=12, pady=6, font=(FONT, 8, "bold"), highlightthickness=1, highlightbackground=BORDER); self.status_pill.pack(side="right")

        hero = self._card(self.content, SURFACE); hero.grid(row=1, column=0, sticky="ew", pady=(0, 12)); hero.columnconfigure(0, weight=1); hero.columnconfigure(1, weight=1); hero.columnconfigure(2, weight=1)
        left = tk.Frame(hero, bg=SURFACE); left.grid(row=0, column=0, sticky="w", padx=22, pady=18)
        self.hero_state = tk.Label(left, text="NOT PROTECTED", bg=SURFACE, fg=MUTED, font=(FONT, 8, "bold")); self.hero_state.pack(anchor="w")
        self.hero_location = tk.Label(left, text="Automatic", bg=SURFACE, fg=TEXT, font=(FONT, 18, "bold")); self.hero_location.pack(anchor="w", pady=(4, 1))
        self.hero_ip = tk.Label(left, text="Exit IP  —", bg=SURFACE, fg=MUTED, font=(FONT, 9)); self.hero_ip.pack(anchor="w")
        center = tk.Frame(hero, bg=SURFACE); center.grid(row=0, column=1, pady=15)
        self.power = tk.Button(center, text="CONNECT", command=self._toggle, bg=ACCENT, fg="white", activebackground=ACCENT_HI, activeforeground="white", relief="flat", bd=0, font=(FONT, 9, "bold"), width=11, padx=10, pady=8, cursor="hand2"); self.power.pack()
        self.timer = tk.Label(center, text="", bg=SURFACE, fg=MUTED, font=(FONT, 8)); self.timer.pack(pady=(6, 0))
        actions = tk.Frame(hero, bg=SURFACE); actions.grid(row=0, column=2, sticky="e", padx=22)
        self.change_btn = self._btn(actions, "↻  CHANGE IP", self._change_ip, "secondary", True); self.change_btn.pack(side="left", padx=3)
        self.disconnect_btn = self._btn(actions, "DISCONNECT", self._disconnect, "danger", True); self.disconnect_btn.pack(side="left", padx=3); self.disconnect_btn.configure(state="disabled")

        toolbar = tk.Frame(self.content, bg=BG); toolbar.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        self.best_btn = self._btn(toolbar, "✦  FASTEST", self.best, "primary", True); self.best_btn.pack(side="left")
        self.selected_btn = self._btn(toolbar, "CONNECT SELECTED", self.selected, "secondary", True); self.selected_btn.pack(side="left", padx=6)
        self.scan_btn = self._btn(toolbar, "SCAN", self.refresh, "ghost", True); self.scan_btn.pack(side="right")

        body = tk.Frame(self.content, bg=BG); body.grid(row=3, column=0, sticky="nsew"); body.columnconfigure(0, weight=4); body.columnconfigure(1, weight=2); body.rowconfigure(0, weight=1)
        locations = self._card(body); locations.grid(row=0, column=0, sticky="nsew", padx=(0, 9)); locations.rowconfigure(2, weight=1); locations.columnconfigure(0, weight=1)
        head = tk.Frame(locations, bg=PANEL); head.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 8)); tk.Label(head, text="LOCATIONS", bg=PANEL, fg=TEXT, font=(FONT, 11, "bold")).pack(side="left"); self.count = tk.Label(head, text="0 servers", bg=PANEL, fg=MUTED, font=(FONT, 8)); self.count.pack(side="right")
        search = tk.Frame(locations, bg=PANEL_2, highlightthickness=1, highlightbackground=BORDER); search.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 8)); tk.Label(search, text="⌕", bg=PANEL_2, fg=MUTED, font=(FONT, 13)).pack(side="left", padx=(9, 3)); self.search_var = tk.StringVar(); entry = tk.Entry(search, textvariable=self.search_var, bg=PANEL_2, fg=TEXT, insertbackground=TEXT, relief="flat", bd=0, font=(FONT, 10)); entry.pack(fill="x", expand=True, padx=(0, 9), pady=7); self.search_var.trace_add("write", lambda *_: self._render()); self.entry = entry
        frame = tk.Frame(locations, bg=PANEL); frame.grid(row=2, column=0, sticky="nsew", padx=9, pady=(0, 9)); frame.rowconfigure(0, weight=1); frame.columnconfigure(0, weight=1)
        cols = ("fav", "country", "city", "endpoint", "ping", "speed"); self.tree = ttk.Treeview(frame, columns=cols, show="headings", selectmode="browse")
        for col, title, w in (("fav", "", 35), ("country", "COUNTRY", 120), ("city", "CITY", 110), ("endpoint", "SERVER / IP", 190), ("ping", "PING", 75), ("speed", "SPEED", 85)):
            self.tree.heading(col, text=title); self.tree.column(col, width=w, minwidth=45, stretch=True)
        self.tree.tag_configure("fast", foreground=SUCCESS); self.tree.tag_configure("normal", foreground=TEXT); self.tree.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview); sb.grid(row=0, column=1, sticky="ns"); self.tree.configure(yscrollcommand=sb.set); self.tree.bind("<Double-1>", lambda _e: self.selected())

        side = tk.Frame(body, bg=BG); side.grid(row=0, column=1, sticky="nsew"); side.rowconfigure(1, weight=1)
        route = self._card(side); route.grid(row=0, column=0, sticky="ew", pady=(0, 9)); tk.Label(route, text="CURRENT ROUTE", bg=PANEL, fg=MUTED, font=(FONT, 8, "bold")).pack(anchor="w", padx=14, pady=(13, 5)); self.route_name = tk.StringVar(value="Automatic route"); tk.Label(route, textvariable=self.route_name, bg=PANEL, fg=TEXT, font=(FONT, 14, "bold"), wraplength=300, justify="left").pack(anchor="w", padx=14); self.route_ip = tk.StringVar(value="Exit IP  —"); tk.Label(route, textvariable=self.route_ip, bg=PANEL, fg=CYAN, font=(FONT, 9, "bold")).pack(anchor="w", padx=14, pady=(5, 2)); self.route_meta = tk.StringVar(value="Ping —  •  Protocol OpenVPN"); tk.Label(route, textvariable=self.route_meta, bg=PANEL, fg=MUTED, font=(FONT, 8)).pack(anchor="w", padx=14, pady=(0, 13))
        adv = self._card(side); adv.grid(row=1, column=0, sticky="nsew"); tk.Label(adv, text="ADVANCED", bg=PANEL, fg=MUTED, font=(FONT, 8, "bold")).pack(anchor="w", padx=14, pady=(13, 8)); self.advanced_text = tk.StringVar(value="Kill switch   Available\nDNS protection  Active after connect\nAuto-connect  Ready\nSplit tunneling  Ready"); tk.Label(adv, textvariable=self.advanced_text, bg=PANEL, fg=TEXT, justify="left", font=(FONT, 9), anchor="nw").pack(fill="both", expand=True, padx=14, pady=(0, 12))

    def _set_busy(self, busy, text="CONNECTING…"):
        self._ui_state = "busy" if busy else ("connected" if getattr(self, "_connected", False) else "ready")
        for b in (self.best_btn, self.selected_btn, self.scan_btn, self.change_btn):
            try: b.configure(state="disabled" if busy else "normal")
            except tk.TclError: pass
        self.status.set(text if busy else ("Protected" if getattr(self, "_connected", False) else "Ready"))
        self.side_status.set(text if busy else ("Protected" if getattr(self, "_connected", False) else "Ready to connect"))
        self.status_pill.configure(text="● CONNECTING" if busy else ("● ON" if getattr(self, "_connected", False) else "● OFF"), fg=CYAN if busy else (SUCCESS if getattr(self, "_connected", False) else MUTED))
        self.power.configure(state="disabled" if busy else "normal")
        self.disconnect_btn.configure(state="disabled" if busy or not getattr(self, "_connected", False) else "normal")

    def _toggle(self): self._disconnect() if getattr(self, "_connected", False) else self._connect_fast()
    def _connect_fast(self): self._set_busy(True); self.best()
    def _disconnect(self): self.disconnect()
    def _change_ip(self): self.change_ip()
    def _fast(self): self._connect_fast()
    def _home(self): self.power.focus_set()
    def _focus_search(self): self.entry.focus_set()
    def _settings(self): self.advanced_text.set("Kill switch   Available\nDNS protection  Available\nAuto-connect  Configurable\nSplit tunneling  Planned")

    def _render(self):
        if not hasattr(self, "tree"): return
        self.tree.delete(*self.tree.get_children()); query = self.search_var.get().strip().lower(); servers = getattr(self, "servers", []) or []
        shown = []
        for i, s in enumerate(servers):
            text = f"{s.get('country', '')} {s.get('city', '')} {s.get('host', '')} {s.get('ip', '')}".lower()
            if query and query not in text: continue
            shown.append((i, s))
        for i, s in shown[:250]:
            ping = float(s.get("live_ping", 9999) or 9999); speed = s.get("speed") or 0; fast = bool(s.get("available")) and ping < 180
            self.tree.insert("", "end", iid=str(i), tags=("fast" if fast else "normal",), values=("☆", s.get("country", "") or "—", s.get("city", "") or "—", s.get("host", "") or s.get("ip", "") or "—", ("—" if ping >= 9999 else f"{ping:.0f} ms"), (f"{float(speed):.1f} Mbps" if speed else "—")))
        self.count.configure(text=f"{len(shown)} servers")

    def _pump_events(self):
        pass

    def _premium_pump(self):
        try:
            while True:
                kind, _, text = self.events.get_nowait()
                if kind == "servers": self._render()
                elif kind == "status": self._set_busy(True, text)
                elif kind == "connected":
                    self._connected = True; self._connected_at = time.monotonic(); self._set_busy(False); self.hero_state.configure(text="PROTECTED", fg=SUCCESS); self.power.configure(text="DISCONNECT", bg=SUCCESS, fg=BG); self.status.set(text); self.side_status.set(text)
                    server = getattr(self, "selected_server", {}) or {}; loc = server.get("country") or "Secure route"; city = server.get("city") or ""; session = getattr(getattr(self, "_session_controller", None), "session", None); public = getattr(session, "public_ip", None) if session else None
                    self.hero_location.configure(text=f"{loc}{('  •  ' + city) if city else ''}"); self.hero_ip.configure(text=f"Exit IP  {public or server.get('ip') or 'Verified'}"); self.route_name.set(f"{loc}{('  •  ' + city) if city else ''}"); self.route_ip.set(f"Exit IP  {public or server.get('ip') or 'Verified'}")
                elif kind == "disconnected":
                    self._connected = False; self._connected_at = None; self._set_busy(False); self.hero_state.configure(text="NOT PROTECTED", fg=MUTED); self.power.configure(text="CONNECT", bg=ACCENT, fg="white"); self.hero_location.configure(text="Automatic"); self.hero_ip.configure(text="Exit IP  —"); self.route_name.set("Automatic route"); self.route_ip.set("Exit IP  —")
                elif kind == "error":
                    self._connected = False; self._set_busy(False); self.hero_state.configure(text="CONNECTION FAILED", fg=DANGER); self.status_pill.configure(text="● ERROR", fg=DANGER); self.status.set("Connection failed"); self.side_status.set("Connection failed"); messagebox.showerror("Findupto VPN", text)
        except queue.Empty:
            pass
        if getattr(self, "_connected", False) and self._connected_at:
            sec = int(time.monotonic() - self._connected_at); self.timer.configure(text=f"Connected  {sec//3600:02d}:{sec%3600//60:02d}:{sec%60:02d}")
        self.after(120, self._premium_pump)

    def _resize(self, event):
        if event.widget is self and event.width < 1060:
            self.content.configure(padx=18)

    def refresh(self):
        return super().refresh()


if __name__ == "__main__":
    App().mainloop()
