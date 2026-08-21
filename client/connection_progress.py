from __future__ import annotations

import time
import tkinter as tk
from tkinter import ttk


BG = "#060811"
PANEL = "#101722"
PANEL_2 = "#151d2b"
BORDER = "#34435c"
TEXT = "#f8faff"
MUTED = "#8c99ad"
ACCENT = "#765cff"
SUCCESS = "#31d9a5"
WARNING = "#ffc46b"
DANGER = "#ff647d"
CYAN = "#61dcff"
FONT = "Segoe UI"


def install_connection_progress(AppClass):
    """Add a real-time connection progress dialog around the existing connect flow.

    The dialog never claims a tunnel is connected by itself. It follows the
    application's status string and closes only when the underlying connection
    reports a terminal state or the safety timeout is reached.
    """
    if getattr(AppClass, "_findupto_progress_installed", False):
        return

    original_connect = AppClass._connect
    AppClass._findupto_original_connect = original_connect

    def _connect_with_progress(self, servers):
        if not servers:
            return
        target = servers[0]
        self._show_connection_progress(target)
        try:
            original_connect(self, servers)
        except Exception as exc:
            self._connection_progress_fail(f"Connection error: {type(exc).__name__}: {exc}")
            raise
        self._connection_progress_poll()

    def _show_connection_progress(self, target):
        old = getattr(self, "_connection_progress", None)
        if old is not None:
            try:
                old.destroy()
            except tk.TclError:
                pass

        win = tk.Toplevel(self)
        self._connection_progress = win
        win.title("Findupto • Secure Connection")
        win.geometry("500x390")
        win.resizable(False, False)
        win.configure(bg=BG)
        win.transient(self)
        win.grab_set()
        win.protocol("WM_DELETE_WINDOW", lambda: None)

        country = target.get("country") or "Unknown country"
        city = target.get("city") or "Unknown city"
        host = target.get("host") or target.get("ip") or "Unknown endpoint"
        ips = target.get("ips") or [target.get("ip") or host]
        ping = target.get("live_ping")
        speed = target.get("speed")
        source = target.get("source") or "Unknown source"

        tk.Label(win, text="SECURE VPN CONNECTION", bg=BG, fg=CYAN,
                 font=(FONT, 9, "bold")).pack(anchor="w", padx=26, pady=(24, 4))
        tk.Label(win, text=f"Connecting to {country} • {city}", bg=BG, fg=TEXT,
                 font=(FONT, 18, "bold")).pack(anchor="w", padx=26)
        tk.Label(win, text=host, bg=BG, fg=MUTED, font=(FONT, 9)).pack(anchor="w", padx=26, pady=(3, 16))

        details = tk.Frame(win, bg=PANEL, highlightthickness=1, highlightbackground=BORDER)
        details.pack(fill="x", padx=22, pady=(0, 14))
        values = [
            ("ROUTE IP", str(ips[0]) if ips else "—"),
            ("LATENCY", f"{float(ping):.0f} ms" if ping is not None else "Testing…"),
            ("SPEED", f"{float(speed):.1f} Mbps" if speed else "Testing…"),
            ("SOURCE", str(source)),
        ]
        for i, (label, value) in enumerate(values):
            cell = tk.Frame(details, bg=PANEL)
            cell.grid(row=i // 2, column=i % 2, sticky="ew", padx=12, pady=8)
            tk.Label(cell, text=label, bg=PANEL, fg=MUTED, font=(FONT, 7, "bold")).pack(anchor="w")
            tk.Label(cell, text=value, bg=PANEL, fg=TEXT, font=(FONT, 9, "bold")).pack(anchor="w")
        details.columnconfigure(0, weight=1)
        details.columnconfigure(1, weight=1)

        self._connection_progress_status = tk.StringVar(value="Preparing secure tunnel…")
        tk.Label(win, textvariable=self._connection_progress_status, bg=BG, fg=TEXT,
                 font=(FONT, 10, "bold")).pack(anchor="w", padx=26, pady=(0, 7))
        self._connection_progress_bar = ttk.Progressbar(win, mode="indeterminate", length=448)
        self._connection_progress_bar.pack(padx=26, fill="x")
        self._connection_progress_bar.start(12)

        self._connection_progress_started = time.monotonic()
        self._connection_progress_target = target
        self._connection_progress_phase = 0
        self._connection_progress_log = []

        actions = tk.Frame(win, bg=BG)
        actions.pack(fill="x", padx=22, pady=(18, 0))
        self._connection_progress_disconnect = tk.Button(
            actions, text="CANCEL / DISCONNECT", command=self._connection_progress_cancel,
            bg=PANEL_2, fg=TEXT, activebackground=DANGER, activeforeground="white",
            relief="flat", bd=0, font=(FONT, 8, "bold"), padx=12, pady=8, cursor="hand2")
        self._connection_progress_disconnect.pack(side="right")

        win.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - win.winfo_width()) // 2
        y = self.winfo_rooty() + (self.winfo_height() - win.winfo_height()) // 2
        win.geometry(f"+{max(0, x)}+{max(0, y)}")

    def _connection_progress_poll(self):
        win = getattr(self, "_connection_progress", None)
        if win is None or not win.winfo_exists():
            return
        elapsed = time.monotonic() - getattr(self, "_connection_progress_started", time.monotonic())
        status = str(getattr(self, "status", tk.StringVar(value="")).get())
        side = str(getattr(self, "side_status", tk.StringVar(value="")).get())
        combined = f"{status} {side}".lower()

        phases = (
            ("discover", "Selecting verified route…"),
            ("config", "Preparing VPN tunnel configuration…"),
            ("openvpn", "Starting encrypted OpenVPN tunnel…"),
            ("connect", "Negotiating secure tunnel…"),
            ("route", "Installing protected network routes…"),
            ("verif", "Verifying tunnel and public IP…"),
            ("connect", "Waiting for VPN connection confirmation…"),
        )
        phase = min(int(elapsed // 2), len(phases) - 1)
        if phase != getattr(self, "_connection_progress_phase", -1):
            self._connection_progress_phase = phase
        if any(word in combined for word in ("connected", "protected", "tunnel active")) and not any(word in combined for word in ("connecting", "disconnecting")):
            self._connection_progress_success(status or "VPN connected")
            return
        if any(word in combined for word in ("failed", "error", "unable", "refused")):
            self._connection_progress_fail(status or side or "VPN connection failed")
            return
        if elapsed >= 120:
            self._connection_progress_fail("Connection timed out after 120 seconds. Check OpenVPN, credentials and the selected endpoint.")
            return
        self._connection_progress_status.set(f"{phases[phase][1]}  •  {int(elapsed)}s")
        self.after(250, self._connection_progress_poll)

    def _connection_progress_success(self, message):
        self._finish_connection_progress(message, SUCCESS, "CONNECTED • VPN tunnel verified")

    def _connection_progress_fail(self, message):
        self._finish_connection_progress(message, DANGER, "CONNECTION FAILED")

    def _finish_connection_progress(self, message, color, title):
        win = getattr(self, "_connection_progress", None)
        if win is None:
            return
        try:
            self._connection_progress_bar.stop()
            self._connection_progress_status.set(message)
            for child in win.winfo_children():
                if isinstance(child, tk.Label) and "SECURE VPN CONNECTION" in str(child.cget("text")):
                    child.configure(text=title, fg=color)
            if color == SUCCESS:
                self._connection_progress_disconnect.configure(text="CLOSE", command=self._close_connection_progress)
            else:
                self._connection_progress_disconnect.configure(text="CLOSE", command=self._close_connection_progress)
        except tk.TclError:
            pass

    def _close_connection_progress(self):
        win = getattr(self, "_connection_progress", None)
        if win is not None:
            try:
                win.grab_release()
                win.destroy()
            except tk.TclError:
                pass
            self._connection_progress = None

    def _connection_progress_cancel(self):
        try:
            fn = getattr(self, "_disconnect", None)
            if fn:
                fn()
            else:
                self.disconnect()
        except Exception:
            pass
        self._connection_progress_fail("Connection cancelled by user")

    AppClass._connect = _connect_with_progress
    AppClass._show_connection_progress = _show_connection_progress
    AppClass._connection_progress_poll = _connection_progress_poll
    AppClass._connection_progress_success = _connection_progress_success
    AppClass._connection_progress_fail = _connection_progress_fail
    AppClass._finish_connection_progress = _finish_connection_progress
    AppClass._close_connection_progress = _close_connection_progress
    AppClass._connection_progress_cancel = _connection_progress_cancel
    AppClass._findupto_progress_installed = True
    return AppClass
