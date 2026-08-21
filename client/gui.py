from __future__ import annotations

import os
import queue
import shutil
import socket
import subprocess
import sys
import threading
import time
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor, as_completed
from tkinter import messagebox, ttk

import standalone_engine as engine
import runtime_bootstrap
from fast_server_pool import endpoints, rank

APP = "Findupto VPN"
VERSION = engine.APP_VERSION
FAST_LIMIT_MS = 250
PROBE_TIMEOUT = 1.2

BG = "#060811"
SURFACE = "#0b101a"
PANEL = "#101722"
PANEL_2 = "#151d2b"
PANEL_3 = "#1a2434"
BORDER = "#202b3d"
BORDER_HI = "#34435c"
TEXT = "#f8faff"
MUTED = "#8c99ad"
ACCENT = "#765cff"
ACCENT_2 = "#9a87ff"
SUCCESS = "#31d9a5"
WARNING = "#ffc46b"
DANGER = "#ff647d"
CYAN = "#61dcff"
FONT = "Segoe UI"


class App(tk.Tk):
    """Responsive VPN dashboard with a polished premium desktop UI."""

    def __init__(self):
        super().__init__()
        self.title(f"{APP} {VERSION}")
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{min(1480, max(820, sw - 70))}x{min(920, max(620, sh - 90))}")
        self.minsize(760, 560)
        self.configure(bg=BG)
        self.events = queue.Queue()
        self.servers = []
        self.process = self.tmp = self.current_log = None
        self.busy = False
        self.cancel_event = threading.Event()
        self.compact = False
        self._resize_job = None
        self._configure_styles()
        self._build()
        self.bind("<Configure>", self._on_resize)
        self.after(100, self._pump)
        self.refresh()

    def _configure_styles(self):
        s = ttk.Style(self)
        try:
            s.theme_use("clam")
        except tk.TclError:
            pass
        s.configure("TFrame", background=BG)
        s.configure("TLabel", background=BG, foreground=TEXT, font=(FONT, 10))
        s.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=TEXT,
                    rowheight=44, borderwidth=0, relief="flat", font=(FONT, 9))
        s.configure("Treeview.Heading", background=PANEL_2, foreground=MUTED,
                    relief="flat", font=(FONT, 8, "bold"), padding=(9, 10))
        s.map("Treeview", background=[("selected", "#2a3650")], foreground=[("selected", TEXT)])
        s.configure("TCheckbutton", background=PANEL, foreground=TEXT, font=(FONT, 9))
        s.map("TCheckbutton", background=[("active", PANEL)])
        s.configure("TCombobox", fieldbackground=PANEL_2, background=PANEL_2,
                    foreground=TEXT, arrowcolor=MUTED, bordercolor=BORDER,
                    lightcolor=BORDER, darkcolor=BORDER)
        s.map("TCombobox", fieldbackground=[("readonly", PANEL_2)],
              foreground=[("readonly", TEXT)])
        s.configure("TSpinbox", fieldbackground=PANEL_2, background=PANEL_2,
                    foreground=TEXT, arrowcolor=MUTED, bordercolor=BORDER)

    def _button(self, parent, text, command, kind="secondary", compact=False):
        palette = {
            "primary": (ACCENT, "white", ACCENT_2),
            "success": (SUCCESS, BG, "#58e8bb"),
            "danger": (DANGER, BG, "#ff8ba0"),
            "secondary": (PANEL_2, TEXT, PANEL_3),
            "ghost": (BG, MUTED, PANEL_2),
        }
        bg, fg, active = palette[kind]
        b = tk.Button(parent, text=text, command=command, bg=bg, fg=fg,
                      activebackground=active, activeforeground=fg, relief="flat", bd=0,
                      highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT,
                      cursor="hand2", font=(FONT, 9 if compact else 10, "bold"),
                      padx=11 if compact else 15, pady=7 if compact else 10)
        b.bind("<Enter>", lambda _e: b.configure(bg=active if b["state"] != "disabled" else bg))
        b.bind("<Leave>", lambda _e: b.configure(bg=bg))
        b.bind("<FocusIn>", lambda _e: b.configure(highlightbackground=ACCENT))
        b.bind("<FocusOut>", lambda _e: b.configure(highlightbackground=BORDER))
        return b

    def _card(self, parent, accent=False):
        outer = tk.Frame(parent, bg=BORDER_HI if accent else BORDER, padx=1, pady=1)
        inner = tk.Frame(outer, bg=PANEL)
        inner.pack(fill="both", expand=True)
        return outer

    @staticmethod
    def _label(parent, text, fg=TEXT, size=10, weight="normal", bg=PANEL, **kwargs):
        return tk.Label(parent, text=text, bg=bg, fg=fg, font=(FONT, size, weight), **kwargs)

    def _build(self):
        self.root = tk.Frame(self, bg=BG)
        self.root.pack(fill="both", expand=True)
        self.sidebar = tk.Frame(self.root, bg=SURFACE, width=232,
                                highlightthickness=1, highlightbackground=BORDER)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        self._build_sidebar()
        self.content = tk.Frame(self.root, bg=BG)
        self.content.pack(side="left", fill="both", expand=True)
        self._build_content()
        self._apply_responsive_layout(self.winfo_width() or 1200)

    def _build_sidebar(self):
        brand = tk.Frame(self.sidebar, bg=SURFACE)
        brand.pack(fill="x", padx=18, pady=(20, 24))
        mark = tk.Frame(brand, bg=ACCENT, width=42, height=42)
        mark.pack(side="left", padx=(0, 11))
        mark.pack_propagate(False)
        self._label(mark, "F", fg="white", size=17, weight="bold", bg=ACCENT).pack(expand=True)
        text = tk.Frame(brand, bg=SURFACE)
        text.pack(side="left")
        self._label(text, "FINDUPTO", size=13, weight="bold", bg=SURFACE).pack(anchor="w")
        self._label(text, "SECURE VPN CONTROL", fg=MUTED, size=7, weight="bold", bg=SURFACE).pack(anchor="w")

        self.nav_items = []
        for icon, label in (("⌂", "Dashboard"), ("◉", "Servers"),
                            ("⚡", "Fast Pool"), ("◌", "Diagnostics")):
            active = label == "Dashboard"
            b = tk.Button(self.sidebar, text=f"  {icon}   {label}", anchor="w",
                          command=self.open_log if label == "Diagnostics" else self._focus_dashboard,
                          bg=ACCENT if active else SURFACE,
                          fg="white" if active else MUTED,
                          activebackground=PANEL_2, activeforeground=TEXT,
                          relief="flat", bd=0, cursor="hand2", font=(FONT, 10, "bold"),
                          padx=16, pady=11, highlightthickness=0)
            b.pack(fill="x", padx=10, pady=3)
            b.bind("<Enter>", lambda e, w=b, a=active: w.configure(bg=ACCENT_2 if a else PANEL_2, fg="white"))
            b.bind("<Leave>", lambda e, w=b, a=active: w.configure(bg=ACCENT if a else SURFACE, fg="white" if a else MUTED))
            self.nav_items.append(b)

        tk.Frame(self.sidebar, bg=SURFACE).pack(fill="both", expand=True)
        status_outer = self._card(self.sidebar, accent=True)
        status_outer.pack(fill="x", padx=14, pady=14)
        info = status_outer.winfo_children()[0]
        self._label(info, "CONNECTION STATUS", fg=MUTED, size=7, weight="bold").pack(anchor="w", padx=13, pady=(11, 3))
        self.side_status = tk.StringVar(value="Ready to connect")
        tk.Label(info, textvariable=self.side_status, bg=PANEL, fg=SUCCESS,
                 font=(FONT, 9, "bold"), wraplength=178, justify="left").pack(anchor="w", padx=13, pady=(0, 12))
        self._label(self.sidebar, f"v{VERSION}  •  Secure tunnel", fg=MUTED, size=7, bg=SURFACE).pack(anchor="w", padx=18, pady=(0, 18))

    def _build_content(self):
        self.header = tk.Frame(self.content, bg=BG)
        self.header.pack(fill="x", padx=26, pady=(20, 14))
        left = tk.Frame(self.header, bg=BG)
        left.pack(side="left", fill="x", expand=True)
        self._label(left, "VPN Control Center", size=24, weight="bold", bg=BG).pack(anchor="w")
        self._label(left, "Verified endpoints, intelligent routing, one-click secure connection.", fg=MUTED, size=9, bg=BG).pack(anchor="w", pady=(3, 0))
        self.status = tk.StringVar(value="Preparing instant-connect pool…")
        self.status_pill = tk.Label(self.header, textvariable=self.status, bg=PANEL_2,
                                    fg=MUTED, padx=14, pady=8, font=(FONT, 8, "bold"),
                                    highlightthickness=1, highlightbackground=BORDER)
        self.status_pill.pack(side="right", padx=(12, 0))

        self.filters = self._card(self.content)
        self.filters.pack(fill="x", padx=26, pady=(0, 11))
        self._build_filters()

        self.stats = tk.Frame(self.content, bg=BG)
        self.stats.pack(fill="x", padx=26, pady=(0, 11))
        self.stat_cards = {}
        for key, label, accent in (("shown", "SHOWN", CYAN), ("available", "AVAILABLE", SUCCESS),
                                   ("fast", "FAST", ACCENT_2), ("pool", "QUICK POOL", WARNING), ("tested", "TESTED", MUTED)):
            c = self._card(self.stats, accent=key == "fast")
            c.pack(side="left", fill="x", expand=True, padx=(0, 8))
            inner = c.winfo_children()[0]
            value = tk.StringVar(value="0")
            tk.Label(inner, textvariable=value, bg=PANEL, fg=TEXT, font=(FONT, 19, "bold")).pack(anchor="w", padx=13, pady=(9, 0))
            tk.Label(inner, text=label, bg=PANEL, fg=accent, font=(FONT, 7, "bold")).pack(anchor="w", padx=13, pady=(0, 9))
            self.stat_cards[key] = value

        self.quick = self._card(self.content, accent=True)
        self.quick.pack(fill="x", padx=26, pady=(0, 11))
        quick_inner = self.quick.winfo_children()[0]
        qhead = tk.Frame(quick_inner, bg=PANEL)
        qhead.pack(fill="x", padx=14, pady=(10, 6))
        self._label(qhead, "⚡  FASTEST VERIFIED", size=11, weight="bold").pack(side="left")
        self.speed_status = tk.StringVar(value="Live probing…")
        tk.Label(qhead, textvariable=self.speed_status, bg=PANEL, fg=SUCCESS, font=(FONT, 8, "bold")).pack(side="right")
        self.quick_frame = tk.Frame(quick_inner, bg=PANEL)
        self.quick_frame.pack(fill="x", padx=10, pady=(0, 11))

        self.server_card = self._card(self.content)
        self.server_card.pack(fill="both", expand=True, padx=26, pady=(0, 11))
        server_inner = self.server_card.winfo_children()[0]
        top = tk.Frame(server_inner, bg=PANEL)
        top.pack(fill="x", padx=14, pady=(10, 7))
        title_wrap = tk.Frame(top, bg=PANEL)
        title_wrap.pack(side="left")
        self._label(title_wrap, "Server Lounge", size=12, weight="bold").pack(anchor="w")
        self._label(title_wrap, "Live verified endpoint pool", fg=MUTED, size=7).pack(anchor="w", pady=(1, 0))
        self.table_hint = tk.Label(top, text="Select a verified server to connect", bg=PANEL, fg=MUTED, font=(FONT, 8))
        self.table_hint.pack(side="right")

        frame = tk.Frame(server_inner, bg=PANEL)
        frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        cols = ("status", "country", "city", "host", "ips", "ping", "speed", "source")
        self.tree = ttk.Treeview(frame, columns=cols, show="headings", selectmode="browse")
        self._table_columns = cols
        for col in cols:
            self.tree.heading(col, text=col.upper())
            self.tree.column(col, width=100, minwidth=50, anchor="w", stretch=True)
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

        self.action_bar = tk.Frame(self.content, bg=BG)
        self.action_bar.pack(fill="x", padx=26, pady=(0, 16))
        self.refresh_btn = self._button(self.action_bar, "↻  Refresh", self.refresh)
        self.refresh_btn.pack(side="left")
        self.best_btn = self._button(self.action_bar, "✦  Connect Fastest", self.best, "primary")
        self.best_btn.pack(side="left", padx=7)
        self.sel_btn = self._button(self.action_bar, "➜  Selected", self.selected)
        self.sel_btn.pack(side="left")
        self.diag_btn = self._button(self.action_bar, "◉  Diagnostics", self.open_log, "ghost")
        self.diag_btn.pack(side="left", padx=7)
        self.disconnect_btn = self._button(self.action_bar, "■  Disconnect", self.disconnect, "danger")
        self.disconnect_btn.pack(side="right")

    def _build_filters(self):
        inner = self.filters.winfo_children()[0]
        self._label(inner, "FILTERS", fg=MUTED, size=7, weight="bold").pack(side="left", padx=(14, 7), pady=11)
        self.fast_only = tk.BooleanVar(value=True)
        self.available_only = tk.BooleanVar(value=True)
        self.auto_connect = tk.BooleanVar(value=False)
        ttk.Checkbutton(inner, text="Fast", variable=self.fast_only, command=self._render).pack(side="left", padx=4)
        ttk.Checkbutton(inner, text="Available", variable=self.available_only, command=self._render).pack(side="left", padx=4)
        self.country = tk.StringVar(value="All")
        self.city = tk.StringVar(value="All")
        self.source = tk.StringVar(value="All")
        for label, var in (("COUNTRY", self.country), ("CITY", self.city), ("SOURCE", self.source)):
            self._label(inner, label, fg=MUTED, size=7, weight="bold").pack(side="left", padx=(10, 4))
            cb = ttk.Combobox(inner, textvariable=var, state="readonly", width=12)
            cb.pack(side="left", padx=(0, 4))
            cb.bind("<<ComboboxSelected>>", lambda _e: self._render())
            setattr(self, label.lower() + "_combo", cb)
        self._label(inner, "MAX PING", fg=MUTED, size=7, weight="bold").pack(side="left", padx=(10, 4))
        self.max_ping = tk.IntVar(value=250)
        self.ping_spin = ttk.Spinbox(inner, from_=50, to=2000, increment=25, width=6, textvariable=self.max_ping, command=self._render)
        self.ping_spin.pack(side="left")
        self._label(inner, "ms", fg=MUTED, size=8).pack(side="left", padx=(3, 8))
        ttk.Checkbutton(inner, text="Auto Connect", variable=self.auto_connect, command=self._auto_connect_changed).pack(side="left", padx=4)

    def _focus_dashboard(self):
        self.server_card.focus_set()

    def _on_resize(self, event):
        if event.widget is not self:
            return
        if self._resize_job:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(80, lambda: self._apply_responsive_layout(event.width))

    def _apply_responsive_layout(self, width):
        compact = width < 1040
        narrow = width < 860
        if compact != self.compact:
            self.compact = compact
            if compact:
                self.sidebar.pack_forget()
            else:
                self.sidebar.pack(side="left", fill="y", before=self.content)
        if narrow:
            for widget in (self.header, self.filters, self.stats, self.quick, self.server_card, self.action_bar):
                widget.pack_configure(padx=14)
            self.header.pack_configure(pady=(14, 8))
            self.status_pill.pack_forget()
            self.table_hint.configure(text="Scroll horizontally for more columns")
            self._set_table_mode("narrow")
        elif compact:
            for widget in (self.header, self.filters, self.stats, self.quick, self.server_card, self.action_bar):
                widget.pack_configure(padx=18)
            self.status_pill.pack(side="right", padx=(10, 0))
            self.table_hint.configure(text="Verified endpoints")
            self._set_table_mode("compact")
        else:
            self.header.pack_configure(padx=26, pady=(20, 14))
            for widget in (self.filters, self.stats, self.quick, self.server_card, self.action_bar):
                widget.pack_configure(padx=26)
            self.status_pill.pack(side="right", padx=(12, 0))
            self.table_hint.configure(text="Select a verified server to connect")
            self._set_table_mode("wide")

    def _set_table_mode(self, mode):
        widths = {"wide": (92, 100, 105, 180, 210, 72, 90, 95), "compact": (80, 90, 90, 145, 170, 68, 82, 85), "narrow": (72, 82, 82, 135, 150, 65, 78, 80)}[mode]
        for col, width in zip(self._table_columns, widths):
            self.tree.column(col, width=width, minwidth=48, stretch=True)

    def _set_busy(self, value):
        self.busy = value
        state = "disabled" if value else "normal"
        for b in (self.refresh_btn, self.best_btn, self.sel_btn):
            b.configure(state=state)

    def _auto_connect_changed(self):
        if self.auto_connect.get() and not self.busy:
            self.best()

    @staticmethod
    def _probe(server):
        eps = endpoints(server)
        best = None
        best_host = None
        for ep in eps[:8]:
            ports = [ep.port] if ep.port else ([443, 80, 53] if server.get("kind") == "gate" else [443, 80])
            for port in ports:
                started = time.monotonic()
                try:
                    with socket.create_connection((ep.host, port), timeout=PROBE_TIMEOUT):
                        latency = (time.monotonic() - started) * 1000
                        if best is None or latency < best:
                            best, best_host = latency, ep.host
                except OSError:
                    continue
        if best is None:
            return dict(server, available=False, live_ping=9999, ips=[e.host for e in eps])
        return dict(server, available=True, live_ping=best, ping=best, ip=best_host, host=server.get("host") or best_host, ips=[e.host for e in eps], rank=float(server.get("rank", 0)) + max(0, 500 - best))

    def refresh(self):
        if self.busy:
            return
        self.cancel_event.clear()
        self._set_busy(True)
        self.status.set("Scanning endpoints for the fastest verified pool…")
        self.side_status.set("Scanning endpoints…")
        threading.Thread(target=self._discover_worker, daemon=True).start()

    def _discover_worker(self):
        try:
            data = engine.discover(10)
            tested = []
            with ThreadPoolExecutor(max_workers=32, thread_name_prefix="vpn-probe") as pool:
                futures = [pool.submit(self._probe, s) for s in data[:150]]
                for f in as_completed(futures):
                    if self.cancel_event.is_set():
                        break
                    tested.append(f.result())
            tested.sort(key=lambda s: (not s.get("available"), s.get("live_ping", 9999), -float(s.get("speed", 0) or 0), -float(s.get("rank", 0) or 0)))
            self.events.put(("servers", tested, f"Fast pool ready • {len(tested)} endpoints tested"))
        except Exception as exc:
            self.events.put(("error", None, f"Server discovery failed: {exc}"))

    def _eligible(self):
        try:
            limit = max(50, int(self.max_ping.get()))
        except Exception:
            limit = FAST_LIMIT_MS
        items = [s for s in self.servers if (not self.available_only.get() or s.get("available")) and (not self.fast_only.get() or float(s.get("live_ping", 9999)) <= limit)]
        for key, var in (("country", self.country), ("city", self.city), ("source", self.source)):
            if var.get() != "All":
                items = [s for s in items if str(s.get(key, "")) == var.get()]
        return rank(items, limit, False, False)

    def _update_combos(self):
        for key, combo in (("country", self.country_combo), ("city", self.city_combo), ("source", self.source_combo)):
            vals = sorted({str(s.get(key, "")) for s in self.servers if s.get(key)})
            combo["values"] = ["All"] + vals
            if combo.get() not in combo["values"]:
                combo.set("All")

    def _render_quick(self, items):
        for w in self.quick_frame.winfo_children():
            w.destroy()
        if not items:
            self._label(self.quick_frame, "No servers match the current filters.", fg=MUTED, size=9).pack(anchor="w", padx=8, pady=12)
            return
        count = 4 if self.compact else 6
        for s in items[:count]:
            ips = s.get("ips") or [s.get("ip") or s.get("host", "")]
            name = s.get("city") or s.get("country") or s.get("host", "Server")
            ping = float(s.get("live_ping", 9999))
            card = tk.Frame(self.quick_frame, bg=PANEL_2, highlightthickness=1, highlightbackground=BORDER_HI)
            card.pack(side="left", fill="x", expand=True, padx=3)
            self._label(card, f"●  {name}", fg=SUCCESS, size=8, weight="bold", bg=PANEL_2).pack(anchor="w", padx=9, pady=(7, 0))
            self._label(card, f"{ping:.0f} ms  •  {len(ips)} IPs", size=9, bg=PANEL_2).pack(anchor="w", padx=9)
            if not self.compact:
                self._label(card, "  ".join(str(x) for x in ips[:2]), fg=MUTED, size=7, bg=PANEL_2).pack(anchor="w", padx=9, pady=(0, 4))
            b = self._button(card, "CONNECT", lambda x=s: self._connect([x]), "primary", compact=True)
            b.pack(anchor="e", padx=8, pady=(0, 7))

    def _render(self):
        visible = self._eligible()
        self.tree.delete(*self.tree.get_children())
        index = {id(s): i for i, s in enumerate(self.servers)}
        for s in visible:
            ping = float(s.get("live_ping", 9999))
            ips = s.get("ips") or [s.get("ip") or s.get("host", "")]
            fast = bool(s.get("available")) and ping <= FAST_LIMIT_MS
            self.tree.insert("", "end", iid=str(index[id(s)]), tags=("fast" if fast else "online",), values=("● FAST" if fast else "● ONLINE", s.get("country", ""), s.get("city", ""), s.get("host", "") or s.get("ip", ""), ", ".join(str(x) for x in ips[:4]), "—" if ping >= 9999 else f"{ping:.0f} ms", f"{float(s.get('speed', 0) or 0):.1f} Mbps" if s.get("speed") else "—", s.get("source", "")))
        available = sum(bool(s.get("available")) for s in self.servers)
        fast = sum(bool(s.get("available")) and float(s.get("live_ping", 9999)) <= FAST_LIMIT_MS for s in self.servers)
        self.stat_cards["shown"].set(str(len(visible)))
        self.stat_cards["available"].set(str(available))
        self.stat_cards["fast"].set(str(fast))
        self.stat_cards["pool"].set(str(len(self._eligible()[:8])))
        self.stat_cards["tested"].set(str(len(self.servers)))
        self._render_quick(visible)
        self._update_combos()

    def best(self):
        candidates = self._eligible()
        if not candidates:
            messagebox.showwarning(APP, "No fast available server matches the filters. Refresh or widen MAX PING.")
            return
        self._connect(candidates[:24])

    def selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning(APP, "Select a server first.")
            return
        try:
            server = self.servers[int(sel[0])]
        except (ValueError, IndexError):
            messagebox.showwarning(APP, "Server is no longer in the live pool.")
            return
        if self.available_only.get() and not server.get("available"):
            messagebox.showwarning(APP, "This server is not available.")
            return
        self._connect([server])

    def _connect(self, candidates):
        if self.busy or not candidates:
            return
        self.cancel_event.clear()
        self._set_busy(True)
        self.status.set(f"✦ Trying {len(candidates)} verified fast servers…")
        self.side_status.set("Establishing secure tunnel…")
        threading.Thread(target=self._connect_worker, args=(candidates,), daemon=True).start()

    @staticmethod
    def _stop_process(process, tmp=None):
        if process is not None:
            try:
                process.terminate()
                process.wait(timeout=3)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)

    def _connect_worker(self, candidates):
        errors = []
        try:
            baseline = engine.public_ip(6)
        except Exception:
            baseline = None
        for server in candidates:
            if self.cancel_event.is_set() or self.process is not None:
                return
            try:
                self.events.put(("status", None, f"✦ {server.get('host') or server.get('ip')} • {server.get('live_ping', 0):.0f} ms • connecting…"))
                runtime_bootstrap.install_bundled_drivers()
                process, tmp, logfile = engine.connect(server, 45)
                if self.cancel_event.is_set():
                    self._stop_process(process, tmp)
                    return
                if process.poll() is not None:
                    raise RuntimeError("VPN process exited after startup")
                ip = engine.verify_tunnel(baseline, 10)
                self.process, self.tmp, self.current_log = process, tmp, logfile
                self.events.put(("connected", None, f"CONNECTED • {server.get('host') or server.get('ip')} • {server.get('live_ping', 0):.0f} ms • IP {ip}"))
                return
            except Exception as exc:
                errors.append(f"{server.get('host') or server.get('ip')}: {exc}")
        if not self.cancel_event.is_set():
            self.events.put(("error", None, "No verified fast server connected.\n\n" + "\n".join(errors[:12])))

    def disconnect(self):
        self.cancel_event.set()
        process, tmp = self.process, self.tmp
        self.process = self.tmp = self.current_log = None
        if process is not None:
            self._stop_process(process, tmp)
        elif tmp:
            shutil.rmtree(tmp, ignore_errors=True)
        if hasattr(self, "status"):
            self.status.set("Disconnected")
        if hasattr(self, "side_status"):
            self.side_status.set("Ready to connect")
        if hasattr(self, "speed_status"):
            self.speed_status.set("● READY")
        if hasattr(self, "refresh_btn"):
            self._set_busy(False)

    @staticmethod
    def _open_path(path):
        try:
            if os.name == "nt":
                os.startfile(str(path))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
            return True
        except Exception:
            return False

    def open_log(self):
        engine.ROOT.mkdir(parents=True, exist_ok=True)
        engine.LOG.touch(exist_ok=True)
        if not self._open_path(engine.LOG):
            messagebox.showinfo(APP, f"Diagnostic log:\n{engine.LOG}")

    def _pump(self):
        try:
            while True:
                kind, data, msg = self.events.get_nowait()
                if kind == "servers":
                    self.servers = data or []
                    self._render()
                    self._set_busy(False)
                    self.status.set(msg)
                    self.side_status.set(f"{len(self.servers)} endpoints verified")
                    self.speed_status.set("● LIVE • pool verified")
                    self.status_pill.configure(fg=MUTED)
                    self._auto_connect_changed()
                elif kind == "status":
                    self.status.set(msg)
                    self.side_status.set("Connecting…")
                elif kind == "connected":
                    self._set_busy(False)
                    self.status.set(msg)
                    self.side_status.set("● Tunnel connected")
                    self.speed_status.set("● CONNECTED • tunnel verified")
                    self.status_pill.configure(fg=SUCCESS)
                elif kind == "error":
                    self._set_busy(False)
                    self.status.set("Connection unavailable")
                    self.side_status.set("Connection failed")
                    self.speed_status.set("● OFFLINE")
                    self.status_pill.configure(fg=DANGER)
                    messagebox.showerror(APP, msg)
        except queue.Empty:
            pass
        self.after(100, self._pump)

    def destroy(self):
        self.disconnect()
        super().destroy()


if __name__ == "__main__":
    App().mainloop()
