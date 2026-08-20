from __future__ import annotations

import os
import queue
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk

import standalone_engine as engine
import runtime_bootstrap

APP = "Findupto VPN"
VERSION = engine.APP_VERSION


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP} {VERSION}")
        self._set_initial_geometry()
        self.events = queue.Queue()
        self.servers = []
        self.process = None
        self.tmp = None
        self.current_log = None
        self.busy = False
        self._build()
        self.after(100, self._pump)
        self.refresh()

    def _set_initial_geometry(self):
        width = max(760, min(1240, self.winfo_screenwidth() - 80))
        height = max(520, min(720, self.winfo_screenheight() - 120))
        self.geometry(f"{width}x{height}")
        self.minsize(760, 520)

    def _build(self):
        head = ttk.Frame(self, padding=14)
        head.pack(fill="x")
        ttk.Label(head, text=APP, font=("Segoe UI", 20, "bold")).pack(side="left")
        ttk.Label(head, text=f"  Live Free VPN • {VERSION}").pack(side="left", pady=7)
        self.status = tk.StringVar(value="Starting...")
        ttk.Label(self, textvariable=self.status, padding=(14, 0, 14, 10)).pack(fill="x")

        frame = ttk.Frame(self, padding=(14, 0, 14, 0))
        frame.pack(fill="both", expand=True)
        cols = ("country", "city", "host", "ip", "ping", "speed", "source")
        self.tree = ttk.Treeview(frame, columns=cols, show="headings", selectmode="browse")
        widths = (130, 140, 250, 130, 85, 105, 110)
        for col, width in zip(cols, widths):
            self.tree.heading(col, text=col.title())
            self.tree.column(col, width=width, minwidth=70, anchor="w", stretch=True)
        y = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        x = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=y.set, xscrollcommand=x.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        y.grid(row=0, column=1, sticky="ns")
        x.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        bar = ttk.Frame(self, padding=14)
        bar.pack(fill="x")
        self.refresh_btn = ttk.Button(bar, text="Refresh Live Servers", command=self.refresh)
        self.refresh_btn.pack(side="left")
        self.best_btn = ttk.Button(bar, text="Connect Fastest", command=self.best)
        self.best_btn.pack(side="left", padx=7)
        self.sel_btn = ttk.Button(bar, text="Connect Selected", command=self.selected)
        self.sel_btn.pack(side="left")
        ttk.Button(bar, text="Open Diagnostic Log", command=self.open_log).pack(side="left", padx=7)
        ttk.Button(bar, text="Open Latest OpenVPN Log", command=self.open_openvpn_logs).pack(side="left")
        ttk.Button(bar, text="Disconnect", command=self.disconnect).pack(side="right")

    def _set_busy(self, value):
        self.busy = value
        state = "disabled" if value else "normal"
        for button in (self.refresh_btn, self.best_btn, self.sel_btn):
            button.configure(state=state)

    def refresh(self):
        if self.busy:
            return
        self._set_busy(True)
        self.status.set("Discovering live public VPN servers...")
        threading.Thread(target=self._discover_worker, daemon=True).start()

    def _discover_worker(self):
        try:
            data = engine.discover(10)
            self.events.put(("servers", data, f"Live catalog ready — {len(data)} candidates"))
        except Exception as exc:
            engine.log(f"DISCOVERY FATAL {type(exc).__name__}: {exc}")
            self.events.put(("error", None, f"Discovery failed: {exc}\n\n{engine.LOG}"))

    def _render(self, data):
        self.servers = data
        self.tree.delete(*self.tree.get_children())
        for index, server in enumerate(data):
            ping = "-" if server.get("ping", 9999) >= 9999 else f"{server['ping']:.0f} ms"
            speed = "-" if not server.get("speed") else f"{server['speed']:.1f} Mbps"
            self.tree.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    server.get("country", ""),
                    server.get("city", ""),
                    server.get("host", ""),
                    server.get("ip", ""),
                    ping,
                    speed,
                    server.get("source", ""),
                ),
            )

    def best(self):
        if not self.servers:
            messagebox.showwarning(APP, "No servers available. Refresh first.")
            return
        gate = [s for s in self.servers if s.get("kind") == "gate"][:32]
        book = [s for s in self.servers if s.get("kind") == "book"][:8]
        self._connect(gate + book)

    def selected(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning(APP, "Select a server first.")
            return
        self._connect([self.servers[int(selected[0])]])

    def _connect(self, candidates):
        if self.busy:
            return
        if not candidates:
            messagebox.showwarning(APP, "No valid server candidates are available.")
            return
        self._set_busy(True)
        self.status.set(
            f"Trying {len(candidates)} live candidates; full-tunnel verification is mandatory..."
        )
        threading.Thread(target=self._connect_worker, args=(candidates,), daemon=True).start()

    def _connect_worker(self, candidates):
        errors = []
        try:
            baseline = engine.public_ip(6)
            engine.log(f"CONNECT BASELINE public_ip={baseline}")
        except Exception as exc:
            baseline = None
            engine.log(f"CONNECT BASELINE unavailable error={type(exc).__name__}: {exc}")

        for server in candidates:
            if self.process is not None:
                return
            try:
                self.events.put(("status", None, f"Trying {server['host']} ({server['source']})..."))
                if not runtime_bootstrap.install_bundled_drivers():
                    engine.log(
                        "RUNTIME DRIVER bootstrap: no bundled INF installed; "
                        "continuing with existing driver"
                    )
                process, tmp, logfile = engine.connect(server, 45)
                try:
                    if process.poll() is not None:
                        raise RuntimeError("VPN process exited immediately after initialization")
                    ip = engine.verify_tunnel(baseline, 10)
                except Exception as verify_exc:
                    engine.log(
                        f"POST-CONNECT VERIFICATION FAIL server={server['host']} "
                        f"error={type(verify_exc).__name__}: {verify_exc}"
                    )
                    try:
                        process.terminate()
                        process.wait(timeout=3)
                    except Exception:
                        try:
                            process.kill()
                        except Exception:
                            pass
                    shutil.rmtree(tmp, ignore_errors=True)
                    raise
                self.process, self.tmp, self.current_log = process, tmp, logfile
                engine.log(
                    f"VPN CONNECTED AND VERIFIED server={server['host']} public_ip={ip}"
                )
                self.events.put(
                    ("connected", None, f"CONNECTED — {server['host']} — public IP {ip}")
                )
                return
            except Exception as exc:
                message = f"{server['host']}: {exc}"
                errors.append(message)
                engine.log(message)
        self.events.put(
            (
                "error",
                None,
                "No candidate connected successfully.\n\n"
                + "\n".join(errors[:20])
                + f"\n\nDiagnostic log:\n{engine.LOG}\nLatest OpenVPN failure log:\n{engine.PROFILE_LOGS}",
            )
        )

    def disconnect(self):
        process = self.process
        self.process = None
        if process is not None:
            engine.log("DISCONNECT")
            try:
                process.terminate()
                process.wait(timeout=3)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass
        if self.tmp:
            shutil.rmtree(self.tmp, ignore_errors=True)
            self.tmp = None
        self.current_log = None
        if hasattr(self, "status"):
            self.status.set("Disconnected")
        if hasattr(self, "refresh_btn"):
            self._set_busy(False)

    @staticmethod
    def _open_path(path):
        path = str(path)
        try:
            if os.name == "nt":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
            return True
        except Exception:
            return False

    def open_log(self):
        engine.ROOT.mkdir(parents=True, exist_ok=True)
        engine.LOG.touch(exist_ok=True)
        if not self._open_path(engine.LOG):
            messagebox.showinfo(APP, f"Diagnostic log:\n{engine.LOG}")

    def open_openvpn_logs(self):
        engine.PROFILE_LOGS.mkdir(parents=True, exist_ok=True)
        if not self._open_path(engine.PROFILE_LOGS):
            messagebox.showinfo(APP, f"Latest OpenVPN failure log:\n{engine.PROFILE_LOGS}")

    def _pump(self):
        try:
            while True:
                kind, data, message = self.events.get_nowait()
                if kind == "servers":
                    self._render(data)
                    self._set_busy(False)
                    self.status.set(message)
                elif kind == "status":
                    self.status.set(message)
                elif kind == "connected":
                    self._set_busy(False)
                    self.status.set(message)
                elif kind == "error":
                    self._set_busy(False)
                    self.status.set("Failed — see diagnostics")
                    messagebox.showerror(APP, message)
        except queue.Empty:
            pass
        self.after(100, self._pump)

    def destroy(self):
        self.disconnect()
        super().destroy()


if __name__ == "__main__":
    App().mainloop()
