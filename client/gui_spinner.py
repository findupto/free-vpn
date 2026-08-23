from __future__ import annotations

import time
import tkinter as tk
from tkinter import ttk

from country_spinner import CountrySpinner
from connection_progress import install_connection_progress
from gui_elite import App as EliteApp, BG, SURFACE, PANEL, PANEL_2, PANEL_3, BORDER, BORDER_HI, TEXT, MUTED, ACCENT, ACCENT_2, SUCCESS, WARNING, DANGER, CYAN, FONT

FLAGS = {
    "Denmark": "DK", "United States": "US", "Japan": "JP", "Germany": "DE",
    "United Kingdom": "UK", "Canada": "CA", "France": "FR", "Netherlands": "NL",
    "Singapore": "SG", "Australia": "AU", "Switzerland": "CH", "Sweden": "SE",
    "Norway": "NO", "Finland": "FI", "Poland": "PL", "Brazil": "BR",
    "India": "IN", "Hong Kong": "HK", "Korea Republic of": "KR", "Taiwan": "TW",
}


class App(EliteApp):
    """Premium connection-first desktop experience.

    The networking/session engine remains inherited from the existing client;
    this class deliberately keeps the UI focused on the three things users
    need most: current protection, server selection and connection control.
    """

    def __init__(self):
        self.spinner_enabled = False
        self.spinner_interval = 3
        self.spinner_countdown = 3
        self.spinner_current = None
        self.spinner_next = None
        self.spinner_history = []
        self._spinner_started = None
        self._spinner_rotating = False
        self._selected_server = None
        self.country_spinner = CountrySpinner(self._spinner_connect, self._spinner_disconnect)
        super().__init__()

    def _configure_styles(self):
        super()._configure_styles()
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=TEXT,
                        rowheight=52, borderwidth=0, font=(FONT, 9))
        style.configure("Treeview.Heading", background=PANEL_2, foreground=MUTED,
                        relief="flat", font=(FONT, 8, "bold"), padding=(12, 10))
        style.map("Treeview", background=[("selected", "#242f43")], foreground=[("selected", TEXT)])
        style.configure("TCombobox", fieldbackground=PANEL_2, background=PANEL_2,
                        foreground=TEXT, arrowcolor=MUTED, padding=7)
        style.map("TCombobox", fieldbackground=[("readonly", PANEL_2)], foreground=[("readonly", TEXT)])
        style.configure("TSpinbox", fieldbackground=PANEL_2, background=PANEL_2,
                        foreground=TEXT, arrowcolor=MUTED, padding=6)

    def _card(self, parent, bg=PANEL, accent=False, glow=False):
        return tk.Frame(parent, bg=bg, highlightthickness=2 if glow else 1,
                        highlightbackground=ACCENT if glow else (BORDER_HI if accent else BORDER),
                        highlightcolor=ACCENT)

    def _button(self, parent, text, command, kind="secondary", compact=False):
        palette = {
            "primary": (ACCENT, "white", ACCENT_2),
            "success": (SUCCESS, BG, "#62edc1"),
            "danger": (DANGER, BG, "#ff93a4"),
            "secondary": (PANEL_3, TEXT, "#29384f"),
            "ghost": (SURFACE, MUTED, PANEL_2),
            "blue": ("#3f78e8", "white", "#6399ff"),
        }
        bg, fg, hover = palette[kind]
        b = tk.Button(parent, text=text, command=command, bg=bg, fg=fg,
                      activebackground=hover, activeforeground=fg, relief="flat", bd=0,
                      highlightthickness=1, highlightbackground=BORDER_HI,
                      cursor="hand2", font=(FONT, 9 if compact else 10, "bold"),
                      padx=12 if compact else 17, pady=7 if compact else 10)
        b._base_bg, b._hover_bg = bg, hover
        b.bind("<Enter>", lambda _e: b.configure(bg=b._hover_bg))
        b.bind("<Leave>", lambda _e: b.configure(bg=b._base_bg))
        return b

    def _pill(self, parent, text, bg=PANEL_2, fg=MUTED):
        return tk.Label(parent, text=text, bg=bg, fg=fg, padx=11, pady=6,
                        font=(FONT, 8, "bold"), highlightthickness=1, highlightbackground=BORDER_HI)

    def _build(self):
        self.configure(bg=BG)
        self.root = tk.Frame(self, bg=BG)
        self.root.pack(fill="both", expand=True)
        self.sidebar = tk.Frame(self.root, bg=SURFACE, width=78,
                                highlightthickness=1, highlightbackground=BORDER)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        self._build_sidebar()
        self.content = tk.Frame(self.root, bg=BG)
        self.content.pack(side="left", fill="both", expand=True)
        self._build_premium_content()
        self.bind("<Configure>", self._on_resize)
        self._apply_responsive_layout(self.winfo_width() or 1280)
        self.after(500, self._render_session)
        self.after(250, self._spinner_tick)

    def _build_sidebar(self):
        mark = tk.Frame(self.sidebar, bg=ACCENT, width=42, height=42)
        mark.pack(pady=(20, 30)); mark.pack_propagate(False)
        tk.Label(mark, text="F", bg=ACCENT, fg="white", font=(FONT, 17, "bold")).pack(expand=True)
        self.nav_items = []
        for icon, label, command in (("⌂", "Dashboard", self._focus_dashboard),
                                     ("◉", "Servers", self._focus_servers),
                                     ("⚡", "Fast", self._focus_quick),
                                     ("◌", "Diagnostics", self.open_log)):
            b = tk.Button(self.sidebar, text=icon, command=command, bg=ACCENT if label == "Dashboard" else SURFACE,
                          fg="white" if label == "Dashboard" else MUTED, activebackground=PANEL_2,
                          activeforeground=TEXT, relief="flat", bd=0, cursor="hand2",
                          font=(FONT, 15, "bold"), width=3, pady=9)
            b.pack(pady=3); self.nav_items.append(b)
        tk.Frame(self.sidebar, bg=SURFACE).pack(fill="both", expand=True)
        self.side_status = tk.StringVar(value="Ready")
        status = self._card(self.sidebar, bg=PANEL, accent=True)
        status.pack(fill="x", padx=9, pady=9)
        tk.Label(status, text="●", bg=PANEL, fg=SUCCESS, font=(FONT, 12, "bold")).pack(pady=(8, 1))
        tk.Label(status, textvariable=self.side_status, bg=PANEL, fg=TEXT,
                 font=(FONT, 7, "bold"), wraplength=58, justify="center").pack(padx=5, pady=(0, 9))

    def _build_premium_content(self):
        # Header: intentionally quiet, like modern premium VPN clients.
        self.header = tk.Frame(self.content, bg=BG)
        self.header.pack(fill="x", padx=26, pady=(20, 12))
        brand = tk.Frame(self.header, bg=BG); brand.pack(side="left", fill="x", expand=True)
        tk.Label(brand, text="FINDUPTO VPN", bg=BG, fg=TEXT, font=(FONT, 20, "bold")).pack(anchor="w")
        tk.Label(brand, text="Private, verified, effortless.", bg=BG, fg=MUTED, font=(FONT, 9)).pack(anchor="w", pady=(2, 0))
        self.status_pill = self._pill(self.header, "●  READY", PANEL_2, MUTED)
        self.status_pill.pack(side="right", pady=(3, 0))

        # Connection hero: the visual center of the application.
        self.hero = self._card(self.content, bg=SURFACE, accent=True, glow=True)
        self.hero.pack(fill="x", padx=26, pady=(0, 14))
        hero_top = tk.Frame(self.hero, bg=SURFACE); hero_top.pack(fill="x", padx=22, pady=(20, 8))
        left = tk.Frame(hero_top, bg=SURFACE); left.pack(side="left", fill="x", expand=True)
        tk.Label(left, text="PROTECTION STATUS", bg=SURFACE, fg=MUTED, font=(FONT, 8, "bold")).pack(anchor="w")
        self.connection_title = tk.Label(left, text="Not connected", bg=SURFACE, fg=TEXT, font=(FONT, 23, "bold"))
        self.connection_title.pack(anchor="w", pady=(4, 0))
        self.connection_detail = tk.Label(left, text="Choose a location to secure your connection.", bg=SURFACE, fg=MUTED, font=(FONT, 9))
        self.connection_detail.pack(anchor="w", pady=(3, 0))
        self.ip_value = tk.StringVar(value="—")
        ipbox = tk.Frame(hero_top, bg=PANEL_2, highlightthickness=1, highlightbackground=BORDER_HI)
        ipbox.pack(side="right", padx=(18, 0))
        tk.Label(ipbox, text="CURRENT EXIT IP", bg=PANEL_2, fg=MUTED, font=(FONT, 7, "bold")).pack(anchor="w", padx=14, pady=(9, 1))
        tk.Label(ipbox, textvariable=self.ip_value, bg=PANEL_2, fg=CYAN, font=(FONT, 15, "bold"), padx=14, pady=8).pack(anchor="w")
        controls = tk.Frame(self.hero, bg=SURFACE); controls.pack(fill="x", padx=22, pady=(9, 20))
        self.best_btn = self._button(controls, "✦  CONNECT FASTEST", self.best, "primary")
        self.best_btn.pack(side="left")
        self.change_ip_btn = self._button(controls, "↻  CHANGE IP", self._change_ip, "success")
        self.change_ip_btn.pack(side="left", padx=8)
        self.disconnect_btn = self._button(controls, "■  DISCONNECT", self.disconnect, "danger")
        self.disconnect_btn.pack(side="left")
        self.session_label = tk.Label(controls, text="00:00:00", bg=PANEL_2, fg=CYAN,
                                      padx=12, pady=9, font=(FONT, 8, "bold"), highlightthickness=1, highlightbackground=BORDER_HI)
        self.session_label.pack(side="right")
        tk.Label(controls, text="SESSION", bg=SURFACE, fg=MUTED, font=(FONT, 7, "bold")).pack(side="right", padx=8)

        # Search + compact filters.
        self.filters = self._card(self.content, bg=PANEL)
        self.filters.pack(fill="x", padx=26, pady=(0, 12))
        self._build_filters_modern()

        # Main workspace: server explorer + quick routes.
        workspace = tk.Frame(self.content, bg=BG)
        workspace.pack(fill="both", expand=True, padx=26, pady=(0, 12))
        self.server_card = self._card(workspace, bg=PANEL)
        self.server_card.pack(side="left", fill="both", expand=True, padx=(0, 8))
        self._build_server_explorer()
        self.quick = self._card(workspace, bg=PANEL, accent=True)
        self.quick.pack(side="right", fill="y", padx=(8, 0))
        self.quick.configure(width=285); self.quick.pack_propagate(False)
        self._build_fast_panel()

        # A small route inspector replaces the old oversized dashboard sections.
        self.ip_panel = self._card(self.content, bg=SURFACE)
        self.ip_panel.pack(fill="x", padx=26, pady=(0, 10))
        self._build_ip_inspector()

        self.action_bar = tk.Frame(self.content, bg=BG)
        self.action_bar.pack(fill="x", padx=26, pady=(0, 15))
        self.refresh_btn = self._button(self.action_bar, "↻  SCAN NETWORK", self.refresh, "blue")
        self.refresh_btn.pack(side="left")
        self.sel_btn = self._button(self.action_bar, "CONNECT SELECTED", self.selected, "secondary")
        self.sel_btn.pack(side="left", padx=7)
        self.diag_btn = self._button(self.action_bar, "DIAGNOSTICS", self.open_log, "ghost")
        self.diag_btn.pack(side="left")
        self.status = tk.StringVar(value="Ready to scan the verified network")
        tk.Label(self.action_bar, textvariable=self.status, bg=BG, fg=MUTED, font=(FONT, 8)).pack(side="right", padx=4)

        self.spinner_panel = None
        self.spinner_badge = self._pill(self.content, "OFF")
        self.spinner_toggle = self._button(self.content, "ENABLE SPINNER", self.toggle_spinner, "ghost", True)
        self.spinner_countdown_label = tk.Label(self.content, text="", bg=BG, fg=MUTED)
        self.spinner_history_label = tk.Label(self.content, text="", bg=BG, fg=MUTED)
        self.spinner_current_label = tk.Label(self.content, text="", bg=BG, fg=TEXT)
        self.spinner_next_label = tk.Label(self.content, text="", bg=BG, fg=ACCENT_2)
        self.spinner_interval_var = tk.StringVar(value="3 seconds")

    def _build_filters_modern(self):
        tk.Label(self.filters, text="LOCATIONS", bg=PANEL, fg=MUTED, font=(FONT, 7, "bold")).pack(side="left", padx=(14, 8), pady=10)
        self.country = tk.StringVar(value="All"); self.city = tk.StringVar(value="All"); self.source = tk.StringVar(value="All")
        for label, var in (("COUNTRY", self.country), ("CITY", self.city), ("SOURCE", self.source)):
            cb = ttk.Combobox(self.filters, textvariable=var, state="readonly", width=12)
            cb.pack(side="left", padx=3, pady=7); cb.bind("<<ComboboxSelected>>", lambda _e: self._render())
            setattr(self, label.lower() + "_combo", cb)
        self.fast_only = tk.BooleanVar(value=True); self.available_only = tk.BooleanVar(value=True); self.auto_connect = tk.BooleanVar(value=False)
        self.max_ping = tk.IntVar(value=250)
        ttk.Checkbutton(self.filters, text="Fast", variable=self.fast_only, command=self._render).pack(side="left", padx=(12, 3))
        ttk.Checkbutton(self.filters, text="Online", variable=self.available_only, command=self._render).pack(side="left", padx=3)
        tk.Label(self.filters, text="MAX", bg=PANEL, fg=MUTED, font=(FONT, 7, "bold")).pack(side="left", padx=(10, 3))
        self.ping_spin = ttk.Spinbox(self.filters, from_=50, to=2000, increment=25, width=6, textvariable=self.max_ping, command=self._render)
        self.ping_spin.pack(side="left", padx=2)
        tk.Label(self.filters, text="ms", bg=PANEL, fg=MUTED, font=(FONT, 8)).pack(side="left", padx=2)
        ttk.Checkbutton(self.filters, text="Auto", variable=self.auto_connect, command=self._auto_connect_changed).pack(side="left", padx=8)
        self.search_var = tk.StringVar()
        search = tk.Entry(self.filters, textvariable=self.search_var, bg=PANEL_2, fg=TEXT, insertbackground=TEXT,
                          relief="flat", highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT,
                          font=(FONT, 9), width=24)
        search.pack(side="right", padx=12, pady=7, ipady=6)
        search.insert(0, "Search country, city or endpoint")
        search.bind("<FocusIn>", lambda _e: search.delete(0, "end") if search.get() == "Search country, city or endpoint" else None)
        search.bind("<KeyRelease>", lambda _e: self._render())

    def _build_server_explorer(self):
        top = tk.Frame(self.server_card, bg=PANEL); top.pack(fill="x", padx=16, pady=(12, 8))
        tk.Label(top, text="SERVER LOCATIONS", bg=PANEL, fg=TEXT, font=(FONT, 12, "bold")).pack(side="left")
        self.table_hint = tk.Label(top, text="Verified live endpoints", bg=PANEL, fg=MUTED, font=(FONT, 8)); self.table_hint.pack(side="right")
        frame = tk.Frame(self.server_card, bg=PANEL); frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        cols = ("status", "country", "city", "endpoint", "ping", "speed", "routes")
        self._table_columns = cols
        self.tree = ttk.Treeview(frame, columns=cols, show="headings", selectmode="browse")
        headings = ("STATUS", "COUNTRY", "CITY", "ENDPOINT", "PING", "SPEED", "ROUTES")
        widths = (78, 105, 110, 185, 70, 85, 80)
        for col, heading, width in zip(cols, headings, widths):
            self.tree.heading(col, text=heading); self.tree.column(col, width=width, minwidth=55, stretch=True)
        self.tree.tag_configure("fast", foreground=SUCCESS); self.tree.tag_configure("online", foreground=TEXT)
        y = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview); y.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=y.set); self.tree.grid(row=0, column=0, sticky="nsew")
        frame.rowconfigure(0, weight=1); frame.columnconfigure(0, weight=1)
        self.tree.bind("<<TreeviewSelect>>", self._on_server_selected, add="+")
        self.tree.bind("<Double-1>", lambda _e: self.selected())

    def _build_fast_panel(self):
        head = tk.Frame(self.quick, bg=PANEL); head.pack(fill="x", padx=15, pady=(13, 8))
        tk.Label(head, text="FASTEST", bg=PANEL, fg=TEXT, font=(FONT, 12, "bold")).pack(side="left")
        self.speed_status = tk.StringVar(value="Waiting for scan")
        tk.Label(head, textvariable=self.speed_status, bg=PANEL, fg=SUCCESS, font=(FONT, 7, "bold")).pack(anchor="e", pady=(2, 0))
        self.quick_frame = tk.Frame(self.quick, bg=PANEL); self.quick_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def _build_ip_inspector(self):
        head = tk.Frame(self.ip_panel, bg=SURFACE); head.pack(fill="x", padx=15, pady=(10, 7))
        tk.Label(head, text="ROUTE DETAILS", bg=SURFACE, fg=MUTED, font=(FONT, 7, "bold")).pack(side="left")
        self.ip_summary = tk.Label(head, text="SELECT A SERVER", bg=PANEL_2, fg=MUTED, padx=10, pady=5, font=(FONT, 7, "bold")); self.ip_summary.pack(side="right")
        self.ip_route_title = tk.Label(self.ip_panel, text="Select a server to inspect verified exit routes", bg=SURFACE, fg=TEXT, font=(FONT, 9, "bold")); self.ip_route_title.pack(anchor="w", padx=15)
        self.ip_route_meta = tk.Label(self.ip_panel, text="", bg=SURFACE, fg=MUTED, font=(FONT, 8)); self.ip_route_meta.pack(anchor="w", padx=15, pady=(2, 8))
        self.ip_list_canvas = tk.Canvas(self.ip_panel, height=50, bg=SURFACE, highlightthickness=0, bd=0); self.ip_list_canvas.pack(fill="x", padx=12, pady=(0, 9))
        self.ip_list_inner = tk.Frame(self.ip_list_canvas, bg=SURFACE); self.ip_list_window = self.ip_list_canvas.create_window((0, 0), window=self.ip_list_inner, anchor="nw")
        self._show_ip_empty()

    def _show_ip_empty(self):
        for w in self.ip_list_inner.winfo_children(): w.destroy()
        tk.Label(self.ip_list_inner, text="No route selected", bg=SURFACE, fg=MUTED, font=(FONT, 8)).pack(padx=8, pady=8)
        self.ip_list_inner.update_idletasks(); self.ip_list_canvas.configure(scrollregion=self.ip_list_canvas.bbox("all"))

    def _on_server_selected(self, _event=None):
        selection = self.tree.selection()
        if not selection: return
        try: server = self.servers[int(selection[0])]
        except (ValueError, IndexError, TypeError): return
        self._selected_server = server; self._render_ip_inspector(server)

    def _render_ip_inspector(self, server):
        country = server.get("country") or "Global"; city = server.get("city") or "Any city"; host = server.get("host") or server.get("ip") or "Unknown"
        ips = [str(x) for x in (server.get("ips") or []) if x]
        if not ips and server.get("ip"): ips = [str(server.get("ip"))]
        if not ips: ips = [host]
        ping = float(server.get("live_ping", 9999) or 9999); speed = float(server.get("speed", 0) or 0)
        self.ip_summary.configure(text=f"{len(ips)} VERIFIED ROUTES", fg=SUCCESS if ips else MUTED)
        self.ip_route_title.configure(text=f"{FLAGS.get(country, 'GLOBAL')}  {country}  ·  {city}")
        self.ip_route_meta.configure(text=f"{host}   ·   {'—' if ping >= 9999 else f'{ping:.0f} ms'}   ·   {'—' if not speed else f'{speed:.1f} Mbps'}")
        for w in self.ip_list_inner.winfo_children(): w.destroy()
        for ip in ips[:8]:
            item = tk.Frame(self.ip_list_inner, bg=PANEL_2, highlightthickness=1, highlightbackground=BORDER); item.pack(side="left", padx=4, pady=4)
            tk.Label(item, text=ip, bg=PANEL_2, fg=TEXT, font=(FONT, 8, "bold"), padx=10, pady=6).pack(side="left")
            self._button(item, "CONNECT", lambda s=server: self._connect([s]), "primary", True).pack(side="left", padx=(0, 4), pady=3)
        self.ip_list_inner.update_idletasks(); self.ip_list_canvas.configure(scrollregion=self.ip_list_canvas.bbox("all"))

    def _eligible(self):
        search = self.search_var.get().strip().lower() if hasattr(self, "search_var") else ""
        if search == "search country, city or endpoint": search = ""
        result = []
        for s in getattr(self, "servers", []) or []:
            ping = float(s.get("live_ping", 9999) or 9999)
            if self.available_only.get() and not s.get("available"): continue
            if self.fast_only.get() and ping > int(self.max_ping.get()): continue
            if self.country.get() != "All" and s.get("country") != self.country.get(): continue
            if self.city.get() != "All" and s.get("city") != self.city.get(): continue
            if self.source.get() != "All" and s.get("source") != self.source.get(): continue
            if search and search not in " ".join(str(s.get(k, "")) for k in ("country", "city", "host", "ip")).lower(): continue
            result.append(s)
        return result

    def _render_quick(self, items):
        for w in self.quick_frame.winfo_children(): w.destroy()
        for s in items[:5]:
            ping = float(s.get("live_ping", 9999) or 9999); country = s.get("country") or "Global"; city = s.get("city") or "Any city"
            card = tk.Frame(self.quick_frame, bg=PANEL_2, highlightthickness=1, highlightbackground=BORDER); card.pack(fill="x", pady=4)
            row = tk.Frame(card, bg=PANEL_2); row.pack(fill="x", padx=10, pady=(9, 2))
            tk.Label(row, text=FLAGS.get(country, "--"), bg=PANEL_2, fg=ACCENT_2, font=(FONT, 8, "bold")).pack(side="left")
            tk.Label(row, text=city, bg=PANEL_2, fg=TEXT, font=(FONT, 9, "bold")).pack(side="left", padx=7)
            tk.Label(row, text=f"{ping:.0f} ms", bg=PANEL_2, fg=SUCCESS if ping < 120 else WARNING, font=(FONT, 8, "bold")).pack(side="right")
            tk.Label(card, text=country, bg=PANEL_2, fg=MUTED, font=(FONT, 7)).pack(anchor="w", padx=10)
            self._button(card, "CONNECT", lambda x=s: self._connect([x]), "primary", True).pack(fill="x", padx=8, pady=8)
        if not items: tk.Label(self.quick_frame, text="No verified routes", bg=PANEL, fg=MUTED, font=(FONT, 9)).pack(pady=20)

    def _render(self):
        visible = self._eligible(); self.tree.delete(*self.tree.get_children())
        index = {id(s): i for i, s in enumerate(self.servers)}
        for s in visible:
            ping = float(s.get("live_ping", 9999) or 9999); ips = s.get("ips") or [s.get("ip") or s.get("host", "")]
            fast = bool(s.get("available")) and ping <= int(self.max_ping.get())
            self.tree.insert("", "end", iid=str(index[id(s)]), values=("● FAST" if fast else "● ONLINE", s.get("country", ""), s.get("city", ""), s.get("host", "") or s.get("ip", ""), "—" if ping >= 9999 else f"{ping:.0f} ms", f"{float(s.get('speed', 0) or 0):.1f} Mbps" if s.get("speed") else "—", len(ips)), tags=("fast" if fast else "online",))
        self.table_hint.configure(text=f"{len(visible)} verified locations")
        self._render_quick(visible); self._update_combos()
        if visible and not self._selected_server:
            self.tree.selection_set(str(index[id(visible[0])]))

    def _update_combos(self):
        servers = getattr(self, "servers", []) or []
        countries = ["All"] + sorted({str(s.get("country")) for s in servers if s.get("country")})
        cities = ["All"] + sorted({str(s.get("city")) for s in servers if s.get("city")})
        sources = ["All"] + sorted({str(s.get("source")) for s in servers if s.get("source")})
        for cb, values, var in ((self.country_combo, countries, self.country), (self.city_combo, cities, self.city), (self.source_combo, sources, self.source)):
            cb["values"] = values
            if var.get() not in values: var.set("All")

    def _set_busy(self, value):
        self.busy = value; state = "disabled" if value else "normal"
        for b in (self.refresh_btn, self.best_btn, self.sel_btn): b.configure(state=state)
        self.status_pill.configure(text="●  SCANNING" if value else "●  READY", fg=WARNING if value else MUTED)

    def _focus_dashboard(self): self.header.focus_set()
    def _focus_servers(self): self.server_card.focus_set()
    def _focus_quick(self): self.quick.focus_set()

    def _apply_responsive_layout(self, width):
        narrow = width < 900
        if narrow:
            if self.sidebar.winfo_ismapped(): self.sidebar.pack_forget()
            pad = 14
        else:
            if not self.sidebar.winfo_ismapped(): self.sidebar.pack(side="left", fill="y", before=self.content)
            pad = 20 if width < 1150 else 26
        for w in (self.header, self.hero, self.filters, self.ip_panel, self.action_bar):
            w.pack_configure(padx=pad)
        try: self.status_pill.pack(side="right", pady=(3, 0))
        except tk.TclError: pass
        if width < 1050:
            self.quick.configure(width=240)
        else:
            self.quick.configure(width=285)

    def _on_resize(self, event):
        if event.widget is self:
            if getattr(self, "_resize_job", None): self.after_cancel(self._resize_job)
            self._resize_job = self.after(80, lambda: self._apply_responsive_layout(event.width))

    def _connect(self, candidates):
        super()._connect(candidates)
        if candidates:
            target = candidates[0]; self.spinner_current = target.get("country") or target.get("city") or target.get("host")
            self._update_connection_view(target)
            if self.spinner_enabled: self._spinner_show_selected(target)

    def _update_connection_view(self, server=None, ip=None):
        if server:
            country = server.get("country") or "Global"; city = server.get("city") or ""
            self.connection_title.configure(text=f"{country}  ·  {city}" if city else country)
            self.connection_detail.configure(text=f"{server.get('host') or server.get('ip') or 'Verified endpoint'}")
            if ip: self.ip_value.set(str(ip))
            self.side_status.set("Connected" if ip else "Connecting")

    def disconnect(self):
        if self._spinner_rotating:
            EliteApp.disconnect(self); return
        self.country_spinner.disable(); self.spinner_enabled = False
        super().disconnect()
        self.ip_value.set("—"); self.connection_title.configure(text="Not connected"); self.connection_detail.configure(text="Choose a location to secure your connection.")
        self.side_status.set("Ready"); self.status_pill.configure(text="●  READY", fg=MUTED)

    # Country Spinner remains available as an advanced feature, but no longer
    # dominates the primary connection workflow.
    def _spinner_interval_changed(self, _event=None):
        value = int(self.spinner_interval_var.get().split()[0]); self.spinner_interval = value; self.spinner_countdown = value
        if self.spinner_enabled:
            self.country_spinner.disable(); self.country_spinner.enable(self._spinner_servers, interval=value); self._spinner_started = time.monotonic()

    def _spinner_servers(self): return list(getattr(self, "servers", []) or [])

    def toggle_spinner(self):
        if self.spinner_enabled:
            self.country_spinner.disable(); self.spinner_enabled = False; self._spinner_rotating = False
            self.side_status.set("Automatic rotation paused"); return
        available = [s for s in self._spinner_servers() if s.get("available")]
        if not available:
            self.side_status.set("Scan the network first"); return
        self.spinner_enabled = True; self.spinner_countdown = self.spinner_interval; self._spinner_started = time.monotonic()
        self.country_spinner.current_country = self.spinner_current; self.country_spinner.enable(self._spinner_servers, interval=self.spinner_interval)
        self.side_status.set("Automatic rotation active")

    def _spinner_disconnect(self): self._spinner_rotating = True; self.after(0, self._spinner_disconnect_ui)
    def _spinner_disconnect_ui(self):
        if self._spinner_rotating: EliteApp.disconnect(self)
    def _spinner_connect(self, candidates): self.after(0, lambda: self._spinner_connect_ui(candidates))
    def _spinner_connect_ui(self, candidates):
        if not candidates or not self.spinner_enabled: self._spinner_rotating = False; return
        target = candidates[0]; self.spinner_next = target; self._connect([target]); self._spinner_rotating = False
        self.spinner_current = target.get("country") or target.get("city") or target.get("host")
        self.spinner_history.append({"country": target.get("country"), "city": target.get("city"), "ip": (target.get("ips") or [target.get("ip") or target.get("host", "")])[0]}); self.spinner_history = self.spinner_history[-12:]
        self._update_connection_view(target); self._spinner_show_selected(target); self.spinner_countdown = self.spinner_interval; self._spinner_started = time.monotonic()

    def _spinner_show_selected(self, target): self._selected_server = target; self._render_ip_inspector(target)

    def _spinner_tick(self):
        try:
            if self.spinner_enabled and self._spinner_started:
                remaining = max(0, self.spinner_interval - int(time.monotonic() - self._spinner_started)); self.status.set(f"Automatic rotation  ·  next switch in {remaining:02d}s")
            self.after(250, self._spinner_tick)
        except tk.TclError: pass


install_connection_progress(App)

if __name__ == "__main__":
    App().mainloop()
