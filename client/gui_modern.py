from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from gui import App as LegacyApp
from gui_elite import App as EliteApp, BG, SURFACE, PANEL, PANEL_2, PANEL_3, BORDER, BORDER_HI, TEXT, MUTED, ACCENT, ACCENT_2, SUCCESS, WARNING, DANGER, CYAN, FONT


class App(EliteApp):
    """Modern Findupto VPN desktop dashboard."""

    def _start_connection(self, server):
        return LegacyApp._start_connection(self, server)

    def _change_ip(self):
        return LegacyApp._change_ip(self)

    def _open_browser(self):
        return LegacyApp._open_browser(self)

    def _build_premium_sidebar(self):
        self.sidebar.configure(width=224, bg=SURFACE)
        brand = tk.Frame(self.sidebar, bg=SURFACE)
        brand.pack(fill="x", padx=18, pady=(22, 24))
        mark = tk.Frame(brand, bg=ACCENT, width=44, height=44)
        mark.pack(side="left", padx=(0, 11)); mark.pack_propagate(False)
        tk.Label(mark, text="F", bg=ACCENT, fg="white", font=(FONT, 18, "bold")).pack(expand=True)
        name = tk.Frame(brand, bg=SURFACE); name.pack(side="left")
        tk.Label(name, text="FINDUPTO", bg=SURFACE, fg=TEXT, font=(FONT, 13, "bold")).pack(anchor="w")
        tk.Label(name, text="PRIVATE NETWORK", bg=SURFACE, fg=ACCENT_2, font=(FONT, 7, "bold")).pack(anchor="w")
        self.nav_items = []
        for icon, label, command in (("⌂", "Dashboard", self._focus_dashboard), ("◉", "Servers", self._focus_servers), ("⚡", "Fast routes", self._focus_quick), ("◌", "Diagnostics", self.open_log)):
            active = label == "Dashboard"
            b = tk.Button(self.sidebar, text=f"  {icon}   {label}", anchor="w", command=command,
                          bg=ACCENT if active else SURFACE, fg="white" if active else MUTED,
                          activebackground=PANEL_2, activeforeground=TEXT, relief="flat", bd=0,
                          cursor="hand2", font=(FONT, 10, "bold"), padx=16, pady=11)
            b.pack(fill="x", padx=10, pady=3); self.nav_items.append(b)
        tk.Frame(self.sidebar, bg=SURFACE).pack(fill="both", expand=True)
        status = self._card(self.sidebar, bg=PANEL, accent=True)
        status.pack(fill="x", padx=13, pady=13)
        tk.Label(status, text="CONNECTION", bg=PANEL, fg=MUTED, font=(FONT, 7, "bold")).pack(anchor="w", padx=13, pady=(11, 3))
        self.side_status = tk.StringVar(value="Ready to connect")
        tk.Label(status, textvariable=self.side_status, bg=PANEL, fg=TEXT, font=(FONT, 9, "bold"), wraplength=180, justify="left").pack(anchor="w", padx=13, pady=(0, 12))
        tk.Label(self.sidebar, text="Secure tunnel • verified routes", bg=SURFACE, fg=MUTED, font=(FONT, 7)).pack(anchor="w", padx=18, pady=(0, 18))

    def _build_premium_content(self):
        self.content.configure(bg=BG)
        self.header = tk.Frame(self.content, bg=BG); self.header.pack(fill="x", padx=30, pady=(22, 14))
        title = tk.Frame(self.header, bg=BG); title.pack(side="left", fill="x", expand=True)
        tk.Label(title, text="FINDUPTO VPN", bg=BG, fg=TEXT, font=(FONT, 25, "bold")).pack(anchor="w")
        tk.Label(title, text="Private connection control • verified exit IP • intelligent routing", bg=BG, fg=MUTED, font=(FONT, 9)).pack(anchor="w", pady=(3, 0))
        self.status_pill = tk.Label(self.header, text="●  READY", bg=PANEL_2, fg=MUTED, padx=13, pady=8, font=(FONT, 8, "bold"), highlightthickness=1, highlightbackground=BORDER_HI); self.status_pill.pack(side="right", pady=(4, 0))

        self.hero = self._card(self.content, bg=SURFACE, accent=True, glow=True); self.hero.pack(fill="x", padx=30, pady=(0, 12))
        top = tk.Frame(self.hero, bg=SURFACE); top.pack(fill="x", padx=22, pady=(18, 8))
        left = tk.Frame(top, bg=SURFACE); left.pack(side="left", fill="x", expand=True)
        tk.Label(left, text="SECURE CONNECTION", bg=SURFACE, fg=CYAN, font=(FONT, 8, "bold")).pack(anchor="w")
        self.connection_title = tk.Label(left, text="Not connected", bg=SURFACE, fg=TEXT, font=(FONT, 20, "bold")); self.connection_title.pack(anchor="w", pady=(3, 0))
        self.connection_detail = tk.Label(left, text="Choose a verified route to start a private tunnel.", bg=SURFACE, fg=MUTED, font=(FONT, 9)); self.connection_detail.pack(anchor="w", pady=(3, 0))
        ipbox = tk.Frame(top, bg=PANEL_2, highlightthickness=1, highlightbackground=BORDER_HI); ipbox.pack(side="right", padx=(14, 0))
        tk.Label(ipbox, text="CURRENT EXIT IP", bg=PANEL_2, fg=MUTED, font=(FONT, 7, "bold")).pack(anchor="w", padx=14, pady=(9, 0))
        self.current_ip = tk.StringVar(value="—")
        tk.Label(ipbox, textvariable=self.current_ip, bg=PANEL_2, fg=CYAN, font=(FONT, 14, "bold"), padx=14, pady=9).pack(anchor="w")
        controls = tk.Frame(self.hero, bg=SURFACE); controls.pack(fill="x", padx=22, pady=(8, 20))
        self.connect_btn = self._button(controls, "●  CONNECT FASTEST", self.best, "primary"); self.connect_btn.pack(side="left")
        self.change_ip_btn = self._button(controls, "↻  CHANGE IP", self._change_ip, "success"); self.change_ip_btn.pack(side="left", padx=8)
        self.disconnect_btn = self._button(controls, "■  DISCONNECT", self.disconnect, "danger"); self.disconnect_btn.pack(side="left")
        self.browser_btn = self._button(controls, "🌐  SECURE BROWSER", self._open_browser, "secondary"); self.browser_btn.pack(side="right")
        self.session_label = tk.Label(controls, text="SESSION  00:00:00", bg=PANEL_2, fg=CYAN, padx=12, pady=8, font=(FONT, 8, "bold"), highlightthickness=1, highlightbackground=BORDER_HI); self.session_label.pack(side="right", padx=8)

        self.metrics = tk.Frame(self.content, bg=BG); self.metrics.pack(fill="x", padx=30, pady=(0, 12)); self.metric_vars = {}
        for key, label, accent in (("visible", "ROUTES", CYAN), ("online", "ONLINE", SUCCESS), ("fast", "FAST", ACCENT_2), ("countries", "COUNTRIES", WARNING), ("tested", "TESTED", TEXT)):
            card = self._card(self.metrics, bg=PANEL); card.pack(side="left", fill="x", expand=True, padx=(0, 7))
            tk.Label(card, text=label, bg=PANEL, fg=MUTED, font=(FONT, 7, "bold")).pack(anchor="w", padx=14, pady=(9, 1))
            var = tk.StringVar(value="0"); self.metric_vars[key] = var
            tk.Label(card, textvariable=var, bg=PANEL, fg=accent, font=(FONT, 19, "bold")).pack(anchor="w", padx=14, pady=(0, 9))

        self.filters = self._card(self.content, bg=PANEL); self.filters.pack(fill="x", padx=30, pady=(0, 10)); self._build_filters_premium()
        self.quick = self._card(self.content, bg=PANEL, accent=True); self.quick.pack(fill="x", padx=30, pady=(0, 10))
        qhead = tk.Frame(self.quick, bg=PANEL); qhead.pack(fill="x", padx=15, pady=(10, 5))
        tk.Label(qhead, text="FASTEST VERIFIED ROUTES", bg=PANEL, fg=TEXT, font=(FONT, 11, "bold")).pack(side="left")
        self.speed_status = tk.StringVar(value="Waiting for scan"); tk.Label(qhead, textvariable=self.speed_status, bg=PANEL, fg=SUCCESS, font=(FONT, 8, "bold")).pack(side="right")
        self.quick_frame = tk.Frame(self.quick, bg=PANEL); self.quick_frame.pack(fill="x", padx=10, pady=(0, 11))

        self.server_card = self._card(self.content, bg=PANEL); self.server_card.pack(fill="both", expand=True, padx=30, pady=(0, 10))
        top = tk.Frame(self.server_card, bg=PANEL); top.pack(fill="x", padx=15, pady=(11, 7))
        tk.Label(top, text="SERVER NETWORK", bg=PANEL, fg=TEXT, font=(FONT, 12, "bold")).pack(side="left")
        self.table_hint = tk.Label(top, text="Select a verified route", bg=PANEL, fg=MUTED, font=(FONT, 8)); self.table_hint.pack(side="right")
        frame = tk.Frame(self.server_card, bg=PANEL); frame.pack(fill="both", expand=True, padx=9, pady=(0, 9))
        cols = ("status", "country", "city", "host", "ips", "ping", "speed", "source"); self._table_columns = cols
        self.tree = ttk.Treeview(frame, columns=cols, show="headings", selectmode="browse")
        for col, heading in zip(cols, ("STATUS", "COUNTRY", "CITY", "ENDPOINT", "IP ROUTES", "LATENCY", "SPEED", "SOURCE")):
            self.tree.heading(col, text=heading); self.tree.column(col, width=105, minwidth=55, stretch=True)
        self.tree.tag_configure("fast", foreground=SUCCESS); self.tree.tag_configure("online", foreground=TEXT)
        y = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview); x = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=y.set, xscrollcommand=x.set); self.tree.grid(row=0, column=0, sticky="nsew"); y.grid(row=0, column=1, sticky="ns"); x.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1); frame.columnconfigure(0, weight=1); self.tree.bind("<Double-1>", lambda _e: self.selected())

        self.action_bar = tk.Frame(self.content, bg=BG); self.action_bar.pack(fill="x", padx=30, pady=(0, 16))
        self.refresh_btn = self._button(self.action_bar, "↻  SCAN", self.refresh, "secondary"); self.refresh_btn.pack(side="left")
        self.sel_btn = self._button(self.action_bar, "CONNECT SELECTED", self.selected, "primary"); self.sel_btn.pack(side="left", padx=7)
        self.diag_btn = self._button(self.action_bar, "DIAGNOSTICS", self.open_log, "ghost"); self.diag_btn.pack(side="left")

        # Compatibility aliases: inherited lifecycle code from gui_elite/gui_pro
        # expects the old primary-button attribute names.
        self.best_btn = self.connect_btn
        self.bst_btn = self.connect_btn

    def _set_connection_view(self, connected=False, server=None, ip=None):
        try:
            if connected and server:
                country = server.get("country") or "Global"; city = server.get("city") or ""
                self.connection_title.configure(text=f"Connected • {country}")
                self.connection_detail.configure(text=f"{city}  •  {server.get('host') or server.get('ip') or 'verified endpoint'}")
                self.current_ip.set(str(ip or "—")); self.side_status.set(f"Connected via {country} • exit IP {ip or '—'}")
            else:
                self.connection_title.configure(text="Not connected")
                self.connection_detail.configure(text="Choose a verified route to start a private tunnel.")
                self.current_ip.set("—"); self.side_status.set("Ready to connect")
        except tk.TclError:
            pass

    def _connect(self, candidates):
        super()._connect(candidates)
        if candidates:
            self._set_connection_view(False, candidates[0])

    def _render(self):
        super()._render()
        try:
            if getattr(self, "servers", None): self.speed_status.set("Live verified pool")
        except tk.TclError:
            pass

    def disconnect(self):
        super().disconnect(); self._set_connection_view(False)

    def _apply_responsive_layout(self, width):
        compact = width < 1050; narrow = width < 820
        if getattr(self, "compact", False) != compact:
            self.compact = compact
            if compact: self.sidebar.pack_forget()
            else: self.sidebar.pack(side="left", fill="y", before=self.content)
        pad = 12 if narrow else 18 if compact else 30
        for widget in (self.header, self.hero, self.metrics, self.filters, self.quick, self.server_card, self.action_bar): widget.pack_configure(padx=pad)
        if narrow:
            self.status_pill.pack_forget(); self._set_table_mode("narrow")
        elif compact:
            self.status_pill.pack(side="right", pady=(4, 0)); self._set_table_mode("compact")
        else:
            self.status_pill.pack(side="right", pady=(4, 0)); self._set_table_mode("wide")

    def _set_busy(self, value):
        # The modern UI owns these controls, so don't call the legacy method
        # that assumes the removed button hierarchy.
        self.busy = value
        state = "disabled" if value else "normal"
        seen = set()
        for widget in (self.connect_btn, self.best_btn, self.bst_btn, self.change_ip_btn, self.refresh_btn, self.sel_btn, self.disconnect_btn):
            if widget is None or id(widget) in seen:
                continue
            seen.add(id(widget))
            try:
                widget.configure(state=state)
            except tk.TclError:
                pass
        try:
            self.status_pill.configure(text="●  SCANNING" if value else "●  READY", fg=WARNING if value else MUTED)
        except tk.TclError:
            pass
