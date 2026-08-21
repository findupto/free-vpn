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


class App(tk.Tk):
    def __init__(self):
        super().__init__(); self.title(f"{APP} {VERSION}")
        width = max(860, min(1320, self.winfo_screenwidth() - 70)); height = max(600, min(800, self.winfo_screenheight() - 100))
        self.geometry(f"{width}x{height}"); self.minsize(860, 600)
        self.events = queue.Queue(); self.servers = []; self.process = self.tmp = self.current_log = None
        self.busy = False; self.cancel_event = threading.Event(); self._build(); self.after(100, self._pump); self.refresh()

    def _build(self):
        head = ttk.Frame(self, padding=(18, 16, 18, 8)); head.pack(fill="x")
        ttk.Label(head, text=APP, font=("Segoe UI", 22, "bold")).pack(side="left")
        ttk.Label(head, text=f"  FAST • LIVE • AUTO CONNECT  {VERSION}").pack(side="left", padx=12, pady=7)
        self.status = tk.StringVar(value="Starting..."); ttk.Label(self, textvariable=self.status, padding=(18, 0, 18, 10)).pack(fill="x")
        filters = ttk.LabelFrame(self, text="Fast server filters", padding=10); filters.pack(fill="x", padx=18, pady=(0, 10))
        self.fast_only = tk.BooleanVar(value=True); self.available_only = tk.BooleanVar(value=True); self.auto_connect = tk.BooleanVar(value=False)
        ttk.Checkbutton(filters, text="Fast only (<250 ms)", variable=self.fast_only, command=self._apply_filters).pack(side="left", padx=6)
        ttk.Checkbutton(filters, text="Available only", variable=self.available_only, command=self._apply_filters).pack(side="left", padx=6)
        ttk.Checkbutton(filters, text="Auto-connect fastest verified", variable=self.auto_connect, command=self._auto_connect_changed).pack(side="left", padx=6)
        ttk.Label(filters, text="Max ping:").pack(side="left", padx=(18, 5))
        self.max_ping = tk.IntVar(value=250); ttk.Spinbox(filters, from_=50, to=2000, increment=25, width=7, textvariable=self.max_ping, command=self._apply_filters).pack(side="left")
        ttk.Label(filters, text="ms").pack(side="left", padx=3)
        stats = ttk.Frame(self, padding=(18, 0, 18, 8)); stats.pack(fill="x")
        self.stats = tk.StringVar(value="0 servers"); ttk.Label(stats, textvariable=self.stats, font=("Segoe UI", 11, "bold")).pack(side="left")
        self.speed_status = tk.StringVar(value="Live availability probing..."); ttk.Label(stats, textvariable=self.speed_status).pack(side="right")
        frame = ttk.Frame(self, padding=(18, 0, 18, 0)); frame.pack(fill="both", expand=True)
        cols = ("status", "country", "city", "host", "ping", "speed", "score", "source")
        self.tree = ttk.Treeview(frame, columns=cols, show="headings", selectmode="browse")
        for col, width in zip(cols, (90, 125, 120, 240, 80, 100, 90, 105)):
            self.tree.heading(col, text=col.title()); self.tree.column(col, width=width, minwidth=65, anchor="w", stretch=True)
        y = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview); x = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=y.set, xscrollcommand=x.set); self.tree.grid(row=0, column=0, sticky="nsew"); y.grid(row=0, column=1, sticky="ns"); x.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1); frame.columnconfigure(0, weight=1)
        bar = ttk.Frame(self, padding=14); bar.pack(fill="x")
        self.refresh_btn = ttk.Button(bar, text="Refresh & Test Servers", command=self.refresh); self.refresh_btn.pack(side="left")
        self.best_btn = ttk.Button(bar, text="⚡ Connect Fastest", command=self.best); self.best_btn.pack(side="left", padx=7)
        self.sel_btn = ttk.Button(bar, text="Connect Selected", command=self.selected); self.sel_btn.pack(side="left")
        ttk.Button(bar, text="Diagnostics", command=self.open_log).pack(side="left", padx=7); ttk.Button(bar, text="OpenVPN Logs", command=self.open_openvpn_logs).pack(side="left"); ttk.Button(bar, text="Disconnect", command=self.disconnect).pack(side="right")

    def _set_busy(self, value):
        self.busy = value; state = "disabled" if value else "normal"
        for b in (self.refresh_btn, self.best_btn, self.sel_btn): b.configure(state=state)

    def _auto_connect_changed(self):
        if self.auto_connect.get() and not self.busy:
            self.best()

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
        self.cancel_event.clear(); self._set_busy(True); self.status.set("Discovering servers and testing availability in parallel...")
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
            self.events.put(("servers", tested, f"Live test complete — {len(tested)} servers checked"))
        except Exception as exc:
            engine.log(f"DISCOVERY/PROBE FATAL {type(exc).__name__}: {exc}"); self.events.put(("error", None, f"Server discovery failed: {exc}"))

    def _apply_filters(self): self._render()

    def _eligible(self):
        try: limit = max(50, int(self.max_ping.get()))
        except Exception: limit = FAST_LIMIT_MS
        return sorted([s for s in self.servers if (not self.available_only.get() or s.get("available")) and (not self.fast_only.get() or float(s.get("live_ping", s.get("ping", 9999))) <= limit)], key=lambda s: (s.get("live_ping", 9999), -float(s.get("speed", 0)), -float(s.get("rank", 0))))

    def _render(self):
        self.tree.delete(*self.tree.get_children())
        visible = self._eligible()
        index_map = {id(s): i for i, s in enumerate(self.servers)}
        for s in visible:
            ping = float(s.get("live_ping", s.get("ping", 9999))); speed = s.get("speed") or 0; score = s.get("rank", s.get("score", 0))
            self.tree.insert("", "end", iid=str(index_map[id(s)]), values=("● FAST" if s.get("available") and ping <= FAST_LIMIT_MS else "● ONLINE", s.get("country", ""), s.get("city", ""), s.get("host", ""), "-" if ping >= 9999 else f"{ping:.0f} ms", f"{speed:.1f} Mbps" if speed else "-", f"{float(score):.0f}", s.get("source", "")))
        available = sum(bool(s.get("available")) for s in self.servers); fast = sum(bool(s.get("available")) and float(s.get("live_ping", 9999)) <= FAST_LIMIT_MS for s in self.servers)
        self.stats.set(f"{len(visible)} shown  •  {available} available  •  {fast} fast  •  {len(self.servers)} tested")

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
        self.cancel_event.clear(); self._set_busy(True); self.status.set(f"⚡ Trying up to {len(candidates)} verified fast servers...")
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
                self.events.put(("status", None, f"⚡ {server['host']} • {server.get('live_ping', 0):.0f} ms • connecting...")); runtime_bootstrap.install_bundled_drivers()
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
                if kind == "servers": self.servers = data or []; self._render(); self._set_busy(False); self.status.set(msg); self.speed_status.set("Live availability verified"); self._auto_connect_changed()
                elif kind == "status": self.status.set(msg)
                elif kind == "connected": self._set_busy(False); self.status.set(msg)
                elif kind == "error": self._set_busy(False); self.status.set("No connection"); messagebox.showerror(APP, msg)
        except queue.Empty: pass
        self.after(100, self._pump)

    def destroy(self): self.disconnect(); super().destroy()


if __name__ == "__main__": App().mainloop()
