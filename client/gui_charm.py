from __future__ import annotations

import queue
import tkinter as tk
from tkinter import messagebox, ttk

from gui_pro import App as EngineApp, BG as OLD_BG, SURFACE as OLD_SURFACE, PANEL as OLD_PANEL
import standalone_engine as engine

# Findupto Charm UI — deliberately minimal, premium and connection-first.
BG = "#07070c"
SURFACE = "#0c0c13"
PANEL = "#11111a"
PANEL_2 = "#171722"
PANEL_3 = "#20202d"
BORDER = "#282837"
BORDER_HI = "#3a3a52"
TEXT = "#f8f8fc"
MUTED = "#85859a"
ACCENT = "#7c5cff"
ACCENT_2 = "#a58cff"
SUCCESS = "#35e0ad"
DANGER = "#ff5f78"
CYAN = "#5bdcff"
FONT = "Segoe UI"


class App(EngineApp):
    """Charm-style consumer VPN UI using the existing verified VPN engine."""

    def __init__(self):
        self._connection_state = "ready"
        self._session_started = None
        super().__init__()

    def _configure_styles(self):
        s = ttk.Style(self)
        try:
            s.theme_use("clam")
        except tk.TclError:
            pass
        s.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=TEXT,
                    rowheight=52, borderwidth=0, relief="flat", font=(FONT, 9))
        s.configure("Treeview.Heading", background=PANEL, foreground=MUTED,
                    relief="flat", font=(FONT, 8, "bold"), padding=(12, 10))
        s.map("Treeview", background=[("selected", "#27253a")], foreground=[("selected", TEXT)])
        s.configure("TCombobox", fieldbackground=PANEL_2, background=PANEL_2,
                    foreground=TEXT, arrowcolor=ACCENT_2, bordercolor=BORDER)
        s.configure("TCheckbutton", background=PANEL, foreground=TEXT, font=(FONT, 9))
        s.map("TCheckbutton", background=[("active", PANEL)])

    def _card(self, parent, bg=PANEL, border=BORDER):
        return tk.Frame(parent, bg=bg, highlightthickness=1, highlightbackground=border)

    def _button(self, parent, text, command, kind="secondary", compact=False):
        palette = {
            "primary": (ACCENT, "white", ACCENT_2),
            "success": (SUCCESS, BG, "#67edc3"),
            "danger": (DANGER, BG, "#ff8798"),
            "secondary": (PANEL_3, TEXT, "#2b2b3c"),
            "ghost": (PANEL, MUTED, PANEL_2),
        }
        bg, fg, hover = palette[kind]
        b = tk.Button(parent, text=text, command=command, bg=bg, fg=fg,
                      activebackground=hover, activeforeground=fg, relief="flat", bd=0,
                      highlightthickness=1, highlightbackground=BORDER_HI,
                      cursor="hand2", font=(FONT, 9 if compact else 10, "bold"),
                      padx=12 if compact else 18, pady=7 if compact else 11)
        b._charm_base = bg
        b.bind("<Enter>", lambda _e: b.configure(bg=hover))
        b.bind("<Leave>", lambda _e: b.configure(bg=b._charm_base))
        return b

    def _build(self):
        self.configure(bg=BG)
        self.geometry(f"{min(1320, max(980, self.winfo_screenwidth()-120))}x{min(820, max(680, self.winfo_screenheight()-130))}")
        self.minsize(900, 620)

        self.root = tk.Frame(self, bg=BG)
        self.root.pack(fill="both", expand=True)

        # Slim navigation — no oversized admin-style sidebar.
        self.sidebar = tk.Frame(self.root, bg=SURFACE, width=74, highlightthickness=1, highlightbackground=BORDER)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        self._build_sidebar()

        self.content = tk.Frame(self.root, bg=BG)
        self.content.pack(side="left", fill="both", expand=True)
        self._build_content()
        self._apply_responsive_layout(self.winfo_width() or 1200)

    def _build_sidebar(self):
        logo = tk.Frame(self.sidebar, bg=ACCENT, width=42, height=42)
        logo.pack(pady=(22, 30)); logo.pack_propagate(False)
        tk.Label(logo, text="F", bg=ACCENT, fg="white", font=(FONT, 17, "bold")).pack(expand=True)

        self.nav_items = []
        for icon, label, command in (("⌂", "Home", self._focus_dashboard),
                                     ("◎", "Locations", self._focus_servers),
                                     ("⚡", "Fast", self._focus_quick),
                                     ("◌", "Diagnostics", self.open_log)):
            b = tk.Button(self.sidebar, text=icon, command=command, bg=SURFACE, fg=MUTED,
                          activebackground=PANEL_2, activeforeground=TEXT, relief="flat", bd=0,
                          cursor="hand2", font=("Segoe UI Symbol", 17), pady=9)
            b.pack(fill="x", padx=10, pady=3)
            b.bind("<Enter>", lambda e, x=b: x.configure(fg=TEXT, bg=PANEL_2))
            b.bind("<Leave>", lambda e, x=b: x.configure(fg=MUTED, bg=SURFACE))
            self.nav_items.append(b)
        tk.Frame(self.sidebar, bg=SURFACE).pack(fill="both", expand=True)
        tk.Label(self.sidebar, text="●", bg=SURFACE, fg=SUCCESS, font=(FONT, 13)).pack(pady=(0, 3))
        tk.Label(self.sidebar, text="SAFE", bg=SURFACE, fg=MUTED, font=(FONT, 7, "bold")).pack(pady=(0, 20))

    def _build_content(self):
        self.header = tk.Frame(self.content, bg=BG)
        self.header.pack(fill="x", padx=34, pady=(24, 12))
        left = tk.Frame(self.header, bg=BG); left.pack(side="left", fill="x", expand=True)
        tk.Label(left, text="FINDUPTO", bg=BG, fg=TEXT, font=(FONT, 11, "bold")).pack(anchor="w")
        self.status = tk.StringVar(value="Ready to protect your connection")
        tk.Label(left, textvariable=self.status, bg=BG, fg=MUTED, font=(FONT, 9)).pack(anchor="w", pady=(3, 0))
        self.status_pill = tk.Label(self.header, text="●  NOT CONNECTED", bg=PANEL_2, fg=MUTED,
                                    padx=13, pady=7, font=(FONT, 8, "bold"), highlightthickness=1, highlightbackground=BORDER)
        self.status_pill.pack(side="right", pady=3)

        # Hero: this is the visual center of the application.
        self.hero = self._card(self.content, bg=SURFACE, border=BORDER_HI)
        self.hero.pack(fill="both", expand=False, padx=34, pady=(0, 14))
        self.hero.configure(height=292); self.hero.pack_propagate(False)

        canvas = tk.Canvas(self.hero, bg=SURFACE, highlightthickness=0, bd=0)
        canvas.pack(fill="both", expand=True)
        self.hero_canvas = canvas
        canvas.bind("<Configure>", self._draw_hero)

        self.hero_title = tk.Label(self.hero, text="PROTECTED", bg=SURFACE, fg=MUTED, font=(FONT, 8, "bold"))
        self.hero_title.place(relx=.5, y=24, anchor="n")
        self.location_label = tk.Label(self.hero, text="Automatic location", bg=SURFACE, fg=TEXT, font=(FONT, 18, "bold"))
        self.location_label.place(relx=.5, y=48, anchor="n")
        self.ip_label = tk.Label(self.hero, text="Exit IP  —", bg=SURFACE, fg=MUTED, font=(FONT, 9))
        self.ip_label.place(relx=.5, y=78, anchor="n")
        self.power = tk.Button(self.hero, text="ON", command=self._hero_action, bg=ACCENT, fg="white",
                               activebackground=ACCENT_2, activeforeground="white", relief="flat", bd=0,
                               font=(FONT, 13, "bold"), cursor="hand2", width=6, height=2)
        self.power.place(relx=.5, rely=.55, anchor="center")
        self.hero_hint = tk.Label(self.hero, text="Tap to connect to the fastest verified route", bg=SURFACE, fg=MUTED, font=(FONT, 8))
        self.hero_hint.place(relx=.5, rely=.84, anchor="center")

        # Compact control rail: only actions people actually need.
        self.controls = tk.Frame(self.content, bg=BG)
        self.controls.pack(fill="x", padx=34, pady=(0, 12))
        self.best_btn = self._button(self.controls, "✦  CONNECT FASTEST", self.best, "primary")
        self.best_btn.pack(side="left")
        self.change_btn = self._button(self.controls, "↻  CHANGE IP", self._change_ip, "secondary")
        self.change_btn.pack(side="left", padx=8)
        self.disconnect_btn = self._button(self.controls, "DISCONNECT", self.disconnect, "danger")
        self.disconnect_btn.pack(side="left")
        self.refresh_btn = self._button(self.controls, "SCAN", self.refresh, "ghost", True)
        self.refresh_btn.pack(side="right")
        self.sel_btn = self._button(self.controls, "CONNECT SELECTED", self.selected, "ghost", True)
        self.sel_btn.pack(side="right", padx=7)

        body = tk.Frame(self.content, bg=BG)
        body.pack(fill="both", expand=True, padx=34, pady=(0, 20))
        body.grid_columnconfigure(0, weight=3); body.grid_columnconfigure(1, weight=2); body.grid_rowconfigure(1, weight=1)

        # Search-first location panel inspired by current premium VPN UX.
        locations = self._card(body, bg=PANEL)
        locations.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(0, 9))
        head = tk.Frame(locations, bg=PANEL); head.pack(fill="x", padx=16, pady=(15, 9))
        tk.Label(head, text="LOCATIONS", bg=PANEL, fg=TEXT, font=(FONT, 12, "bold")).pack(side="left")
        self.speed_status = tk.StringVar(value="Ready")
        tk.Label(head, textvariable=self.speed_status, bg=PANEL, fg=SUCCESS, font=(FONT, 8, "bold")).pack(side="right")
        search_wrap = tk.Frame(locations, bg=PANEL_2, highlightthickness=1, highlightbackground=BORDER_HI)
        search_wrap.pack(fill="x", padx=16, pady=(0, 10))
        tk.Label(search_wrap, text="⌕", bg=PANEL_2, fg=MUTED, font=(FONT, 14)).pack(side="left", padx=(10, 3))
        self.search_var = tk.StringVar()
        entry = tk.Entry(search_wrap, textvariable=self.search_var, bg=PANEL_2, fg=TEXT,
                         insertbackground=TEXT, relief="flat", bd=0, font=(FONT, 10))
        entry.pack(side="left", fill="x", expand=True, padx=(0, 10), pady=9)
        self.search_var.trace_add("write", lambda *_: self._render())

        # Filter variables required by the inherited discovery/ranking engine.
        self.fast_only = tk.BooleanVar(value=True)
        self.available_only = tk.BooleanVar(value=True)
        self.auto_connect = tk.BooleanVar(value=False)
        self.country = tk.StringVar(value="All"); self.city = tk.StringVar(value="All"); self.source = tk.StringVar(value="All")
        self.max_ping = tk.IntVar(value=400)
        self.country_combo = ttk.Combobox(locations, textvariable=self.country, state="readonly", width=12)
        self.city_combo = ttk.Combobox(locations, textvariable=self.city, state="readonly", width=12)
        self.source_combo = ttk.Combobox(locations, textvariable=self.source, state="readonly", width=12)
        # Keep combos available to inherited _eligible/_update_combos without making them dominate the UI.
        self.country_combo.pack_forget(); self.city_combo.pack_forget(); self.source_combo.pack_forget()

        frame = tk.Frame(locations, bg=PANEL); frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        cols = ("status", "country", "city", "endpoint", "latency", "speed")
        self._table_columns = cols
        self.tree = ttk.Treeview(frame, columns=cols, show="headings", selectmode="browse")
        for col, title, width in (("status", "", 70), ("country", "COUNTRY", 125), ("city", "CITY", 110),
                                  ("endpoint", "LOCATION", 180), ("latency", "PING", 75), ("speed", "SPEED", 85)):
            self.tree.heading(col, text=title); self.tree.column(col, width=width, minwidth=55, stretch=True)
        self.tree.tag_configure("fast", foreground=SUCCESS); self.tree.tag_configure("online", foreground=TEXT)
        y = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview); self.tree.configure(yscrollcommand=y.set)
        self.tree.grid(row=0, column=0, sticky="nsew"); y.grid(row=0, column=1, sticky="ns")
        frame.rowconfigure(0, weight=1); frame.columnconfigure(0, weight=1)
        self.tree.bind("<Double-1>", lambda _e: self.selected())

        # Right side: current route + quiet telemetry, not a wall of cards.
        route = self._card(body, bg=PANEL)
        route.grid(row=0, column=1, sticky="nsew", pady=(0, 9))
        tk.Label(route, text="CURRENT ROUTE", bg=PANEL, fg=MUTED, font=(FONT, 8, "bold")).pack(anchor="w", padx=16, pady=(15, 5))
        self.route_name = tk.StringVar(value="No active route")
        tk.Label(route, textvariable=self.route_name, bg=PANEL, fg=TEXT, font=(FONT, 15, "bold"), wraplength=300, justify="left").pack(anchor="w", padx=16)
        self.route_ip = tk.StringVar(value="Exit IP  —")
        tk.Label(route, textvariable=self.route_ip, bg=PANEL, fg=CYAN, font=(FONT, 10, "bold")).pack(anchor="w", padx=16, pady=(6, 2))
        self.route_meta = tk.StringVar(value="Latency —   •   Speed —")
        tk.Label(route, textvariable=self.route_meta, bg=PANEL, fg=MUTED, font=(FONT, 8)).pack(anchor="w", padx=16)
        self.session_label = tk.Label(route, text="SESSION  00:00:00", bg=PANEL_2, fg=MUTED, padx=10, pady=7, font=(FONT, 8, "bold"), highlightthickness=1, highlightbackground=BORDER)
        self.session_label.pack(anchor="w", padx=16, pady=14)

        stats = self._card(body, bg=PANEL)
        stats.grid(row=1, column=1, sticky="nsew")
        tk.Label(stats, text="NETWORK INTELLIGENCE", bg=PANEL, fg=MUTED, font=(FONT, 8, "bold")).pack(anchor="w", padx=16, pady=(14, 7))
        self.stat_cards = {}
        for key, title in (("available", "ONLINE"), ("fast", "FAST ROUTES"), ("tested", "TESTED"), ("shown", "MATCHING")):
            row = tk.Frame(stats, bg=PANEL); row.pack(fill="x", padx=16, pady=5)
            v = tk.StringVar(value="0"); self.stat_cards[key] = v
            tk.Label(row, text=title, bg=PANEL, fg=MUTED, font=(FONT, 8, "bold")).pack(side="left")
            tk.Label(row, textvariable=v, bg=PANEL, fg=TEXT, font=(FONT, 10, "bold")).pack(side="right")
        self.quick_frame = tk.Frame(stats, bg=PANEL)
        self.quick_frame.pack(fill="x", padx=16, pady=(7, 12))

    def _draw_hero(self, event=None):
        if not hasattr(self, "hero_canvas"):
            return
        c = self.hero_canvas; c.delete("all")
        w, h = max(c.winfo_width(), 400), max(c.winfo_height(), 250)
        cx, cy = w/2, h*.56
        for r, color, width in ((92, "#17142a", 10), (72, "#1f1a3b", 6), (53, "#2b2450", 3)):
            c.create_oval(cx-r, cy-r, cx+r, cy+r, outline=color, width=width)
        c.create_oval(cx-112, cy-112, cx+112, cy+112, outline="#151522", width=1)

    def _hero_action(self):
        if self._connection_state == "connected":
            self.disconnect()
        else:
            self.best()

    def _focus_dashboard(self): self.hero.focus_set()
    def _focus_servers(self): self.tree.focus_set()
    def _focus_quick(self): self.tree.focus_set()

    def _apply_responsive_layout(self, width):
        narrow = width < 1040
        pad = 18 if narrow else 34
        for w in (self.header, self.hero, self.controls):
            w.pack_configure(padx=pad)
        body = getattr(self, "content", None)
        if body and hasattr(self, "tree"):
            # Keep the two-column composition until the window becomes genuinely narrow.
            pass
        self.sidebar.pack_configure(fill="y")

    def _set_table_mode(self, mode):
        return None

    def _set_busy(self, value):
        self.busy = value
        state = "disabled" if value else "normal"
        for b in (self.refresh_btn, self.best_btn, self.sel_btn, self.change_btn):
            try: b.configure(state=state)
            except tk.TclError: pass
        self.status_pill.configure(text="●  CONNECTING" if value else "●  READY", fg=CYAN if value else MUTED)

    def _render(self):
        visible = self._eligible()
        query = self.search_var.get().strip().lower()
        if query:
            visible = [s for s in visible if query in str(s.get("country", "")).lower() or query in str(s.get("city", "")).lower() or query in str(s.get("host", "")).lower()]
        self.tree.delete(*self.tree.get_children())
        index = {id(s): i for i, s in enumerate(self.servers)}
        for s in visible:
            ping = float(s.get("live_ping", 9999)); fast = bool(s.get("available")) and ping <= 250
            self.tree.insert("", "end", iid=str(index[id(s)]), tags=("fast" if fast else "online",), values=(
                "●" if fast else "○", s.get("country", ""), s.get("city", ""), s.get("host", "") or s.get("ip", ""),
                "—" if ping >= 9999 else f"{ping:.0f} ms", f"{float(s.get('speed', 0) or 0):.1f} Mbps" if s.get("speed") else "—"))
        self.stat_cards["shown"].set(str(len(visible))); self.stat_cards["available"].set(str(sum(bool(s.get("available")) for s in self.servers)))
        self.stat_cards["fast"].set(str(sum(bool(s.get("available")) and float(s.get("live_ping", 9999)) <= 250 for s in self.servers)))
        self.stat_cards["tested"].set(str(len(self.servers)))

    def _pump(self):
        try:
            while True:
                kind, payload, text = self.events.get_nowait()
                if kind == "servers":
                    self.servers = payload or []; self._update_combos(); self._render(); self._set_busy(False)
                    self.status.set(text); self.speed_status.set("● NETWORK READY");
                elif kind == "status":
                    self.status.set(text); self.status_pill.configure(text="●  CONNECTING", fg=CYAN); self._connection_state = "connecting"
                elif kind == "connected":
                    self._set_busy(False); self._connection_state = "connected"
                    self.status.set(text); self.status_pill.configure(text="●  PROTECTED", fg=SUCCESS)
                    self.hero_title.configure(text="PROTECTED", fg=SUCCESS); self.power.configure(text="OFF", bg=SUCCESS, fg=BG)
                    server = getattr(self, "selected_server", {}) or {}; country = server.get("country") or "Secure route"; city = server.get("city") or ""
                    self.location_label.configure(text=f"{country}{('  •  ' + city) if city else ''}")
                    ip = getattr(getattr(self, "_session_controller", None), "session", None)
                    public_ip = getattr(ip, "public_ip", None) if ip else None
                    self.ip_label.configure(text=f"Exit IP  {public_ip or 'verified'}")
                    self.route_name.set(f"{country}{('  •  ' + city) if city else ''}"); self.route_ip.set(f"Exit IP  {public_ip or 'verified'}")
                    self.hero_hint.configure(text="Your connection is protected • Change IP anytime")
                elif kind == "disconnected":
                    self._set_busy(False); self._connection_state = "ready"
                    self.status.set(text); self.status_pill.configure(text="●  NOT CONNECTED", fg=MUTED)
                    self.hero_title.configure(text="PROTECTED", fg=MUTED); self.power.configure(text="ON", bg=ACCENT, fg="white")
                    self.location_label.configure(text="Automatic location"); self.ip_label.configure(text="Exit IP  —"); self.route_name.set("No active route"); self.route_ip.set("Exit IP  —")
                    self.hero_hint.configure(text="Tap to connect to the fastest verified route")
                elif kind == "error":
                    self._set_busy(False); self._connection_state = "ready"
                    self.status.set("Connection unavailable"); self.status_pill.configure(text="●  ATTENTION", fg=DANGER)
                    messagebox.showerror("Findupto VPN", text)
        except queue.Empty:
            pass
        self.after(100, self._pump)

    def _on_resize(self, event):
        if event.widget is self:
            self._apply_responsive_layout(event.width)


if __name__ == "__main__":
    App().mainloop()
