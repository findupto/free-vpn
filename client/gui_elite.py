from __future__ import annotations

import threading
import time
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor, as_completed

import standalone_engine as engine
from gui_pro import App as PremiumApp

BG = "#05070c"
SURFACE = "#0a0f17"
PANEL = "#0f1722"
PANEL_2 = "#141e2b"
PANEL_3 = "#1b2738"
BORDER = "#263448"
BORDER_HI = "#435673"
TEXT = "#f8fbff"
MUTED = "#8290a6"
ACCENT = "#7357ff"
ACCENT_HI = "#a18eff"
SUCCESS = "#31ddb0"
WARNING = "#ffc66e"
DANGER = "#ff6680"
CYAN = "#60dcff"
FONT = "Segoe UI"


class App(PremiumApp):
    """Refined Findupto dashboard with premium controls and a much larger live pool."""

    def _configure_styles(self):
        super()._configure_styles()
        s = self.ttk_style if hasattr(self, "ttk_style") else None
        if s is None:
            from tkinter import ttk
            s = ttk.Style(self)
        s.configure("Treeview", rowheight=50, font=(FONT, 9), borderwidth=0,
                    background=PANEL, fieldbackground=PANEL, foreground=TEXT)
        s.configure("Treeview.Heading", padding=(12, 11), font=(FONT, 8, "bold"),
                    background=PANEL_2, foreground=MUTED, relief="flat")
        s.map("Treeview", background=[("selected", "#303e58")], foreground=[("selected", TEXT)])
        s.configure("TCombobox", padding=6, font=(FONT, 9), fieldbackground=PANEL_2,
                    background=PANEL_2, foreground=TEXT, arrowcolor=ACCENT_HI)
        s.configure("TSpinbox", padding=5, font=(FONT, 9), fieldbackground=PANEL_2,
                    background=PANEL_2, foreground=TEXT, arrowcolor=ACCENT_HI)
        s.configure("TCheckbutton", padding=5, font=(FONT, 9, "bold"), background=PANEL,
                    foreground=TEXT)

    def _card(self, parent, bg=PANEL, accent=False):
        frame = tk.Frame(parent, bg=bg, highlightthickness=1,
                         highlightbackground=BORDER_HI if accent else BORDER,
                         highlightcolor=ACCENT)
        # A very thin inset rail gives every surface a polished, layered edge.
        rail = tk.Frame(frame, bg=ACCENT if accent else PANEL_3, height=2)
        rail.pack(fill="x", side="top")
        return frame

    def _pill(self, parent, text, bg=PANEL_2, fg=MUTED):
        return tk.Label(parent, text=text, bg=bg, fg=fg, padx=12, pady=6,
                        font=(FONT, 8, "bold"), highlightthickness=1,
                        highlightbackground=BORDER_HI, highlightcolor=ACCENT)

    def _button(self, parent, text, command, kind="secondary", compact=False):
        palette = {
            "primary": (ACCENT, "#ffffff", ACCENT_HI),
            "success": (SUCCESS, BG, "#63edc2"),
            "danger": (DANGER, BG, "#ff91a4"),
            "secondary": (PANEL_3, TEXT, "#2a3b53"),
            "ghost": (SURFACE, MUTED, PANEL_2),
        }
        base, fg, hover = palette.get(kind, palette["secondary"])
        b = tk.Button(parent, text=text, command=command, bg=base, fg=fg,
                      activebackground=hover, activeforeground=fg, relief="flat", bd=0,
                      highlightthickness=1, highlightbackground=BORDER_HI,
                      highlightcolor=ACCENT, cursor="hand2",
                      font=(FONT, 9 if compact else 10, "bold"),
                      padx=12 if compact else 17, pady=7 if compact else 10)
        b._base_bg, b._hover_bg = base, hover
        b.bind("<Enter>", lambda _e: b.configure(bg=b._hover_bg, highlightbackground=ACCENT_HI))
        b.bind("<Leave>", lambda _e: b.configure(bg=b._base_bg, highlightbackground=BORDER_HI))
        b.bind("<ButtonPress-1>", lambda _e: b.configure(relief="sunken"))
        b.bind("<ButtonRelease-1>", lambda _e: b.configure(relief="flat"))
        return b

    def _discover_worker(self):
        """Pull the large VPN Gate catalog, then concurrently verify a broad slice."""
        try:
            data = engine.discover(25)
            tested = []
            # VPN Gate publishes thousands of volunteer relays; keep a broad
            # working set instead of truncating the UI to a few hundred.
            with ThreadPoolExecutor(max_workers=64, thread_name_prefix="vpn-probe") as pool:
                futures = [pool.submit(self._probe, s) for s in data[:1000]]
                for f in as_completed(futures):
                    if self.cancel_event.is_set():
                        break
                    try:
                        tested.append(f.result())
                    except Exception:
                        continue
            tested.sort(key=lambda s: (not s.get("available"), s.get("live_ping", 9999),
                                       -float(s.get("speed", 0) or 0), -float(s.get("rank", 0) or 0)))
            self.events.put(("servers", tested, f"Large live pool ready • {len(tested)} endpoints tested"))
        except Exception as exc:
            self.events.put(("error", None, f"Server discovery failed: {exc}"))

    def _render_quick(self, items):
        # More breathing room and compact metric chips in the Fast Lane.
        for w in self.quick_frame.winfo_children():
            w.destroy()
        if not items:
            tk.Label(self.quick_frame, text="No matching live servers. Widen MAX PING or disable Fast.",
                     bg=PANEL, fg=MUTED, font=(FONT, 9)).pack(anchor="w", padx=12, pady=16)
            return
        count = 3 if self.compact else 5
        for server in items[:count]:
            ping = float(server.get("live_ping", 9999))
            name = server.get("city") or server.get("country") or server.get("host") or "Server"
            card = self._card(self.quick_frame, bg=PANEL_2, accent=True)
            card.pack(side="left", fill="x", expand=True, padx=4)
            tk.Label(card, text="●  LIVE ROUTE", bg=PANEL_2, fg=SUCCESS,
                     font=(FONT, 7, "bold")).pack(anchor="w", padx=12, pady=(9, 1))
            tk.Label(card, text=str(name)[:22], bg=PANEL_2, fg=TEXT,
                     font=(FONT, 10, "bold")).pack(anchor="w", padx=12)
            metrics = tk.Frame(card, bg=PANEL_2)
            metrics.pack(fill="x", padx=12, pady=(4, 2))
            tk.Label(metrics, text=f"{ping:.0f} ms", bg=PANEL_2, fg=CYAN,
                     font=(FONT, 9, "bold")).pack(side="left")
            tk.Label(metrics, text=f"  {float(server.get('speed', 0) or 0):.1f} Mbps",
                     bg=PANEL_2, fg=MUTED, font=(FONT, 8)).pack(side="left")
            b = self._button(card, "CONNECT  →", lambda x=server: self._connect([x]),
                             "primary", compact=True)
            b.pack(anchor="e", padx=10, pady=(5, 10))

    def _render(self):
        super()._render()
        if hasattr(self, "table_hint"):
            total = len(getattr(self, "servers", []))
            self.table_hint.configure(text=f"{total:,} catalog endpoints • live checks")


if __name__ == "__main__":
    App().mainloop()
