from __future__ import annotations

import time
import tkinter as tk
from tkinter import ttk

from country_spinner import CountrySpinner
from connection_progress import install_connection_progress
from gui_elite import App as EliteApp, BG, SURFACE, PANEL, PANEL_2, PANEL_3, BORDER, BORDER_HI, TEXT, MUTED, ACCENT, ACCENT_2, SUCCESS, WARNING, CYAN, FONT

FLAGS = {
    "Denmark": "🇩🇰", "United States": "🇺🇸", "Japan": "🇯🇵", "Germany": "🇩🇪",
    "United Kingdom": "🇬🇧", "Canada": "🇨🇦", "France": "🇫🇷", "Netherlands": "🇳🇱",
    "Singapore": "🇸🇬", "Australia": "🇦🇺", "Switzerland": "🇨🇭", "Sweden": "🇸🇪",
    "Norway": "🇳🇴", "Finland": "🇫🇮", "Poland": "🇵🇱", "Brazil": "🇧🇷",
    "India": "🇮🇳", "Hong Kong": "🇭🇰", "Korea Republic of": "🇰🇷", "Taiwan": "🇹🇼",
}


class App(EliteApp):
    """Ultra-premium dashboard with explicit live IP route inspection and automatic rotation."""

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

    def _build_premium_content(self):
        super()._build_premium_content()
        self._build_ip_inspector()
        self._spinner_tick()

    def _build_ip_inspector(self):
        self.ip_panel = self._card(self.content, bg=SURFACE, accent=True, glow=True)
        self.ip_panel.pack(fill="x", padx=30, pady=(0, 10), before=self.action_bar)
        head = tk.Frame(self.ip_panel, bg=SURFACE)
        head.pack(fill="x", padx=16, pady=(10, 6))
        left = tk.Frame(head, bg=SURFACE); left.pack(side="left", fill="x", expand=True)
        tk.Label(left, text="◈  LIVE IP ROUTE INSPECTOR", bg=SURFACE, fg=CYAN, font=(FONT, 8, "bold")).pack(anchor="w")
        tk.Label(left, text="Every discovered endpoint, visible and ready to inspect.", bg=SURFACE, fg=TEXT, font=(FONT, 11, "bold")).pack(anchor="w", pady=(2, 0))
        self.ip_summary = tk.Label(head, text="SELECT A SERVER", bg=PANEL_2, fg=MUTED, padx=12, pady=7, font=(FONT, 8, "bold"), highlightthickness=1, highlightbackground=BORDER_HI)
        self.ip_summary.pack(side="right")

        body = tk.Frame(self.ip_panel, bg=SURFACE); body.pack(fill="x", padx=14, pady=(0, 12))
        meta = tk.Frame(body, bg=PANEL); meta.pack(fill="x", pady=(0, 7))
        self.ip_route_title = tk.Label(meta, text="No route selected", bg=PANEL, fg=TEXT, font=(FONT, 9, "bold"), padx=12, pady=8)
        self.ip_route_title.pack(side="left")
        self.ip_route_meta = tk.Label(meta, text="Double-click any server row or select a route", bg=PANEL, fg=MUTED, font=(FONT, 8))
        self.ip_route_meta.pack(side="right", padx=12)

        list_frame = tk.Frame(body, bg=PANEL_2, highlightthickness=1, highlightbackground=BORDER)
        list_frame.pack(fill="x")
        self.ip_list_canvas = tk.Canvas(list_frame, height=92, bg=PANEL_2, highlightthickness=0, bd=0)
        self.ip_list_canvas.pack(side="left", fill="both", expand=True)
        ip_scroll = ttk.Scrollbar(list_frame, orient="horizontal", command=self.ip_list_canvas.xview)
        ip_scroll.pack(side="bottom", fill="x")
        self.ip_list_canvas.configure(xscrollcommand=ip_scroll.set)
        self.ip_list_inner = tk.Frame(self.ip_list_canvas, bg=PANEL_2)
        self.ip_list_window = self.ip_list_canvas.create_window((8, 8), window=self.ip_list_inner, anchor="nw")
        self.ip_list_canvas.bind("<Configure>", lambda e: self.ip_list_canvas.itemconfigure(self.ip_list_window, height=max(76, e.height - 8)))
        self._show_ip_empty()

        self.tree.bind("<<TreeviewSelect>>", self._on_server_selected, add="+")
        self.tree.bind("<Double-1>", self._on_server_double_click)

    def _show_ip_empty(self):
        for w in self.ip_list_inner.winfo_children(): w.destroy()
        tk.Label(self.ip_list_inner, text="Select a server to reveal its complete verified IP route list", bg=PANEL_2, fg=MUTED, font=(FONT, 9)).pack(padx=14, pady=20)
        self.ip_list_canvas.configure(scrollregion=(0, 0, 560, 92))

    def _on_server_selected(self, _event=None):
        selection = self.tree.selection()
        if not selection:
            return
        try:
            server = self.servers[int(selection[0])]
        except (ValueError, IndexError, TypeError):
            return
        self._selected_server = server
        self._render_ip_inspector(server)

    def _on_server_double_click(self, _event=None):
        self.selected()

    def _render_ip_inspector(self, server):
        country = server.get("country") or "Global"
        city = server.get("city") or "Any city"
        host = server.get("host") or server.get("ip") or "Unknown endpoint"
        ips = [str(x) for x in (server.get("ips") or []) if x]
        if not ips and server.get("ip"):
            ips = [str(server.get("ip"))]
        if not ips and host:
            ips = [host]
        ping = float(server.get("live_ping", 9999) or 9999)
        speed = float(server.get("speed", 0) or 0)
        self.ip_summary.configure(text=f"{len(ips)} VERIFIED IP ROUTES", fg=SUCCESS if ips else MUTED)
        self.ip_route_title.configure(text=f"{FLAGS.get(country, '◈')}  {country}  •  {city}")
        perf = f"{ping:.0f} ms" if ping < 9999 else "LATENCY —"
        rate = f"{speed:.1f} Mbps" if speed else "SPEED —"
        self.ip_route_meta.configure(text=f"{host}   •   {perf}   •   {rate}")
        for w in self.ip_list_inner.winfo_children(): w.destroy()
        for index, ip in enumerate(ips):
            card = tk.Frame(self.ip_list_inner, bg=PANEL_3, highlightthickness=1, highlightbackground=BORDER_HI)
            card.pack(side="left", padx=(0, 8), pady=8)
            tk.Label(card, text=f"{index + 1:02d}", bg=ACCENT if index == 0 else PANEL_3, fg="white", font=(FONT, 8, "bold"), padx=8, pady=7).pack(side="left")
            tk.Label(card, text=ip, bg=PANEL_3, fg=TEXT, font=(FONT, 9, "bold"), padx=10, pady=7).pack(side="left")
            tk.Button(card, text="CONNECT", command=lambda s=server: self._connect([s]), bg=ACCENT, fg="white", activebackground=ACCENT_2, activeforeground="white", relief="flat", bd=0, cursor="hand2", font=(FONT, 7, "bold"), padx=8, pady=6).pack(side="left", padx=(0, 5), pady=4)
        self.ip_list_inner.update_idletasks()
        self.ip_list_canvas.configure(scrollregion=self.ip_list_canvas.bbox("all"))

    def _spinner_interval_changed(self, _event=None):
        value = int(self.spinner_interval_var.get().split()[0]); self.spinner_interval = value; self.spinner_countdown = value
        if self.spinner_enabled:
            self.country_spinner.disable(); self.country_spinner.enable(self._spinner_servers, interval=value); self._spinner_started = time.monotonic()

    def _spinner_servers(self):
        return list(getattr(self, "servers", []) or [])

    def toggle_spinner(self):
        if self.spinner_enabled:
            self.country_spinner.disable(); self.spinner_enabled = False; self._spinner_rotating = False
            self.spinner_badge.configure(text="OFF", fg=MUTED, bg=PANEL_2); self.spinner_toggle.configure(text="◉  ENABLE SPINNER", bg=ACCENT)
            self.spinner_countdown_label.configure(text="NEXT SWITCH  •  STANDBY", fg=MUTED); self.side_status.set("Automatic country rotation is paused"); return
        available = [s for s in self._spinner_servers() if s.get("available")]
        if not available:
            self.side_status.set("Scan the network first to activate Country Spinner"); self.spinner_countdown_label.configure(text="NEXT SWITCH  •  SCAN REQUIRED", fg=WARNING); return
        self.spinner_enabled = True; self.spinner_countdown = self.spinner_interval; self._spinner_started = time.monotonic()
        self.country_spinner.current_country = self.spinner_current; self.country_spinner.enable(self._spinner_servers, interval=self.spinner_interval)
        self.spinner_badge.configure(text="● ON", fg=SUCCESS, bg="#10382f"); self.spinner_toggle.configure(text="●  SPINNER ACTIVE", bg=SUCCESS, fg=BG)
        self.spinner_countdown_label.configure(text=f"NEXT SWITCH  •  {self.spinner_interval:02d}s", fg=CYAN); self.side_status.set("Country Spinner is actively rotating verified routes")

    def _spinner_disconnect(self):
        self._spinner_rotating = True
        self.after(0, self._spinner_disconnect_ui)

    def _spinner_disconnect_ui(self):
        if self._spinner_rotating:
            EliteApp.disconnect(self)

    def _spinner_connect(self, candidates):
        self.after(0, lambda: self._spinner_connect_ui(candidates))

    def _spinner_connect_ui(self, candidates):
        if not candidates or not self.spinner_enabled:
            self._spinner_rotating = False
            return
        target = candidates[0]
        self.spinner_next = target
        self._connect([target])
        self._spinner_rotating = False
        self.spinner_current = target.get("country") or target.get("city") or target.get("host")
        self.spinner_history.append({"country": target.get("country"), "city": target.get("city"), "ip": (target.get("ips") or [target.get("ip") or target.get("host", "")])[0]})
        self.spinner_history = self.spinner_history[-12:]
        self.spinner_history_label.configure(text=f"Rotation history: {len(self.spinner_history)}")
        self._update_spinner_route(target); self._spinner_show_selected(target); self.spinner_countdown = self.spinner_interval; self._spinner_started = time.monotonic()

    def _spinner_show_selected(self, target):
        self._selected_server = target
        self._render_ip_inspector(target)

    def _update_spinner_route(self, target=None):
        if target:
            country = target.get("country") or "Unknown"; city = target.get("city") or "Any city"; flag = FLAGS.get(country, "◈")
            self.spinner_current_label.configure(text=f"CURRENT  {flag}  {country}  •  {city}")
        if self.spinner_next and self.spinner_next is not target:
            country = self.spinner_next.get("country") or "AUTO"; city = self.spinner_next.get("city") or "Any city"
            self.spinner_next_label.configure(text=f"NEXT  {FLAGS.get(country, '◈')}  {country}  •  {city}")
        else:
            self.spinner_next_label.configure(text="NEXT  •  AUTO")

    def _spinner_tick(self):
        try:
            if self.spinner_enabled and self._spinner_started:
                elapsed = time.monotonic() - self._spinner_started; remaining = max(0, self.spinner_interval - int(elapsed))
                self.spinner_countdown_label.configure(text=f"NEXT SWITCH  •  {remaining:02d}s  •  VERIFIED ROUTE ROTATION", fg=CYAN if remaining > 1 else WARNING)
            self.after(250, self._spinner_tick)
        except tk.TclError:
            pass

    def _connect(self, candidates):
        super()._connect(candidates)
        if candidates and self.spinner_enabled:
            target = candidates[0]; self.spinner_current = target.get("country") or target.get("city"); self.spinner_next = None; self._update_spinner_route(target); self._spinner_show_selected(target)

    def disconnect(self):
        if self._spinner_rotating:
            EliteApp.disconnect(self)
            return
        self.country_spinner.disable(); self.spinner_enabled = False
        super().disconnect()
        try:
            self.spinner_badge.configure(text="OFF", fg=MUTED, bg=PANEL_2); self.spinner_toggle.configure(text="◉  ENABLE SPINNER", bg=ACCENT)
        except tk.TclError:
            pass

    def _build_spinner_panel(self):
        self.spinner_panel = self._card(self.content, bg=SURFACE, accent=True, glow=False)
        self.spinner_panel.pack(fill="x", padx=30, pady=(0, 10), before=self.command)
        left = tk.Frame(self.spinner_panel, bg=SURFACE); left.pack(side="left", fill="x", expand=True, padx=18, pady=12)
        title_row = tk.Frame(left, bg=SURFACE); title_row.pack(fill="x")
        tk.Label(title_row, text="◌  COUNTRY SPINNER", bg=SURFACE, fg=CYAN, font=(FONT, 9, "bold")).pack(side="left")
        self.spinner_badge = tk.Label(title_row, text="OFF", bg=PANEL_2, fg=MUTED, padx=9, pady=4, font=(FONT, 7, "bold"), highlightthickness=1, highlightbackground=BORDER_HI)
        self.spinner_badge.pack(side="left", padx=8)
        tk.Label(left, text="Automatically roam across verified countries, cities and IP routes.", bg=SURFACE, fg=MUTED, font=(FONT, 8)).pack(anchor="w", pady=(4, 0))
        route = tk.Frame(self.spinner_panel, bg=PANEL_2, highlightthickness=1, highlightbackground=BORDER_HI); route.pack(side="left", padx=8, pady=10)
        self.spinner_current_label = tk.Label(route, text="CURRENT  •  —", bg=PANEL_2, fg=TEXT, font=(FONT, 8, "bold"), padx=10, pady=7); self.spinner_current_label.pack(side="left")
        tk.Label(route, text="→", bg=PANEL_2, fg=ACCENT_2, font=(FONT, 14, "bold")).pack(side="left")
        self.spinner_next_label = tk.Label(route, text="NEXT  •  AUTO", bg=PANEL_2, fg=ACCENT_2, font=(FONT, 8, "bold"), padx=10, pady=7); self.spinner_next_label.pack(side="left")
        controls = tk.Frame(self.spinner_panel, bg=SURFACE); controls.pack(side="right", padx=14, pady=10)
        tk.Label(controls, text="ROTATE EVERY", bg=SURFACE, fg=MUTED, font=(FONT, 7, "bold")).pack(side="left", padx=(0, 5))
        self.spinner_interval_var = tk.StringVar(value="3 seconds")
        self.spinner_interval_combo = ttk.Combobox(controls, textvariable=self.spinner_interval_var, state="readonly", width=11, values=("3 seconds", "10 seconds", "30 seconds", "60 seconds")); self.spinner_interval_combo.pack(side="left", padx=4); self.spinner_interval_combo.bind("<<ComboboxSelected>>", self._spinner_interval_changed)
        self.spinner_toggle = tk.Button(controls, text="◉  ENABLE SPINNER", command=self.toggle_spinner, bg=ACCENT, fg="white", activebackground=ACCENT_2, activeforeground="white", relief="flat", bd=0, cursor="hand2", font=(FONT, 9, "bold"), padx=13, pady=8, highlightthickness=1, highlightbackground=BORDER_HI); self.spinner_toggle.pack(side="left", padx=(8, 0))
        bottom = tk.Frame(self.spinner_panel, bg=SURFACE); bottom.pack(fill="x", padx=18, pady=(0, 11))
        self.spinner_countdown_label = tk.Label(bottom, text="NEXT SWITCH  •  STANDBY", bg=SURFACE, fg=MUTED, font=(FONT, 7, "bold")); self.spinner_countdown_label.pack(side="left")
        self.spinner_history_label = tk.Label(bottom, text="Rotation history: 0", bg=SURFACE, fg=MUTED, font=(FONT, 7)); self.spinner_history_label.pack(side="right")


# Install the live connection progress layer after the concrete spinner App class exists.
install_connection_progress(App)


if __name__ == "__main__":
    App().mainloop()
