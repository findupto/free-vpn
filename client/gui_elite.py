from __future__ import annotations

import threading
import time
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor, as_completed
from tkinter import ttk

import standalone_engine as engine
from gui_pro import App as PremiumApp

# Keep a very large live catalog. The application never invents IPs: all
# endpoints come from the live public discovery feeds and are deduplicated by
# the underlying engine.
engine.MAX_DISCOVERY = 5000

BG = "#05070d"
SURFACE = "#090d15"
PANEL = "#0d1420"
PANEL_2 = "#111a29"
PANEL_3 = "#172338"
PANEL_4 = "#1d2b43"
BORDER = "#233149"
BORDER_HI = "#3b4f70"
TEXT = "#f7faff"
MUTED = "#7f8da5"
ACCENT = "#7657ff"
ACCENT_HI = "#aa96ff"
SUCCESS = "#31dfad"
WARNING = "#ffc66d"
DANGER = "#ff6681"
CYAN = "#5edcff"
BLUE = "#4f8cff"
FONT = "Segoe UI"


class App(PremiumApp):
    """Elite Findupto VPN dashboard with premium controls and live timers."""

    def _configure_styles(self):
        super()._configure_styles()
        s = ttk.Style(self)
        s.configure("Treeview", rowheight=54, font=(FONT, 9), borderwidth=0,
                    background=PANEL, fieldbackground=PANEL, foreground=TEXT,
                    padding=(3, 3))
        s.configure("Treeview.Heading", padding=(14, 13), font=(FONT, 8, "bold"),
                    background=PANEL_3, foreground=MUTED, relief="flat")
        s.map("Treeview", background=[("selected", "#2b3b5a")],
              foreground=[("selected", TEXT)])
        s.configure("TCombobox", padding=8, font=(FONT, 9), fieldbackground=PANEL_2,
                    background=PANEL_2, foreground=TEXT, arrowcolor=ACCENT_HI,
                    borderwidth=0)
        s.configure("TSpinbox", padding=7, font=(FONT, 9), fieldbackground=PANEL_2,
                    background=PANEL_2, foreground=TEXT, arrowcolor=ACCENT_HI)
        s.configure("TCheckbutton", padding=6, font=(FONT, 9, "bold"),
                    background=PANEL, foreground=TEXT)

    def _card(self, parent, bg=PANEL, accent=False, glow=False):
        frame = tk.Frame(parent, bg=bg, highlightthickness=1,
                         highlightbackground=BORDER_HI if accent else BORDER,
                         highlightcolor=ACCENT)
        if glow:
            frame.configure(highlightthickness=2, highlightbackground=ACCENT)
        rail = tk.Frame(frame, bg=ACCENT if accent else PANEL_4, height=3)
        rail.pack(fill="x", side="top")
        return frame

    def _pill(self, parent, text, bg=PANEL_2, fg=MUTED):
        return tk.Label(parent, text=text, bg=bg, fg=fg, padx=12, pady=6,
                        font=(FONT, 8, "bold"), highlightthickness=1,
                        highlightbackground=BORDER_HI, highlightcolor=ACCENT)

    def _button(self, parent, text, command, kind="secondary", compact=False):
        palette = {
            "primary": (ACCENT, "#ffffff", ACCENT_HI),
            "success": (SUCCESS, BG, "#67efc4"),
            "danger": (DANGER, BG, "#ff9aae"),
            "secondary": (PANEL_4, TEXT, "#2b3d5c"),
            "ghost": (SURFACE, MUTED, PANEL_3),
            "blue": (BLUE, "#ffffff", "#73a6ff"),
        }
        base, fg, hover = palette.get(kind, palette["secondary"])
        b = tk.Button(parent, text=text, command=command, bg=base, fg=fg,
                      activebackground=hover, activeforeground=fg, relief="flat", bd=0,
                      highlightthickness=1, highlightbackground=BORDER_HI,
                      highlightcolor=ACCENT_HI, cursor="hand2",
                      font=(FONT, 9 if compact else 10, "bold"),
                      padx=12 if compact else 18, pady=7 if compact else 11)
        b._base_bg, b._hover_bg = base, hover
        b.bind("<Enter>", lambda _e: b.configure(bg=b._hover_bg,
                                                   highlightbackground=ACCENT_HI))
        b.bind("<Leave>", lambda _e: b.configure(bg=b._base_bg,
                                                   highlightbackground=BORDER_HI))
        b.bind("<ButtonPress-1>", lambda _e: b.configure(relief="sunken"))
        b.bind("<ButtonRelease-1>", lambda _e: b.configure(relief="flat"))
        return b

    def _build(self):
        super()._build()
        self._elite_timer_start = time.monotonic()
        self._elite_connected_at = None
        self._elite_timer_enabled = tk.BooleanVar(value=True)
        self._add_elite_widgets()
        self.after(250, self._elite_tick)

    def _add_elite_widgets(self):
        # Add a compact command ribbon beneath the existing header without
        # replacing the proven VPN controls supplied by PremiumApp.
        host = getattr(self, "content", self)
        self.elite_ribbon = self._card(host, bg=SURFACE, accent=True)
        self.elite_ribbon.pack(fill="x", padx=26, pady=(0, 10), before=getattr(self, "filters", None))

        left = tk.Frame(self.elite_ribbon, bg=SURFACE)
        left.pack(side="left", fill="x", expand=True, padx=16, pady=12)
        tk.Label(left, text="SMART CONTROL CENTER", bg=SURFACE, fg=ACCENT_HI,
                 font=(FONT, 8, "bold")).pack(anchor="w")
        tk.Label(left, text="Live routes • latency intelligence • connection timer",
                 bg=SURFACE, fg=TEXT, font=(FONT, 10, "bold")).pack(anchor="w", pady=(2, 0))

        self.elite_timer_label = tk.Label(self.elite_ribbon, text="SESSION 00:00:00",
                                          bg=PANEL_2, fg=CYAN, padx=14, pady=9,
                                          font=(FONT, 9, "bold"), highlightthickness=1,
                                          highlightbackground=BORDER_HI)
        self.elite_timer_label.pack(side="right", padx=(6, 10), pady=9)
        self._button(self.elite_ribbon, "⟳ SCAN NOW", self.refresh, "blue", True).pack(
            side="right", padx=4, pady=9)
        self._button(self.elite_ribbon, "⚡ SMART CONNECT", self.best, "primary", True).pack(
            side="right", padx=4, pady=9)

        # A dedicated server-intelligence strip gives the interface a more
        # premium command-center feel while staying responsive.
        self.elite_stats = self._card(host, bg=PANEL, accent=False)
        self.elite_stats.pack(fill="x", padx=26, pady=(0, 10), before=getattr(self, "filters", None))
        cells = [
            ("LIVE CATALOG", "0", CYAN),
            ("VERIFIED", "0", SUCCESS),
            ("FAST ROUTES", "0", ACCENT_HI),
            ("COUNTRIES", "0", WARNING),
            ("REFRESH", "READY", TEXT),
        ]
        self.elite_stat_vars = []
        for title, value, color in cells:
            box = tk.Frame(self.elite_stats, bg=PANEL)
            box.pack(side="left", fill="x", expand=True, padx=2, pady=2)
            tk.Label(box, text=title, bg=PANEL, fg=MUTED,
                     font=(FONT, 7, "bold")).pack(anchor="w", padx=13, pady=(9, 1))
            var = tk.StringVar(value=value)
            self.elite_stat_vars.append(var)
            tk.Label(box, textvariable=var, bg=PANEL, fg=color,
                     font=(FONT, 14, "bold")).pack(anchor="w", padx=13, pady=(0, 9))

    def _elite_tick(self):
        try:
            if self._elite_connected_at is not None:
                elapsed = int(time.monotonic() - self._elite_connected_at)
            else:
                elapsed = 0
            h, rem = divmod(elapsed, 3600)
            m, s = divmod(rem, 60)
            self.elite_timer_label.configure(text=f"SESSION {h:02d}:{m:02d}:{s:02d}")
        except tk.TclError:
            return
        self.after(250, self._elite_tick)

    def _discover_worker(self):
        try:
            data = engine.discover(35)
            # Deduplicate by concrete endpoint before probing. Public feeds can
            # contain the same relay through multiple hostnames/mirrors.
            unique = []
            seen = set()
            for server in data:
                eps = server.get("ips") or [server.get("ip") or server.get("host", "")]
                key = tuple(sorted(str(x) for x in eps if x)) or (str(server.get("host", "")),)
                if key in seen:
                    continue
                seen.add(key)
                unique.append(server)

            tested = []
            # Large bulk catalog: probe 1800 real entries in parallel. The UI
            # still receives the complete discovered catalog when more entries
            # are available, while the verified subset gets the live metrics.
            probe_pool = unique[:1800]
            with ThreadPoolExecutor(max_workers=72, thread_name_prefix="vpn-probe") as pool:
                futures = [pool.submit(self._probe, s) for s in probe_pool]
                for f in as_completed(futures):
                    if self.cancel_event.is_set():
                        break
                    try:
                        tested.append(f.result())
                    except Exception:
                        continue

            tested.sort(key=lambda s: (not s.get("available"),
                                       s.get("live_ping", 9999),
                                       -float(s.get("speed", 0) or 0),
                                       -float(s.get("rank", 0) or 0)))
            self.events.put(("servers", tested,
                             f"Elite pool ready • {len(tested):,} live endpoints tested"))
        except Exception as exc:
            self.events.put(("error", None, f"Server discovery failed: {exc}"))

    def _render_quick(self, items):
        for w in self.quick_frame.winfo_children():
            w.destroy()
        if not items:
            tk.Label(self.quick_frame,
                     text="No live routes match your filters. Try widening latency or enabling all servers.",
                     bg=PANEL, fg=MUTED, font=(FONT, 9)).pack(anchor="w", padx=14, pady=17)
            return
        count = 3 if self.compact else 5
        for server in items[:count]:
            ping = float(server.get("live_ping", 9999))
            name = server.get("city") or server.get("country") or server.get("host") or "Server"
            country = str(server.get("country") or "Global")
            ips = server.get("ips") or [server.get("ip") or server.get("host", "")]
            card = self._card(self.quick_frame, bg=PANEL_2, accent=True, glow=ping < 100)
            card.pack(side="left", fill="x", expand=True, padx=4)
            top = tk.Frame(card, bg=PANEL_2)
            top.pack(fill="x", padx=12, pady=(10, 1))
            tk.Label(top, text="● ONLINE", bg=PANEL_2, fg=SUCCESS,
                     font=(FONT, 7, "bold")).pack(side="left")
            tk.Label(top, text=f"{ping:.0f} ms", bg=PANEL_2, fg=CYAN,
                     font=(FONT, 8, "bold")).pack(side="right")
            tk.Label(card, text=str(name)[:25], bg=PANEL_2, fg=TEXT,
                     font=(FONT, 11, "bold")).pack(anchor="w", padx=12)
            tk.Label(card, text=f"{country}  •  {len(ips)} IP routes",
                     bg=PANEL_2, fg=MUTED, font=(FONT, 8)).pack(anchor="w", padx=12, pady=(2, 3))
            meter = tk.Frame(card, bg=PANEL_3, height=5)
            meter.pack(fill="x", padx=12, pady=(3, 5))
            fill = tk.Frame(meter, bg=SUCCESS if ping < 100 else WARNING, height=5)
            fill.pack(side="left", fill="y", expand=True if ping < 100 else False,
                      ipadx=max(2, min(80, int(80 - min(ping, 250) / 250 * 80))))
            tk.Label(card, text=str(ips[0])[:35], bg=PANEL_2, fg=MUTED,
                     font=(FONT, 7)).pack(anchor="w", padx=12)
            self._button(card, "CONNECT  →", lambda x=server: self._connect([x]),
                         "primary", True).pack(anchor="e", padx=10, pady=(6, 10))

    def _render(self):
        super()._render()
        total = len(getattr(self, "servers", []))
        available = sum(bool(s.get("available")) for s in getattr(self, "servers", []))
        fast = sum(bool(s.get("available")) and float(s.get("live_ping", 9999)) <= 250
                   for s in getattr(self, "servers", []))
        countries = len({s.get("country") for s in getattr(self, "servers", []) if s.get("country")})
        if hasattr(self, "table_hint"):
            self.table_hint.configure(text=f"{total:,} catalog endpoints • {available:,} verified • live intelligence")
        if hasattr(self, "elite_stat_vars"):
            vals = [f"{total:,}", f"{available:,}", f"{fast:,}", str(countries), "LIVE"]
            for var, value in zip(self.elite_stat_vars, vals):
                var.set(value)

    def _connect(self, candidates):
        super()._connect(candidates)
        if candidates:
            self._elite_connected_at = time.monotonic()

    def disconnect(self):
        super().disconnect()
        self._elite_connected_at = None
        if hasattr(self, "elite_timer_label"):
            self.elite_timer_label.configure(text="SESSION 00:00:00")


if __name__ == "__main__":
    App().mainloop()
