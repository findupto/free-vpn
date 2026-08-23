"""Fast runtime adapter for the premium Findupto VPN UI.

Keeps the existing UI/engine but moves server search/filtering entirely into an
in-memory index and makes Fastest prefer an already-known good endpoint before
starting discovery or recovery work.
"""
from __future__ import annotations

import time

from gui_premium import App as PremiumBase


class App(PremiumBase):
    """Premium UI with low-latency search and connection shortcuts."""

    def __init__(self):
        self._search_job = None
        self._server_index = ()
        self._index_signature = None
        super().__init__()

    def _pump(self):
        self._premium_pump()

    @staticmethod
    def _server_key(server: dict) -> str:
        return " ".join(
            str(server.get(key) or "")
            for key in ("country", "city", "host", "ip", "source", "kind")
        ).casefold()

    def _rebuild_server_index(self, servers=None):
        servers = list(servers if servers is not None else (getattr(self, "servers", []) or []))
        signature = (len(servers), id(getattr(self, "servers", None)), tuple(
            str(s.get("id") or s.get("host") or s.get("ip") or "") for s in servers[:12]
        ))
        if signature == self._index_signature and self._server_index:
            return
        self._index_signature = signature
        # Precompute the searchable text once. Typing in the search box no
        # longer rebuilds strings for every server on every keystroke.
        self._server_index = tuple((i, self._server_key(s), s) for i, s in enumerate(servers))

    def _schedule_render(self):
        if self._search_job is not None:
            try:
                self.after_cancel(self._search_job)
            except Exception:
                pass
        self._search_job = self.after_idle(self._render)

    def _render(self):
        if not hasattr(self, "tree"):
            return
        self._rebuild_server_index()
        query = str(self.search_var.get() or "").strip().casefold()
        country = str(getattr(self, "country", "").get() if hasattr(getattr(self, "country", None), "get") else "All")
        city = str(getattr(self, "city", "").get() if hasattr(getattr(self, "city", None), "get") else "All")
        source = str(getattr(self, "source", "").get() if hasattr(getattr(self, "source", None), "get") else "All")
        fast_only = bool(getattr(self, "fast_only", None).get()) if hasattr(self, "fast_only") else False
        available_only = bool(getattr(self, "available_only", None).get()) if hasattr(self, "available_only") else False
        try:
            max_ping = float(self.max_ping.get())
        except Exception:
            max_ping = 250.0

        matches = []
        for i, text, server in self._server_index:
            if query and query not in text:
                continue
            if country != "All" and str(server.get("country") or "Unknown") != country:
                continue
            if city != "All" and str(server.get("city") or "Unknown") != city:
                continue
            if source != "All" and str(server.get("source") or "Unknown") != source:
                continue
            ping = float(server.get("live_ping", server.get("ping", 9999)) or 9999)
            available = bool(server.get("available"))
            if available_only and not available:
                continue
            if fast_only and (not available or ping > max_ping):
                continue
            if ping < max_ping or not fast_only:
                matches.append((i, server, ping))

        # Treeview is the expensive part, not the filtering itself. Render a
        # generous window and avoid touching rows when the query is unchanged.
        visible = matches[:500]
        current = self.tree.get_children()
        if current:
            self.tree.delete(*current)
        for i, server, ping in visible:
            speed = float(server.get("speed") or 0)
            fast = bool(server.get("available")) and ping < 180
            tag = "fast" if fast else ("normal" if bool(server.get("available")) else "catalog")
            self.tree.insert(
                "", "end", iid=str(i), tags=(tag,),
                values=(
                    "☆",
                    server.get("country") or "—",
                    server.get("city") or "—",
                    server.get("host") or server.get("ip") or "—",
                    "—" if ping >= 9999 else f"{ping:.0f} ms",
                    f"{speed:.1f} Mbps" if speed else "—",
                ),
            )
        if hasattr(self, "count"):
            self.count.configure(text=f"{len(matches):,} servers")

    def _connect_fast(self):
        """Connect immediately using the best known local endpoint.

        Discovery is a recovery mechanism, not a prerequisite for every click.
        """
        self._set_busy(True)
        servers = list(getattr(self, "servers", []) or [])
        candidates = [s for s in servers if isinstance(s, dict)]
        candidates.sort(key=lambda s: (
            0 if s.get("available") else 1,
            float(s.get("live_ping", s.get("ping", 9999)) or 9999),
            -float(s.get("speed", 0) or 0),
            -float(s.get("rank", 0) or 0),
        ))
        if candidates and hasattr(self, "_start_connection"):
            self._start_connection(candidates[0])
            return
        # No catalog yet: use the engine's normal fastest-server path. This is
        # only the cold-start fallback.
        self.best()

    def _premium_pump(self):
        before = len(getattr(self, "servers", []) or [])
        super()._premium_pump()
        after = len(getattr(self, "servers", []) or [])
        if before != after:
            self._index_signature = None
