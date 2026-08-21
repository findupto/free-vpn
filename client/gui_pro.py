from __future__ import annotations

import queue
import threading
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor, as_completed
from tkinter import messagebox, ttk

import standalone_engine as engine
from gui import App as LegacyApp

BG = "#06080d"
SURFACE = "#0b1018"
PANEL = "#101722"
PANEL_2 = "#151e2c"
PANEL_3 = "#1a2535"
BORDER = "#263246"
BORDER_HI = "#3a4a63"
TEXT = "#f7f9fc"
MUTED = "#8b98ab"
ACCENT = "#765cff"
ACCENT_HI = "#9b89ff"
SUCCESS = "#31d7a4"
WARNING = "#ffbd69"
DANGER = "#ff647d"
CYAN = "#5bdcff"
FONT = "Segoe UI"


class App(LegacyApp):
    """Premium responsive dashboard layered over the existing VPN engine."""

    def __init__(self):
        super().__init__()

    def _configure_styles(self):
        s = ttk.Style(self)
        try:
            s.theme_use("clam")
        except tk.TclError:
            pass
        s.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=TEXT,
                    rowheight=46, borderwidth=0, font=(FONT, 9))
        s.configure("Treeview.Heading", background=PANEL_2, foreground=MUTED,
                    relief="flat", font=(FONT, 8, "bold"), padding=(10, 10))
        s.map("Treeview", background=[("selected", "#29364d")], foreground=[("selected", TEXT)])
        s.configure("TCombobox", fieldbackground=PANEL_2, background=PANEL_2,
                    foreground=TEXT, arrowcolor=MUTED, bordercolor=BORDER)
        s.map("TCombobox", fieldbackground=[("readonly", PANEL_2)], foreground=[("readonly", TEXT)])
        s.configure("TSpinbox", fieldbackground=PANEL_2, background=PANEL_2,
                    foreground=TEXT, arrowcolor=MUTED)
        s.configure("TCheckbutton", background=PANEL, foreground=TEXT, font=(FONT, 9))
        s.map("TCheckbutton", background=[("active", PANEL)])

    def _card(self, parent, bg=PANEL, accent=False):
        f = tk.Frame(parent, bg=bg, highlightthickness=1,
                     highlightbackground=BORDER_HI if accent else BORDER)
        return f

    def _pill(self, parent, text, bg=PANEL_2, fg=MUTED):
        return tk.Label(parent, text=text, bg=bg, fg=fg, padx=10, pady=5,
                        font=(FONT, 8, "bold"), highlightthickness=1,
                        highlightbackground=BORDER)

    def _button(self, parent, text, command, kind="secondary", compact=False):
        palette = {
            "primary": (ACCENT, "white", ACCENT_HI),
            "success": (SUCCESS, BG, "#5ce8bb"),
            "danger": (DANGER, BG, "#ff91a3"),
            "secondary": (PANEL_3, TEXT, "#26354a"),
            "ghost": (SURFACE, MUTED, PANEL_2),
        }
        bg, fg, active = palette[kind]
        b = tk.Button(parent, text=text, command=command, bg=bg, fg=fg,
                      activebackground=active, activeforeground=fg, relief="flat", bd=0,
                      highlightthickness=1, highlightbackground=BORDER_HI,
                      cursor="hand2", font=(FONT, 9 if compact else 10, "bold"),
                      padx=11 if compact else 15, pady=7 if compact else 10)
        b.bind("<Enter>", lambda _e: b.configure(bg=active))
        b.bind("<Leave>", lambda _e: b.configure(bg=bg))
        return b

    def _build(self):
        self.configure(bg=BG)
        self.root = tk.Frame(self, bg=BG)
        self.root.pack(fill="both", expand=True)

        self.sidebar = tk.Frame(self.root, bg=SURFACE, width=235,
                                highlightthickness=1, highlightbackground=BORDER)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        self._build_sidebar()

        self.content = tk.Frame(self.root, bg=BG)
        self.content.pack(side="left", fill="both", expand=True)
        self._build_main()
        self._apply_responsive_layout(self.winfo_width() or 1280)

    def _build_sidebar(self):
        brand = tk.Frame(self.sidebar, bg=SURFACE)
        brand.pack(fill="x", padx=18, pady=(22, 28))
        tk.Label(brand, text="F", bg=ACCENT, fg="white", width=3, pady=8,
                 font=(FONT, 15, "bold")).pack(side="left", padx=(0, 11))
        names = tk.Frame(brand, bg=SURFACE)
        names.pack(side="left")
        tk.Label(names, text="FINDUPTO", bg=SURFACE, fg=TEXT,
                 font=(FONT, 14, "bold")).pack(anchor="w")
        tk.Label(names, text="SECURE VPN NETWORK", bg=SURFACE, fg=MUTED,
                 font=(FONT, 7, "bold")).pack(anchor="w", pady=(1, 0))

        tk.Label(self.sidebar, text="WORKSPACE", bg=SURFACE, fg=MUTED,
                 font=(FONT, 7, "bold")).pack(anchor="w", padx=19, pady=(0, 8))
        self.nav_items = []
        for icon, label, command in (("⌂", "Dashboard", self._focus_dashboard),
                                     ("◉", "All Servers", self._focus_servers),
                                     ("⚡", "Fast Pool", self._focus_quick),
                                     ("◌", "Diagnostics", self.open_log)):
            b = tk.Button(self.sidebar, text=f"  {icon}   {label}", anchor="w",
                          command=command, bg=ACCENT if label == "Dashboard" else SURFACE,
                          fg="white" if label == "Dashboard" else MUTED,
                          activebackground=PANEL_2, activeforeground=TEXT, relief="flat", bd=0,
                          cursor="hand2", font=(FONT, 10, "bold"), padx=17, pady=11)
            b.pack(fill="x", padx=10, pady=2)
            self.nav_items.append(b)

        tk.Frame(self.sidebar, bg=SURFACE).pack(fill="both", expand=True)
        health = self._card(self.sidebar, bg=PANEL, accent=True)
        health.pack(fill="x", padx=14, pady=14)
        top = tk.Frame(health, bg=PANEL)
        top.pack(fill="x", padx=12, pady=(11, 5))
        tk.Label(top, text="●", bg=PANEL, fg=SUCCESS, font=(FONT, 11, "bold")).pack(side="left")
        tk.Label(top, text="NETWORK STATUS", bg=PANEL, fg=MUTED,
                 font=(FONT, 7, "bold")).pack(side="left", padx=6)
        self.side_status = tk.StringVar(value="Ready to connect")
        tk.Label(health, textvariable=self.side_status, bg=PANEL, fg=TEXT,
                 font=(FONT, 9, "bold"), wraplength=185, justify="left").pack(anchor="w", padx=12, pady=(0, 11))
        tk.Label(self.sidebar, text=f"v{engine.APP_VERSION}  •  Encrypted tunnel", bg=SURFACE,
                 fg=MUTED, font=(FONT, 7)).pack(anchor="w", padx=18, pady=(0, 18))

    def _build_main(self):
        self.header = tk.Frame(self.content, bg=BG)
        self.header.pack(fill="x", padx=28, pady=(20, 12))
        left = tk.Frame(self.header, bg=BG)
        left.pack(side="left", fill="x", expand=True)
        eyebrow = tk.Label(left, text="PRIVATE NETWORK  /  CONTROL CENTER", bg=BG, fg=ACCENT_HI,
                           font=(FONT, 8, "bold"))
        eyebrow.pack(anchor="w")
        tk.Label(left, text="Connect without the guesswork.", bg=BG, fg=TEXT,
                 font=(FONT, 24, "bold")).pack(anchor="w", pady=(2, 0))
        tk.Label(left, text="Discover, benchmark and connect to the fastest verified VPN endpoints.",
                 bg=BG, fg=MUTED, font=(FONT, 9)).pack(anchor="w", pady=(2, 0))
        self.status = tk.StringVar(value="Preparing server intelligence…")
        self.status_pill = self._pill(self.header, "●  READY", PANEL_2, MUTED)
        self.status_pill.pack(side="right", padx=(12, 0), pady=(10, 0))

        self.hero = self._card(self.content, bg=SURFACE, accent=True)
        self.hero.pack(fill="x", padx=28, pady=(0, 12))
        hleft = tk.Frame(self.hero, bg=SURFACE)
        hleft.pack(side="left", fill="x", expand=True, padx=18, pady=17)
        tk.Label(hleft, text="SMART CONNECT", bg=SURFACE, fg=CYAN,
                 font=(FONT, 8, "bold")).pack(anchor="w")
        tk.Label(hleft, text="Let Findupto choose the best live route.", bg=SURFACE, fg=TEXT,
                 font=(FONT, 13, "bold")).pack(anchor="w", pady=(3, 1))
        tk.Label(hleft, text="Live latency + availability + speed ranking", bg=SURFACE, fg=MUTED,
                 font=(FONT, 8)).pack(anchor="w")
        self.best_btn = self._button(self.hero, "✦  CONNECT FASTEST", self.best, "primary")
        self.best_btn.pack(side="right", padx=18, pady=17)

        self.filters = self._card(self.content)
        self.filters.pack(fill="x", padx=28, pady=(0, 12))
        self._build_filters()

        self.stats = tk.Frame(self.content, bg=BG)
        self.stats.pack(fill="x", padx=28, pady=(0, 12))
        self.stat_cards = {}
        for key, label, icon in (("shown", "VISIBLE", "◌"), ("available", "ONLINE", "●"),
                                 ("fast", "FAST < 250ms", "⚡"), ("pool", "QUICK POOL", "✦"),
                                 ("tested", "ENDPOINTS TESTED", "◉")):
            c = self._card(self.stats)
            c.pack(side="left", fill="x", expand=True, padx=(0, 7))
            tk.Label(c, text=icon, bg=PANEL, fg=ACCENT_HI, font=(FONT, 12, "bold")).pack(anchor="w", padx=13, pady=(9, 0))
            v = tk.StringVar(value="0")
            tk.Label(c, textvariable=v, bg=PANEL, fg=TEXT, font=(FONT, 18, "bold")).pack(anchor="w", padx=13)
            tk.Label(c, text=label, bg=PANEL, fg=MUTED, font=(FONT, 7, "bold")).pack(anchor="w", padx=13, pady=(0, 9))
            self.stat_cards[key] = v

        self.quick = self._card(self.content, accent=True)
        self.quick.pack(fill="x", padx=28, pady=(0, 12))
        qhead = tk.Frame(self.quick, bg=PANEL)
        qhead.pack(fill="x", padx=15, pady=(11, 6))
        tk.Label(qhead, text="⚡ FAST LANE", bg=PANEL, fg=TEXT, font=(FONT, 12, "bold")).pack(side="left")
        self.speed_status = tk.StringVar(value="Scanning live endpoints…")
        tk.Label(qhead, textvariable=self.speed_status, bg=PANEL, fg=SUCCESS,
                 font=(FONT, 8, "bold")).pack(side="right")
        self.quick_frame = tk.Frame(self.quick, bg=PANEL)
        self.quick_frame.pack(fill="x", padx=10, pady=(0, 12))

        self.server_card = self._card(self.content)
        self.server_card.pack(fill="both", expand=True, padx=28, pady=(0, 12))
        top = tk.Frame(self.server_card, bg=PANEL)
        top.pack(fill="x", padx=15, pady=(11, 8))
        tk.Label(top, text="SERVER EXPLORER", bg=PANEL, fg=TEXT, font=(FONT, 12, "bold")).pack(side="left")
        self.table_hint = tk.Label(top, text="Live verified endpoints", bg=PANEL, fg=MUTED, font=(FONT, 8))
        self.table_hint.pack(side="right")
        frame = tk.Frame(self.server_card, bg=PANEL)
        frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        cols = ("status", "country", "city", "host", "ips", "ping", "speed", "source")
        self.tree = ttk.Treeview(frame, columns=cols, show="headings", selectmode="browse")
        self._table_columns = cols
        for col in cols:
            self.tree.heading(col, text=col.upper())
            self.tree.column(col, width=100, minwidth=58, anchor="w", stretch=True)
        self.tree.tag_configure("fast", foreground=SUCCESS)
        self.tree.tag_configure("online", foreground=TEXT)
        y = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        x = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=y.set, xscrollcommand=x.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        y.grid(row=0, column=1, sticky="ns")
        x.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        self.tree.bind("<Double-1>", lambda _e: self.selected())

        self.action_bar = tk.Frame(self.content, bg=BG)
        self.action_bar.pack(fill="x", padx=28, pady=(0, 17))
        self.refresh_btn = self._button(self.action_bar, "↻  SCAN SERVERS", self.refresh)
        self.refresh_btn.pack(side="left")
        self.sel_btn = self._button(self.action_bar, "➜  CONNECT SELECTED", self.selected)
        self.sel_btn.pack(side="left", padx=7)
        self.diag_btn = self._button(self.action_bar, "◉  DIAGNOSTICS", self.open_log, "ghost")
        self.diag_btn.pack(side="left")
        self.disconnect_btn = self._button(self.action_bar, "■  DISCONNECT", self.disconnect, "danger")
        self.disconnect_btn.pack(side="right")

    def _build_filters(self):
        tk.Label(self.filters, text="FILTERS", bg=PANEL, fg=MUTED,
                 font=(FONT, 7, "bold")).pack(side="left", padx=(14, 8), pady=11)
        self.fast_only = tk.BooleanVar(value=True)
        self.available_only = tk.BooleanVar(value=True)
        self.auto_connect = tk.BooleanVar(value=False)
        ttk.Checkbutton(self.filters, text="Fast", variable=self.fast_only, command=self._render).pack(side="left", padx=4)
        ttk.Checkbutton(self.filters, text="Available", variable=self.available_only, command=self._render).pack(side="left", padx=4)
        self.country = tk.StringVar(value="All")
        self.city = tk.StringVar(value="All")
        self.source = tk.StringVar(value="All")
        for label, var in (("COUNTRY", self.country), ("CITY", self.city), ("SOURCE", self.source)):
            tk.Label(self.filters, text=label, bg=PANEL, fg=MUTED, font=(FONT, 7, "bold")).pack(side="left", padx=(10, 4))
            cb = ttk.Combobox(self.filters, textvariable=var, state="readonly", width=12)
            cb.pack(side="left", padx=(0, 4))
            cb.bind("<<ComboboxSelected>>", lambda _e: self._render())
            setattr(self, label.lower() + "_combo", cb)
        tk.Label(self.filters, text="MAX PING", bg=PANEL, fg=MUTED, font=(FONT, 7, "bold")).pack(side="left", padx=(10, 4))
        self.max_ping = tk.IntVar(value=250)
        self.ping_spin = ttk.Spinbox(self.filters, from_=50, to=2000, increment=25, width=6,
                                     textvariable=self.max_ping, command=self._render)
        self.ping_spin.pack(side="left")
        tk.Label(self.filters, text="ms", bg=PANEL, fg=MUTED, font=(FONT, 8)).pack(side="left", padx=(3, 8))
        ttk.Checkbutton(self.filters, text="Auto Connect", variable=self.auto_connect,
                        command=self._auto_connect_changed).pack(side="left", padx=4)

    def _focus_dashboard(self): self.header.focus_set()
    def _focus_servers(self): self.server_card.focus_set()
    def _focus_quick(self): self.quick.focus_set()

    def _on_resize(self, event):
        if event.widget is not self:
            return
        if getattr(self, "_resize_job", None):
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(80, lambda: self._apply_responsive_layout(event.width))

    def _apply_responsive_layout(self, width):
        compact = width < 1080
        narrow = width < 860
        if getattr(self, "compact", False) != compact:
            self.compact = compact
            if compact:
                self.sidebar.pack_forget()
            else:
                self.sidebar.pack(side="left", fill="y", before=self.content)
        pad = 14 if narrow else 18 if compact else 28
        for w in (self.header, self.hero, self.filters, self.stats, self.quick, self.server_card, self.action_bar):
            w.pack_configure(padx=pad)
        if narrow:
            self.status_pill.pack_forget()
            self.table_hint.configure(text="Scroll horizontally • double-click to connect")
            self._set_table_mode("narrow")
        elif compact:
            self.status_pill.pack(side="right", padx=(12, 0), pady=(10, 0))
            self.table_hint.configure(text="Verified endpoints")
            self._set_table_mode("compact")
        else:
            self.status_pill.pack(side="right", padx=(12, 0), pady=(10, 0))
            self.table_hint.configure(text="Live verified endpoints")
            self._set_table_mode("wide")

    def _set_table_mode(self, mode):
        widths = {"wide": (92, 105, 110, 190, 220, 75, 95, 105),
                  "compact": (82, 92, 95, 150, 175, 70, 85, 90),
                  "narrow": (74, 84, 86, 140, 155, 68, 80, 84)}[mode]
        for col, width in zip(self._table_columns, widths):
            self.tree.column(col, width=width, minwidth=52, stretch=True)

    def _render_quick(self, items):
        for w in self.quick_frame.winfo_children():
            w.destroy()
        if not items:
            tk.Label(self.quick_frame, text="No matching verified servers. Try widening MAX PING.",
                     bg=PANEL, fg=MUTED, font=(FONT, 9)).pack(anchor="w", padx=10, pady=14)
            return
        count = 3 if self.compact else 5
        for s in items[:count]:
            ping = float(s.get("live_ping", 9999))
            name = s.get("city") or s.get("country") or s.get("host") or "Server"
            card = self._card(self.quick_frame, bg=PANEL_2, accent=True)
            card.pack(side="left", fill="x", expand=True, padx=3)
            top = tk.Frame(card, bg=PANEL_2)
            top.pack(fill="x", padx=10, pady=(9, 1))
            tk.Label(top, text="●", bg=PANEL_2, fg=SUCCESS, font=(FONT, 10, "bold")).pack(side="left")
            tk.Label(top, text=name, bg=PANEL_2, fg=TEXT, font=(FONT, 9, "bold")).pack(side="left", padx=5)
            tk.Label(card, text=f"{ping:.0f} ms  •  {s.get('country', 'Unknown')}", bg=PANEL_2,
                     fg=MUTED, font=(FONT, 8)).pack(anchor="w", padx=10)
            b = self._button(card, "CONNECT", lambda x=s: self._connect([x]), "primary", compact=True)
            b.pack(anchor="e", padx=9, pady=(5, 8))

    def _render(self):
        visible = self._eligible()
        self.tree.delete(*self.tree.get_children())
        index = {id(s): i for i, s in enumerate(self.servers)}
        for s in visible:
            ping = float(s.get("live_ping", 9999))
            ips = s.get("ips") or [s.get("ip") or s.get("host", "")]
            fast = bool(s.get("available")) and ping <= 250
            self.tree.insert("", "end", iid=str(index[id(s)]), values=(
                "● FAST" if fast else "● ONLINE", s.get("country", ""), s.get("city", ""),
                s.get("host", "") or s.get("ip", ""), ", ".join(str(x) for x in ips[:4]),
                "—" if ping >= 9999 else f"{ping:.0f} ms",
                f"{float(s.get('speed', 0) or 0):.1f} Mbps" if s.get("speed") else "—",
                s.get("source", ""),
            ), tags=("fast" if fast else "online",))
        available = sum(bool(s.get("available")) for s in self.servers)
        fast = sum(bool(s.get("available")) and float(s.get("live_ping", 9999)) <= 250 for s in self.servers)
        self.stat_cards["shown"].set(str(len(visible)))
        self.stat_cards["available"].set(str(available))
        self.stat_cards["fast"].set(str(fast))
        self.stat_cards["pool"].set(str(len(self._eligible()[:12])))
        self.stat_cards["tested"].set(str(len(self.servers)))
        self._render_quick(visible)
        self._update_combos()

    def _discover_worker(self):
        try:
            data = engine.discover(20)
            tested = []
            with ThreadPoolExecutor(max_workers=48, thread_name_prefix="vpn-probe") as pool:
                futures = [pool.submit(self._probe, s) for s in data[:250]]
                for f in as_completed(futures):
                    if self.cancel_event.is_set():
                        break
                    try:
                        tested.append(f.result())
                    except Exception:
                        continue
            tested.sort(key=lambda s: (not s.get("available"), s.get("live_ping", 9999),
                                       -float(s.get("speed", 0) or 0), -float(s.get("rank", 0) or 0)))
            self.events.put(("servers", tested, f"Fast pool ready • {len(tested)} endpoints tested"))
        except Exception as exc:
            self.events.put(("error", None, f"Server discovery failed: {exc}"))

    def _set_busy(self, value):
        self.busy = value
        state = "disabled" if value else "normal"
        for b in (self.refresh_btn, self.best_btn, self.sel_btn):
            b.configure(state=state)
        self.status_pill.configure(text="●  SCANNING" if value else "●  READY",
                                   fg=WARNING if value else MUTED)

    def _pump(self):
        try:
            while True:
                kind, data, msg = self.events.get_nowait()
                if kind == "servers":
                    self.servers = data or []
                    self._render()
                    self._set_busy(False)
                    self.status.set(msg)
                    self.side_status.set(f"{len(self.servers)} live endpoints verified")
                    self.speed_status.set("● LIVE • pool verified")
                    self._auto_connect_changed()
                elif kind == "status":
                    self.status.set(msg)
                    self.side_status.set("Establishing secure tunnel…")
                elif kind == "connected":
                    self._set_busy(False)
                    self.status.set(msg)
                    self.side_status.set("● Tunnel connected")
                    self.speed_status.set("● CONNECTED • tunnel verified")
                    self.status_pill.configure(text="●  CONNECTED", fg=SUCCESS)
                elif kind == "error":
                    self._set_busy(False)
                    self.status.set("Connection unavailable")
                    self.side_status.set("Connection failed")
                    self.speed_status.set("● OFFLINE")
                    self.status_pill.configure(text="●  OFFLINE", fg=DANGER)
                    messagebox.showerror("Findupto VPN", msg)
        except queue.Empty:
            pass
        self.after(100, self._pump)
