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

APP = "Findupto VPN"
VERSION = engine.APP_VERSION
FAST_LIMIT_MS = 250
PROBE_TIMEOUT = 2.5

# Luxury dark glass-inspired palette. Tkinter keeps this lightweight and portable.
BG = "#0a0d14"
PANEL = "#111722"
PANEL_2 = "#151c29"
BORDER = "#273246"
TEXT = "#f5f7fb"
MUTED = "#8f9aae"
ACCENT = "#7c5cff"
ACCENT_2 = "#9a82ff"
SUCCESS = "#31d6a5"
WARNING = "#ffbf69"
DANGER = "#ff6b81"
CYAN = "#5ddcff"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP} {VERSION}")
        width = max(980, min(1450, self.winfo_screenwidth() - 55))
        height = max(680, min(900, self.winfo_screenheight() - 75))
        self.geometry(f"{width}x{height}")
        self.minsize(980, 680)
        self.configure(bg=BG)
        self.events = queue.Queue(); self.servers = []
        self.process = self.tmp = self.current_log = None
        self.busy = False; self.cancel_event = threading.Event()
        self._configure_styles(); self._build(); self.after(100, self._pump); self.refresh()

    def _configure_styles(self):
        style = ttk.Style(self)
        try: style.theme_use("clam")
        except tk.TclError: pass
        style.configure("TFrame", background=BG)
        style.configure("Panel.TFrame", background=PANEL)
        style.configure("TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background=BG, foreground=MUTED, font=("Segoe UI", 9))
        style.configure("Card.TLabel", background=PANEL, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Title.TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 25, "bold"))
        style.configure("Sub.TLabel", background=BG, foreground=MUTED, font=("Segoe UI", 10))
        style.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=TEXT, rowheight=38, borderwidth=0, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", background=PANEL_2, foreground=MUTED, relief="flat", font=("Segoe UI", 9, "bold"))
        style.map("Treeview", background=[("selected", "#252d42")], foreground=[("selected", TEXT)])
        style.configure("TCheckbutton", background=PANEL, foreground=TEXT, font=("Segoe UI", 9))
        style.map("TCheckbutton", background=[("active", PANEL)], foreground=[("active", TEXT)])
        style.configure("TSpinbox", fieldbackground=PANEL_2, background=PANEL_2, foreground=TEXT, arrowcolor=MUTED)

    def _button(self, parent, text, command, kind="secondary", width=None):
        palette = {
            "primary": (ACCENT, "#ffffff", ACCENT_2),
            "success": (SUCCESS, BG, "#50e7bb"),
            "danger": (DANGER, BG, "#ff8da0"),
            "secondary": (PANEL_2, TEXT, "#202a3b"),
            "ghost": (BG, MUTED, PANEL_2),
        }
        bg, fg, active = palette[kind]
        b = tk.Button(parent, text=text, command=command, bg=bg, fg=fg, activebackground=active,
                      activeforeground=fg, relief="flat", bd=0, highlightthickness=1,
                      highlightbackground=BORDER, highlightcolor=ACCENT, cursor="hand2",
                      font=("Segoe UI", 10, "bold"), padx=17, pady=10)
        if width: b.configure(width=width)
        return b

    def _card(self, parent):
        f = tk.Frame(parent, bg=PANEL, highlightthickness=1, highlightbackground=BORDER)
        return f

    def _build(self):
        header = ttk.Frame(self, padding=(28, 24, 28, 12)); header.pack(fill="x")
        brand = ttk.Frame(header); brand.pack(side="left")
        tk.Label(brand, text="F", bg=ACCENT, fg="white", font=("Segoe UI", 15, "bold"), width=3, pady=7).pack(side="left", padx=(0, 12))
        copy = ttk.Frame(brand); copy.pack(side="left")
        ttk.Label(copy, text=APP, style="Title.TLabel").pack(anchor="w")
        ttk.Label(copy, text="PRIVATE • FAST • VERIFIED", style="Sub.TLabel").pack(anchor="w", pady=(2, 0))
        right = ttk.Frame(header); right.pack(side="right")
        self.status = tk.StringVar(value="Starting secure server scan…")
        tk.Label(right, textvariable=self.status, bg=PANEL, fg=MUTED, padx=15, pady=9, font=("Segoe UI", 9, "bold")).pack(side="right")
        tk.Label(right, text=f"v{VERSION}", bg=PANEL_2, fg=ACCENT_2, padx=12, pady=8, font=("Segoe UI", 9, "bold")).pack(side="right", padx=8)

        controls = tk.Frame(self, bg=BG); controls.pack(fill="x", padx=28, pady=(2, 14))
        filter_card = self._card(controls); filter_card.pack(side="left", fill="x", expand=True)
        tk.Label(filter_card, text="SMART FILTERS", bg=PANEL, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(side="left", padx=(16, 10), pady=13)
        self.fast_only = tk.BooleanVar(value=True); self.available_only = tk.BooleanVar(value=True); self.auto_connect = tk.BooleanVar(value=False)
        ttk.Checkbutton(filter_card, text="Fast", variable=self.fast_only, command=self._apply_filters).pack(side="left", padx=7)
        ttk.Checkbutton(filter_card, text="Available", variable=self.available_only, command=self._apply_filters).pack(side="left", padx=7)
        ttk.Checkbutton(filter_card, text="Auto Connect", variable=self.auto_connect, command=self._auto_connect_changed).pack(side="left", padx=7)
        tk.Label(filter_card, text="MAX PING", bg=PANEL, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(side="left", padx=(18, 6))
        self.max_ping = tk.IntVar(value=250); ttk.Spinbox(filter_card, from_=50, to=2000, increment=25, width=6, textvariable=self.max_ping, command=self._apply_filters).pack(side="left")
        tk.Label(filter_card, text="ms", bg=PANEL, fg=MUTED).pack(side="left", padx=(4, 14))
        self._button(controls, "⚙ Settings", self.open_log, "secondary").pack(side="right", padx=(10, 0))

        stats = tk.Frame(self, bg=BG); stats.pack(fill="x", padx=28, pady=(0, 14))
        self.stat_cards = {}
        for key, label in (("shown", "SHOWN"), ("available", "AVAILABLE"), ("fast", "FAST SERVERS"), ("tested", "TESTED")):
            card = self._card(stats); card.pack(side="left", fill="x", expand=True, padx=(0, 9 if key != "tested" else 0))
            value = tk.StringVar(value="0"); tk.Label(card, textvariable=value, bg=PANEL, fg=TEXT, font=("Segoe UI", 20, "bold")).pack(anchor="w", padx=15, pady=(10, 0))
            tk.Label(card, text=label, bg=PANEL, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=15, pady=(0, 11))
            self.stat_cards[key] = value

        body = self._card(self); body.pack(fill="both", expand=True, padx=28, pady=(0, 14))
        top = tk.Frame(body, bg=PANEL); top.pack(fill="x", padx=16, pady=13)
        tk.Label(top, text="FAST SERVER LOUNGE", bg=PANEL, fg=TEXT, font=("Segoe UI", 12, "bold")).pack(side="left")
        self.speed_status = tk.StringVar(value="Live availability probing…")
        tk.Label(top, textvariable=self.speed_status, bg=PANEL, fg=SUCCESS, font=("Segoe UI", 9, "bold")).pack(side="right")
        frame = tk.Frame(body, bg=PANEL); frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        cols = ("status", "country", "city", "host", "ping", "speed", "score", "source")
        self.tree = ttk.Treeview(frame, columns=cols, show="headings", selectmode="browse")
        widths = (105, 120, 120, 245, 80, 100, 85, 105)
        for col, width in zip(cols, widths):
            self.tree.heading(col, text=col.upper()); self.tree.column(col, width=width, minwidth=65, anchor="w", stretch=True)
        y = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview); x = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=y.set, xscrollcommand=x.set); self.tree.grid(row=0, column=0, sticky="nsew"); y.grid(row=0, column=1, sticky="ns"); x.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1); frame.columnconfigure(0, weight=1)

        bar = tk.Frame(self, bg=BG); bar.pack(fill="x", padx=28, pady=(0, 22))
        self.refresh_btn = self._button(bar, "↻  Scan & Test", self.refresh, "secondary"); self.refresh_btn.pack(side="left")
        self.best_btn = self._button(bar, "✦  Connect Fastest", self.best, "primary"); self.best_btn.pack(side="left", padx=8)
        self.sel_btn = self._button(bar, "➜  Connect Selected", self.selected, "secondary"); self.sel_btn.pack(side="left")
        self._button(bar, "◉  Diagnostics", self.open_log, "ghost").pack(side="left", padx=8)
        self._button(bar, "▣  OpenVPN Logs", self.open_openvpn_logs, "ghost").pack(side="left")
        self._button(bar, "■  Disconnect", self.disconnect, "danger").pack(side="right")

    def _set_busy(self, value):
        self.busy = value; state = "disabled" if value else "normal"
        for b in (self.refresh_btn, self.best_btn, self.sel_btn): b.configure(state=state)

    def _auto_connect_changed(self):
        if self.auto_connect.get() and not self.busy: self.best()

    @staticmethod
    def _probe(server):
        host = str(server.get("ip") or server.get("host") or "")
        if not host: return dict(server, available=False, live_ping=9999)
        best = None
        for port in ((443, 80, 53) if server.get("kind") == "gate" else (443, 80)):
            started = time.monotonic()
            try:
                with socket.create_connection((host, port), timeout=PROBE_TIMEOUT):
                    latency = (time.monotonic() - started) * 1000; best = latency if best is None else min(best, latency)
            except OSError: continue
        if best is None: return dict(server, available=False, live_ping=9999)
        return dict(server, available=True, live_ping=best, ping=best, rank=float(server.get("rank", 0)) + max(0, 500 - best))

    def refresh(self):
        if self.busy: return
        self.cancel_event.clear(); self._set_busy(True); self.status.set("Scanning 100+ candidates with live probes…")
        threading.Thread(target=self._discover_worker, daemon=True).start()

    def _discover_worker(self):
        try:
            data = engine.discover(10); tested = []
            with ThreadPoolExecutor(max_workers=24, thread_name_prefix="vpn-probe") as pool:
                futures = [pool.submit(self._probe, s) for s in data[:100]]
                for f in as_completed(futures):
                    if self.cancel_event.is_set(): break
                    tested.append(f.result())
            tested.sort(key=lambda s: (not s.get("available", False), s.get("live_ping", 9999), -float(s.get("speed", 0)), -float(s.get("rank", 0))))
            self.events.put(("servers", tested, f"Live scan complete • {len(tested)} servers verified"))
        except Exception as exc:
            engine.log(f"DISCOVERY/PROBE FATAL {type(exc).__name__}: {exc}"); self.events.put(("error", None, f"Server discovery failed: {exc}"))

    def _apply_filters(self): self._render()

    def _eligible(self):
        try: limit = max(50, int(self.max_ping.get()))
        except Exception: limit = FAST_LIMIT_MS
        return sorted([s for s in self.servers if (not self.available_only.get() or s.get("available")) and (not self.fast_only.get() or float(s.get("live_ping", s.get("ping", 9999))) <= limit)], key=lambda s: (s.get("live_ping", 9999), -float(s.get("speed", 0)), -float(s.get("rank", 0))))

    def _render(self):
        self.tree.delete(*self.tree.get_children()); visible = self._eligible(); index_map = {id(s): i for i, s in enumerate(self.servers)}
        for s in visible:
            ping = float(s.get("live_ping", s.get("ping", 9999))); speed = s.get("speed") or 0; score = s.get("rank", s.get("score", 0))
            self.tree.insert("", "end", iid=str(index_map[id(s)]), values=("● FAST" if s.get("available") and ping <= FAST_LIMIT_MS else "● ONLINE", s.get("country", ""), s.get("city", ""), s.get("host", ""), "—" if ping >= 9999 else f"{ping:.0f} ms", f"{speed:.1f} Mbps" if speed else "—", f"{float(score):.0f}", s.get("source", "")))
        available = sum(bool(s.get("available")) for s in self.servers); fast = sum(bool(s.get("available")) and float(s.get("live_ping", 9999)) <= FAST_LIMIT_MS for s in self.servers)
        self.stat_cards["shown"].set(str(len(visible))); self.stat_cards["available"].set(str(available)); self.stat_cards["fast"].set(str(fast)); self.stat_cards["tested"].set(str(len(self.servers)))

    def best(self):
        candidates = self._eligible()
        if not candidates: messagebox.showwarning(APP, "No fast, available server passed the current filters. Refresh or raise the ping limit."); return
        self._connect(candidates[:24])

    def selected(self):
        selected = self.tree.selection()
        if not selected: messagebox.showwarning(APP, "Select a server first."); return
        try: server = self.servers[int(selected[0])]
        except (ValueError, IndexError): messagebox.showwarning(APP, "That server is no longer in the live list."); return
        if self.available_only.get() and not server.get("available"): messagebox.showwarning(APP, "This server is not currently available."); return
        self._connect([server])

    def _connect(self, candidates):
        if self.busy or not candidates: return
        self.cancel_event.clear(); self._set_busy(True); self.status.set(f"✦ Trying {len(candidates)} verified fast candidates…")
        threading.Thread(target=self._connect_worker, args=(candidates,), daemon=True).start()

    @staticmethod
    def _stop_process(process, tmp=None):
        if process is not None:
            try: process.terminate(); process.wait(timeout=3)
            except Exception:
                try: process.kill()
                except Exception: pass
        if tmp: shutil.rmtree(tmp, ignore_errors=True)

    def _connect_worker(self, candidates):
        errors = []
        try: baseline = engine.public_ip(6)
        except Exception: baseline = None
        for server in candidates:
            if self.cancel_event.is_set() or self.process is not None: return
            try:
                self.events.put(("status", None, f"✦ {server['host']} • {server.get('live_ping', 0):.0f} ms • connecting…")); runtime_bootstrap.install_bundled_drivers()
                process, tmp, logfile = engine.connect(server, 45)
                if self.cancel_event.is_set(): self._stop_process(process, tmp); return
                if process.poll() is not None: raise RuntimeError("VPN process exited after startup")
                ip = engine.verify_tunnel(baseline, 10); self.process, self.tmp, self.current_log = process, tmp, logfile
                engine.log(f"VPN CONNECTED VERIFIED server={server['host']} public_ip={ip} live_ping={server.get('live_ping')}")
                self.events.put(("connected", None, f"CONNECTED • {server['host']} • {server.get('live_ping', 0):.0f} ms • IP {ip}")); return
            except Exception as exc: errors.append(f"{server['host']}: {exc}"); engine.log(errors[-1])
        if not self.cancel_event.is_set(): self.events.put(("error", None, "No verified fast server connected.\n\n" + "\n".join(errors[:12])))

    def disconnect(self):
        self.cancel_event.set(); process, tmp = self.process, self.tmp; self.process = self.tmp = self.current_log = None
        if process is not None: self._stop_process(process, tmp)
        elif tmp: shutil.rmtree(tmp, ignore_errors=True)
        if hasattr(self, "status"): self.status.set("Disconnected")
        if hasattr(self, "refresh_btn"): self._set_busy(False)

    @staticmethod
    def _open_path(path):
        try:
            if os.name == "nt": os.startfile(str(path))
            elif sys.platform == "darwin": subprocess.Popen(["open", str(path)])
            else: subprocess.Popen(["xdg-open", str(path)])
            return True
        except Exception: return False

    def open_log(self):
        engine.ROOT.mkdir(parents=True, exist_ok=True); engine.LOG.touch(exist_ok=True)
        if not self._open_path(engine.LOG): messagebox.showinfo(APP, f"Diagnostic log:\n{engine.LOG}")

    def open_openvpn_logs(self):
        engine.PROFILE_LOGS.mkdir(parents=True, exist_ok=True)
        if not self._open_path(engine.PROFILE_LOGS): messagebox.showinfo(APP, f"OpenVPN logs:\n{engine.PROFILE_LOGS}")

    def _pump(self):
        try:
            while True:
                kind, data, msg = self.events.get_nowait()
                if kind == "servers": self.servers = data or []; self._render(); self._set_busy(False); self.status.set(msg); self.speed_status.set("● LIVE • availability verified"); self._auto_connect_changed()
                elif kind == "status": self.status.set(msg)
                elif kind == "connected": self._set_busy(False); self.status.set(msg); self.speed_status.set("● CONNECTED • tunnel verified")
                elif kind == "error": self._set_busy(False); self.status.set("Connection unavailable"); self.speed_status.set("● OFFLINE"); messagebox.showerror(APP, msg)
        except queue.Empty: pass
        self.after(100, self._pump)

    def destroy(self): self.disconnect(); super().destroy()


if __name__ == "__main__": App().mainloop()
