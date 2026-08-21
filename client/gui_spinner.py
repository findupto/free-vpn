from __future__ import annotations

import time
import tkinter as tk
from tkinter import ttk

from country_spinner import CountrySpinner
from gui_elite import App as EliteApp, BG, SURFACE, PANEL, PANEL_2, BORDER, BORDER_HI, TEXT, MUTED, ACCENT, ACCENT_2, SUCCESS, WARNING, CYAN, FONT

FLAGS = {
    "Denmark": "🇩🇰", "United States": "🇺🇸", "Japan": "🇯🇵", "Germany": "🇩🇪",
    "United Kingdom": "🇬🇧", "Canada": "🇨🇦", "France": "🇫🇷", "Netherlands": "🇳🇱",
    "Singapore": "🇸🇬", "Australia": "🇦🇺", "Switzerland": "🇨🇭", "Sweden": "🇸🇪",
    "Norway": "🇳🇴", "Finland": "🇫🇮", "Poland": "🇵🇱", "Brazil": "🇧🇷",
    "India": "🇮🇳", "Hong Kong": "🇭🇰", "Korea Republic of": "🇰🇷", "Taiwan": "🇹🇼",
}


class App(EliteApp):
    """Elite dashboard with premium automatic country/IP rotation."""

    def __init__(self):
        self.spinner_enabled = False
        self.spinner_interval = 3
        self.spinner_countdown = 3
        self.spinner_current = None
        self.spinner_next = None
        self.spinner_history = []
        self._spinner_started = None
        self._spinner_rotating = False
        self.country_spinner = CountrySpinner(self._spinner_connect, self._spinner_disconnect)
        super().__init__()

    def _build_premium_content(self):
        super()._build_premium_content()
        self._build_spinner_panel()
        self._spinner_tick()

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
        self._update_spinner_route(target); self.spinner_countdown = self.spinner_interval; self._spinner_started = time.monotonic()

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
            target = candidates[0]; self.spinner_current = target.get("country") or target.get("city"); self.spinner_next = None; self._update_spinner_route(target)

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


if __name__ == "__main__":
    App().mainloop()
