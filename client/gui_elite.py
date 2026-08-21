from __future__ import annotations

import time
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor, as_completed
from tkinter import ttk

import standalone_engine as engine
from gui_pro import App as PremiumApp

# Large real-world discovery pool. No fabricated/static IPs are introduced.
engine.MAX_DISCOVERY = 5000

BG = "#070910"
SURFACE = "#0b0f18"
PANEL = "#101622"
PANEL_2 = "#151d2b"
PANEL_3 = "#1b2638"
BORDER = "#26334a"
BORDER_HI = "#465a7b"
TEXT = "#f7f9ff"
MUTED = "#8290a8"
ACCENT = "#7657ff"
ACCENT_2 = "#9d8cff"
SUCCESS = "#32dfae"
WARNING = "#ffc86e"
DANGER = "#ff6b84"
CYAN = "#60dcff"
BLUE = "#4d91ff"
FONT = "Segoe UI"


class App(PremiumApp):
    """Premium Findupto VPN command-center dashboard."""

    def __init__(self):
        self._session_started = None
        self._scan_started = None
        super().__init__()

    def _configure_styles(self):
        super()._configure_styles()
        s = ttk.Style(self)
        try:
            s.theme_use("clam")
        except tk.TclError:
            pass
        s.configure("Treeview", rowheight=56, font=(FONT, 9), borderwidth=0,
                    background=PANEL, fieldbackground=PANEL, foreground=TEXT)
        s.configure("Treeview.Heading", padding=(13, 12), font=(FONT, 8, "bold"),
                    background=PANEL_3, foreground=MUTED, relief="flat")
        s.map("Treeview", background=[("selected", "#303e5d")],
              foreground=[("selected", TEXT)])
        s.configure("TCombobox", padding=8, font=(FONT, 9), fieldbackground=PANEL_2,
                    background=PANEL_2, foreground=TEXT, arrowcolor=ACCENT_2)
        s.configure("TSpinbox", padding=7, font=(FONT, 9), fieldbackground=PANEL_2,
                    background=PANEL_2, foreground=TEXT, arrowcolor=ACCENT_2)
        s.configure("TCheckbutton", padding=6, font=(FONT, 9, "bold"),
                    background=PANEL, foreground=TEXT)

    def _card(self, parent, bg=PANEL, accent=False, glow=False):
        f = tk.Frame(parent, bg=bg, highlightthickness=2 if glow else 1,
                     highlightbackground=ACCENT if glow else (BORDER_HI if accent else BORDER),
                     highlightcolor=ACCENT)
        if accent:
            tk.Frame(f, bg=ACCENT, height=3).pack(fill="x", side="top")
        return f

    def _pill(self, parent, text, bg=PANEL_2, fg=MUTED):
        return tk.Label(parent, text=text, bg=bg, fg=fg, padx=12, pady=6,
                        font=(FONT, 8, "bold"), highlightthickness=1,
                        highlightbackground=BORDER_HI)

    def _button(self, parent, text, command, kind="secondary", compact=False):
        palette = {
            "primary": (ACCENT, "#ffffff", ACCENT_2),
            "success": (SUCCESS, BG, "#67efc6"),
            "danger": (DANGER, BG, "#ff9aac"),
            "secondary": (PANEL_3, TEXT, "#2a3d5b"),
            "ghost": (SURFACE, MUTED, PANEL_2),
            "blue": (BLUE, "#ffffff", "#79b0ff"),
        }
        bg, fg, hover = palette[kind]
        b = tk.Button(parent, text=text, command=command, bg=bg, fg=fg,
                      activebackground=hover, activeforeground=fg, relief="flat", bd=0,
                      highlightthickness=1, highlightbackground=BORDER_HI,
                      highlightcolor=ACCENT_2, cursor="hand2",
                      font=(FONT, 9 if compact else 10, "bold"),
                      padx=12 if compact else 18, pady=7 if compact else 11)
        b._base_bg, b._hover_bg = bg, hover
        b.bind("<Enter>", lambda _e: b.configure(bg=b._hover_bg, highlightbackground=ACCENT_2))
        b.bind("<Leave>", lambda _e: b.configure(bg=b._base_bg, highlightbackground=BORDER_HI))
        b.bind("<ButtonPress-1>", lambda _e: b.configure(relief="sunken"))
        b.bind("<ButtonRelease-1>", lambda _e: b.configure(relief="flat"))
        return b

    def _build(self):
        self.configure(bg=BG)
        self.root = tk.Frame(self, bg=BG)
        self.root.pack(fill="both", expand=True)

        self.sidebar = tk.Frame(self.root, bg=SURFACE, width=244,
                                highlightthickness=1, highlightbackground=BORDER)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        self._build_premium_sidebar()

        self.content = tk.Frame(self.root, bg=BG)
        self.content.pack(side="left", fill="both", expand=True)
        self._build_premium_content()
        self._apply_responsive_layout(self.winfo_width() or 1280)

    def _build_premium_sidebar(self):
        brand = tk.Frame(self.sidebar, bg=SURFACE)
        brand.pack(fill="x", padx=18, pady=(22, 24))
        logo = tk.Frame(brand, bg=ACCENT, width=46, height=46)
        logo.pack(side="left", padx=(0, 12)); logo.pack_propagate(False)
        tk.Label(logo, text="F", bg=ACCENT, fg="white", font=(FONT, 18, "bold")).pack(expand=True)
        names = tk.Frame(brand, bg=SURFACE); names.pack(side="left")
        tk.Label(names, text="FINDUPTO", bg=SURFACE, fg=TEXT, font=(FONT, 14, "bold")).pack(anchor="w")
        tk.Label(names, text="PRIVATE NETWORK", bg=SURFACE, fg=ACCENT_2, font=(FONT, 7, "bold")).pack(anchor="w")

        tk.Label(self.sidebar, text="COMMAND CENTER", bg=SURFACE, fg=MUTED,
                 font=(FONT, 7, "bold")).pack(anchor="w", padx=20, pady=(0, 8))
        self.nav_items = []
        for icon, label, command in (("⌂", "Overview", self._focus_dashboard),
                                     ("◈", "Server Network", self._focus_servers),
                                     ("⚡", "Fast Routes", self._focus_quick),
                                     ("◉", "Diagnostics", self.open_log)):
            b = tk.Button(self.sidebar, text=f"  {icon}   {label}", anchor="w", command=command,
                          bg=ACCENT if label == "Overview" else SURFACE,
                          fg="#ffffff" if label == "Overview" else MUTED,
                          activebackground=PANEL_2, activeforeground=TEXT, relief="flat", bd=0,
                          cursor="hand2", font=(FONT, 10, "bold"), padx=18, pady=12)
            b.pack(fill="x", padx=10, pady=2)
            self.nav_items.append(b)

        tk.Frame(self.sidebar, bg=SURFACE).pack(fill="both", expand=True)
        status = self._card(self.sidebar, bg=PANEL, accent=True)
        status.pack(fill="x", padx=14, pady=14)
        row = tk.Frame(status, bg=PANEL); row.pack(fill="x", padx=13, pady=(11, 4))
        tk.Label(row, text="●", bg=PANEL, fg=SUCCESS, font=(FONT, 11, "bold")).pack(side="left")
        tk.Label(row, text="NETWORK HEALTH", bg=PANEL, fg=MUTED, font=(FONT, 7, "bold")).pack(side="left", padx=6)
        self.side_status = tk.StringVar(value="Ready for secure connection")
        tk.Label(status, textvariable=self.side_status, bg=PANEL, fg=TEXT,
                 font=(FONT, 9, "bold"), wraplength=190, justify="left").pack(anchor="w", padx=13, pady=(0, 12))
        tk.Label(self.sidebar, text=f"v{engine.APP_VERSION}  •  Live route intelligence", bg=SURFACE,
                 fg=MUTED, font=(FONT, 7)).pack(anchor="w", padx=20, pady=(0, 18))

    def _build_premium_content(self):
        self.header = tk.Frame(self.content, bg=BG)
        self.header.pack(fill="x", padx=30, pady=(22, 13))
        left = tk.Frame(self.header, bg=BG); left.pack(side="left", fill="x", expand=True)
        tk.Label(left, text="SECURE NETWORK  /  COMMAND CENTER", bg=BG, fg=ACCENT_2,
                 font=(FONT, 8, "bold")).pack(anchor="w")
        tk.Label(left, text="Your private network, beautifully controlled.", bg=BG, fg=TEXT,
                 font=(FONT, 25, "bold")).pack(anchor="w", pady=(2, 0))
        tk.Label(left, text="Discover live routes, compare performance and connect with confidence.",
                 bg=BG, fg=MUTED, font=(FONT, 9)).pack(anchor="w", pady=(3, 0))
        self.status_pill = self._pill(self.header, "●  READY", PANEL_2, MUTED)
        self.status_pill.pack(side="right", pady=(8, 0))

        self.hero = self._card(self.content, bg=SURFACE, accent=True, glow=True)
        self.hero.pack(fill="x", padx=30, pady=(0, 12))
        hero_left = tk.Frame(self.hero, bg=SURFACE); hero_left.pack(side="left", fill="x", expand=True, padx=22, pady=19)
        tk.Label(hero_left, text="SMART ROUTE ENGINE", bg=SURFACE, fg=CYAN, font=(FONT, 8, "bold")).pack(anchor="w")
        tk.Label(hero_left, text="One elegant tap. The best verified route.", bg=SURFACE, fg=TEXT,
                 font=(FONT, 15, "bold")).pack(anchor="w", pady=(4, 2))
        tk.Label(hero_left, text="Latency • availability • throughput • route quality", bg=SURFACE, fg=MUTED,
                 font=(FONT, 8)).pack(anchor="w")
        self.best_btn = self._button(self.hero, "✦  CONNECT SMART", self.best, "primary")
        self.best_btn.pack(side="right", padx=22, pady=20)

        self.command = self._card(self.content, bg=PANEL, accent=False)
        self.command.pack(fill="x", padx=30, pady=(0, 10))
        tk.Label(self.command, text="LIVE CONTROL", bg=PANEL, fg=MUTED, font=(FONT, 7, "bold")).pack(side="left", padx=(15, 8), pady=13)
        self._button(self.command, "⚡ SMART CONNECT", self.best, "primary", True).pack(side="right", padx=5, pady=7)
        self._button(self.command, "↻ REFRESH NETWORK", self.refresh, "blue", True).pack(side="right", padx=5, pady=7)
        self.session_label = tk.Label(self.command, text="SESSION  00:00:00", bg=PANEL_2, fg=CYAN,
                                      padx=13, pady=8, font=(FONT, 8, "bold"), highlightthickness=1,
                                      highlightbackground=BORDER_HI)
        self.session_label.pack(side="right", padx=6, pady=7)

        self.metrics = tk.Frame(self.content, bg=BG); self.metrics.pack(fill="x", padx=30, pady=(0, 10))
        self.metric_vars = {}
        for key, title, accent in (("visible", "VISIBLE ROUTES", CYAN), ("online", "VERIFIED ONLINE", SUCCESS),
                                   ("fast", "FAST ROUTES", ACCENT_2), ("countries", "COUNTRIES", WARNING),
                                   ("tested", "TESTED", TEXT)):
            c = self._card(self.metrics, bg=PANEL)
            c.pack(side="left", fill="x", expand=True, padx=(0, 7))
            tk.Label(c, text=title, bg=PANEL, fg=MUTED, font=(FONT, 7, "bold")).pack(anchor="w", padx=14, pady=(10, 2))
            v = tk.StringVar(value="0"); self.metric_vars[key] = v
            tk.Label(c, textvariable=v, bg=PANEL, fg=accent, font=(FONT, 19, "bold")).pack(anchor="w", padx=14)
            tk.Label(c, text="LIVE INTELLIGENCE", bg=PANEL, fg=MUTED, font=(FONT, 6, "bold")).pack(anchor="w", padx=14, pady=(0, 10))

        self.filters = self._card(self.content, bg=PANEL)
        self.filters.pack(fill="x", padx=30, pady=(0, 10))
        self._build_filters_premium()

        self.quick = self._card(self.content, bg=PANEL, accent=True)
        self.quick.pack(fill="x", padx=30, pady=(0, 10))
        qhead = tk.Frame(self.quick, bg=PANEL); qhead.pack(fill="x", padx=16, pady=(10, 5))
        tk.Label(qhead, text="⚡  FASTEST VERIFIED ROUTES", bg=PANEL, fg=TEXT, font=(FONT, 11, "bold")).pack(side="left")
        self.speed_status = tk.StringVar(value="Waiting for network scan")
        tk.Label(qhead, textvariable=self.speed_status, bg=PANEL, fg=SUCCESS, font=(FONT, 8, "bold")).pack(side="right")
        self.quick_frame = tk.Frame(self.quick, bg=PANEL); self.quick_frame.pack(fill="x", padx=10, pady=(0, 12))

        self.server_card = self._card(self.content, bg=PANEL)
        self.server_card.pack(fill="both", expand=True, padx=30, pady=(0, 10))
        top = tk.Frame(self.server_card, bg=PANEL); top.pack(fill="x", padx=16, pady=(11, 7))
        tk.Label(top, text="SERVER NETWORK", bg=PANEL, fg=TEXT, font=(FONT, 12, "bold")).pack(side="left")
        self.table_hint = tk.Label(top, text="Live verified routes", bg=PANEL, fg=MUTED, font=(FONT, 8)); self.table_hint.pack(side="right")
        frame = tk.Frame(self.server_card, bg=PANEL); frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        cols = ("status", "country", "city", "endpoint", "routes", "latency", "speed", "source")
        self.tree = ttk.Treeview(frame, columns=cols, show="headings", selectmode="browse")
        self._table_columns = cols
        headings = ("STATUS", "COUNTRY", "CITY", "ENDPOINT", "IP ROUTES", "LATENCY", "SPEED", "SOURCE")
        for col, heading in zip(cols, headings): self.tree.heading(col, text=heading); self.tree.column(col, width=110, minwidth=58, stretch=True)
        self.tree.tag_configure("fast", foreground=SUCCESS); self.tree.tag_configure("online", foreground=TEXT)
        y = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview); x = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=y.set, xscrollcommand=x.set)
        self.tree.grid(row=0, column=0, sticky="nsew"); y.grid(row=0, column=1, sticky="ns"); x.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1); frame.columnconfigure(0, weight=1)
        self.tree.bind("<Double-1>", lambda _e: self.selected())

        self.action_bar = tk.Frame(self.content, bg=BG); self.action_bar.pack(fill="x", padx=30, pady=(0, 16))
        self.refresh_btn = self._button(self.action_bar, "↻  SCAN NETWORK", self.refresh, "blue")
        self.refresh_btn.pack(side="left")
        self.sel_btn = self._button(self.action_bar, "➜  CONNECT SELECTED", self.selected, "secondary")
        self.sel_btn.pack(side="left", padx=7)
        self.diag_btn = self._button(self.action_bar, "◉  OPEN DIAGNOSTICS", self.open_log, "ghost")
        self.diag_btn.pack(side="left")
        self.disconnect_btn = self._button(self.action_bar, "■  DISCONNECT", self.disconnect, "danger")
        self.disconnect_btn.pack(side="right")

    def _build_filters_premium(self):
        tk.Label(self.filters, text="DISCOVERY FILTERS", bg=PANEL, fg=MUTED, font=(FONT, 7, "bold")).pack(side="left", padx=(15, 9), pady=11)
        self.fast_only = tk.BooleanVar(value=True); self.available_only = tk.BooleanVar(value=True); self.auto_connect = tk.BooleanVar(value=False)
        ttk.Checkbutton(self.filters, text="Fast", variable=self.fast_only, command=self._render).pack(side="left", padx=3)
        ttk.Checkbutton(self.filters, text="Online", variable=self.available_only, command=self._render).pack(side="left", padx=3)
        self.country = tk.StringVar(value="All"); self.city = tk.StringVar(value="All"); self.source = tk.StringVar(value="All")
        for label, var in (("COUNTRY", self.country), ("CITY", self.city), ("SOURCE", self.source)):
            tk.Label(self.filters, text=label, bg=PANEL, fg=MUTED, font=(FONT, 7, "bold")).pack(side="left", padx=(10, 4))
            cb = ttk.Combobox(self.filters, textvariable=var, state="readonly", width=11); cb.pack(side="left", padx=(0, 4)); cb.bind("<<ComboboxSelected>>", lambda _e: self._render())
            setattr(self, label.lower() + "_combo", cb)
        tk.Label(self.filters, text="MAX LATENCY", bg=PANEL, fg=MUTED, font=(FONT, 7, "bold")).pack(side="left", padx=(10, 4))
        self.max_ping = tk.IntVar(value=250); self.ping_spin = ttk.Spinbox(self.filters, from_=50, to=3000, increment=25, width=6, textvariable=self.max_ping, command=self._render); self.ping_spin.pack(side="left")
        tk.Label(self.filters, text="ms", bg=PANEL, fg=MUTED, font=(FONT, 8)).pack(side="left", padx=(3, 8))
        ttk.Checkbutton(self.filters, text="Auto Connect", variable=self.auto_connect, command=self._auto_connect_changed).pack(side="left", padx=4)

    def _focus_dashboard(self): self.header.focus_set()
    def _focus_servers(self): self.server_card.focus_set()
    def _focus_quick(self): self.quick.focus_set()

    def _on_resize(self, event):
        if event.widget is not self: return
        if getattr(self, "_resize_job", None): self.after_cancel(self._resize_job)
        self._resize_job = self.after(80, lambda: self._apply_responsive_layout(event.width))

    def _apply_responsive_layout(self, width):
        compact = width < 1080; narrow = width < 850
        if getattr(self, "compact", False) != compact:
            self.compact = compact
            if compact: self.sidebar.pack_forget()
            else: self.sidebar.pack(side="left", fill="y", before=self.content)
        pad = 14 if narrow else 18 if compact else 30
        for w in (self.header, self.hero, self.command, self.metrics, self.filters, self.quick, self.server_card, self.action_bar): w.pack_configure(padx=pad)
        if narrow:
            self.status_pill.pack_forget(); self.table_hint.configure(text="Horizontal scroll • double-click a route to connect"); self._set_table_mode("narrow")
        elif compact:
            self.status_pill.pack(side="right", pady=(8, 0)); self.table_hint.configure(text="Verified live routes"); self._set_table_mode("compact")
        else:
            self.status_pill.pack(side="right", pady=(8, 0)); self.table_hint.configure(text="Live verified routes"); self._set_table_mode("wide")

    def _set_table_mode(self, mode):
        widths = {"wide": (90, 110, 110, 185, 210, 90, 100, 105), "compact": (82, 92, 95, 145, 170, 78, 88, 90), "narrow": (72, 82, 84, 135, 150, 70, 78, 84)}[mode]
        for col, width in zip(self._table_columns, widths): self.tree.column(col, width=width, minwidth=52, stretch=True)

    def _render_quick(self, items):
        for w in self.quick_frame.winfo_children(): w.destroy()
        if not items:
            tk.Label(self.quick_frame, text="No verified routes match the current filters.", bg=PANEL, fg=MUTED, font=(FONT, 9)).pack(anchor="w", padx=12, pady=16); return
        count = 3 if self.compact else 5
        for s in items[:count]:
            ping = float(s.get("live_ping", 9999)); name = s.get("city") or s.get("country") or s.get("host") or "Unknown route"
            country = str(s.get("country") or "Global"); ips = s.get("ips") or [s.get("ip") or s.get("host", "")]
            c = self._card(self.quick_frame, bg=PANEL_2, accent=True, glow=ping < 100); c.pack(side="left", fill="x", expand=True, padx=4)
            top = tk.Frame(c, bg=PANEL_2); top.pack(fill="x", padx=12, pady=(9, 2))
            tk.Label(top, text="● ONLINE", bg=PANEL_2, fg=SUCCESS, font=(FONT, 7, "bold")).pack(side="left")
            tk.Label(top, text=f"{ping:.0f} ms", bg=PANEL_2, fg=CYAN, font=(FONT, 8, "bold")).pack(side="right")
            tk.Label(c, text=str(name)[:24], bg=PANEL_2, fg=TEXT, font=(FONT, 11, "bold")).pack(anchor="w", padx=12)
            tk.Label(c, text=f"{country}  •  {len(ips)} verified IP routes", bg=PANEL_2, fg=MUTED, font=(FONT, 8)).pack(anchor="w", padx=12, pady=(2, 3))
            meter = tk.Frame(c, bg=PANEL_3, height=5); meter.pack(fill="x", padx=12, pady=(4, 4))
            ratio = max(0.08, min(1.0, 1.0 - ping / 600.0)); tk.Frame(meter, bg=SUCCESS if ping <= 120 else WARNING, height=5, width=max(10, int(100 * ratio))).pack(side="left")
            tk.Label(c, text=str(ips[0])[:36], bg=PANEL_2, fg=MUTED, font=(FONT, 7)).pack(anchor="w", padx=12)
            self._button(c, "CONNECT  →", lambda x=s: self._connect([x]), "primary", True).pack(anchor="e", padx=10, pady=(6, 10))

    def _render(self):
        visible = self._eligible(); self.tree.delete(*self.tree.get_children())
        index = {id(s): i for i, s in enumerate(self.servers)}
        for s in visible:
            ping = float(s.get("live_ping", 9999)); ips = s.get("ips") or [s.get("ip") or s.get("host", "")]; fast = bool(s.get("available")) and ping <= int(self.max_ping.get())
            self.tree.insert("", "end", iid=str(index[id(s)]), values=("● FAST" if fast else "● ONLINE", s.get("country", ""), s.get("city", ""), s.get("host", "") or s.get("ip", ""), ", ".join(str(x) for x in ips[:5]), "—" if ping >= 9999 else f"{ping:.0f} ms", f"{float(s.get('speed', 0) or 0):.1f} Mbps" if s.get("speed") else "—", s.get("source", "")), tags=("fast" if fast else "online",))
        available = sum(bool(s.get("available")) for s in self.servers); fast = sum(bool(s.get("available")) and float(s.get("live_ping", 9999)) <= int(self.max_ping.get()) for s in self.servers); countries = len({s.get("country") for s in self.servers if s.get("country")})
        self.metric_vars["visible"].set(f"{len(visible):,}"); self.metric_vars["online"].set(f"{available:,}"); self.metric_vars["fast"].set(f"{fast:,}"); self.metric_vars["countries"].set(str(countries)); self.metric_vars["tested"].set(f"{len(self.servers):,}")
        self.table_hint.configure(text=f"{len(self.servers):,} catalog endpoints  •  {available:,} verified  •  live intelligence")
        self._render_quick(visible); self._update_combos()

    def _discover_worker(self):
        try:
            data = engine.discover(40)
            unique, seen = [], set()
            for s in data:
                ips = s.get("ips") or [s.get("ip") or s.get("host", "")]
                key = tuple(sorted(str(x) for x in ips if x)) or (str(s.get("host", "")),)
                if key in seen: continue
                seen.add(key); unique.append(s)
            tested = []
            with ThreadPoolExecutor(max_workers=72, thread_name_prefix="vpn-probe") as pool:
                futures = [pool.submit(self._probe, s) for s in unique[:1800]]
                for f in as_completed(futures):
                    if self.cancel_event.is_set(): break
                    try: tested.append(f.result())
                    except Exception: continue
            tested.sort(key=lambda s: (not s.get("available"), s.get("live_ping", 9999), -float(s.get("speed", 0) or 0), -float(s.get("rank", 0) or 0)))
            self.events.put(("servers", tested, f"Premium network scan complete • {len(tested):,} endpoints verified"))
        except Exception as exc:
            self.events.put(("error", None, f"Server discovery failed: {exc}"))

    def _set_busy(self, value):
        self.busy = value; state = "disabled" if value else "normal"
        for b in (self.refresh_btn, self.best_btn, self.sel_btn): b.configure(state=state)
        self.status_pill.configure(text="●  SCANNING NETWORK" if value else "●  READY", fg=WARNING if value else MUTED)
        if value: self._scan_started = time.monotonic()

    def _render_session(self):
        elapsed = int(time.monotonic() - self._session_started) if self._session_started else 0
        h, rem = divmod(elapsed, 3600); m, s = divmod(rem, 60)
        self.session_label.configure(text=f"SESSION  {h:02d}:{m:02d}:{s:02d}")
        self.after(500, self._render_session)

    def _connect(self, candidates):
        super()._connect(candidates)
        if candidates: self._session_started = time.monotonic()

    def disconnect(self):
        super().disconnect(); self._session_started = None
        self.session_label.configure(text="SESSION  00:00:00")


if __name__ == "__main__":
    App().mainloop()
