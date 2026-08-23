"""Low-latency runtime for the premium Findupto VPN UI.

The UI never performs provider discovery on the Tk main thread. A local catalog
is rendered immediately, while VPN Gate/VPNBook discovery runs in one background
worker and pushes the completed catalog back into the UI.
"""
from __future__ import annotations

import threading
import time

import standalone_engine as engine
from gui_premium import App as PremiumBase


class App(PremiumBase):
    """Premium UI with instant local search and asynchronous discovery."""

    def __init__(self):
        self._search_job = None
        self._server_index = ()
        self._index_signature = None
        self._catalog_lock = threading.Lock()
        self._catalog_running = False
        self._catalog_generation = 0
        super().__init__()
        # Do not make startup wait for a provider HTTP request. Populate the
        # UI from cache first, then fetch fresh data in the background.
        self.after(0, self._start_catalog_refresh)

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
        signature = (
            len(servers),
            tuple(str(s.get("id") or s.get("host") or s.get("ip") or "") for s in servers),
        )
        if signature == self._index_signature:
            return
        self._index_signature = signature
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
        country_var = getattr(self, "country", None)
        city_var = getattr(self, "city", None)
        source_var = getattr(self, "source", None)
        fast_var = getattr(self, "fast_only", None)
        avail_var = getattr(self, "available_only", None)
        country = country_var.get() if hasattr(country_var, "get") else "All"
        city = city_var.get() if hasattr(city_var, "get") else "All"
        source = source_var.get() if hasattr(source_var, "get") else "All"
        fast_only = bool(fast_var.get()) if hasattr(fast_var, "get") else False
        available_only = bool(avail_var.get()) if hasattr(avail_var, "get") else False
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
            matches.append((i, server, ping))

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

    def _start_catalog_refresh(self):
        """Render cache now and fetch providers once in a daemon worker."""
        if getattr(self, "_catalog_running", False):
            return
        # Cache is intentionally allowed to win the first paint. The UI is
        # useful immediately even when the network is slow or unavailable.
        try:
            cached = engine._cache_load()
        except Exception:
            cached = []
        if cached:
            self.servers = list(cached)
            self._index_signature = None
            self._render()
            try:
                self.status.set(f"{len(cached):,} routes cached • refreshing in background")
            except Exception:
                pass
        self._catalog_generation += 1
        generation = self._catalog_generation
        with self._catalog_lock:
            self._catalog_running = True
        threading.Thread(
            target=self._catalog_worker,
            args=(generation,),
            daemon=True,
            name="findupto-catalog-refresh",
        ).start()

    def _catalog_worker(self, generation: int):
        started = time.monotonic()
        try:
            # Three sources are already parallelized by vpn_engine.discover().
            # Keep the deadline short enough that a bad provider cannot freeze
            # the product, while allowing a cold VPN Gate response to complete.
            servers = engine.discover(deadline=7.0)
            servers = list(servers or [])
            self.after(0, self._catalog_ready, generation, servers, None, time.monotonic() - started)
        except Exception as exc:
            self.after(0, self._catalog_ready, generation, [], exc, time.monotonic() - started)
        finally:
            with self._catalog_lock:
                self._catalog_running = False

    def _catalog_ready(self, generation, servers, error, elapsed):
        if generation != self._catalog_generation:
            return
        if servers:
            self.servers = servers
            self._index_signature = None
            self._render()
            try:
                self.status.set(f"{len(servers):,} routes ready • updated in {elapsed:.1f}s")
                if hasattr(self, "speed_status"):
                    self.speed_status.set("Live route catalog")
            except Exception:
                pass
        elif not getattr(self, "servers", None):
            try:
                self.status.set("No route catalog available • check network access")
                if hasattr(self, "speed_status"):
                    self.speed_status.set("No servers received")
            except Exception:
                pass

    def refresh(self):
        """Refresh without blocking Tk and without duplicate scans."""
        if getattr(self, "_catalog_running", False):
            return
        self._set_busy(True)
        self._start_catalog_refresh()
        # Scanning is background work; do not leave the UI permanently disabled.
        self.after(150, lambda: self._set_busy(False) if not getattr(self, "busy", False) else None)

    def _connect_fast(self):
        """Connect immediately from the best known local endpoint."""
        self._set_busy(True)
        servers = [s for s in (getattr(self, "servers", []) or []) if isinstance(s, dict)]
        servers.sort(key=lambda s: (
            0 if s.get("available") else 1,
            float(s.get("live_ping", s.get("ping", 9999)) or 9999),
            -float(s.get("speed", 0) or 0),
            -float(s.get("rank", 0) or 0),
        ))
        if servers and hasattr(self, "_start_connection"):
            self._start_connection(servers[0])
            return
        # Cold start: begin catalog asynchronously; connection will not block
        # the UI. The user can retry immediately once the first route arrives.
        self._start_catalog_refresh()
        self.after(250, self._connect_when_catalog_ready)

    def _connect_when_catalog_ready(self):
        if getattr(self, "servers", None):
            self._connect_fast()
            return
        if getattr(self, "_catalog_running", False):
            self.after(250, self._connect_when_catalog_ready)
            return
        self._set_busy(False)

    def _premium_pump(self):
        super()._premium_pump()
        if getattr(self, "servers", None):
            self._rebuild_server_index()
