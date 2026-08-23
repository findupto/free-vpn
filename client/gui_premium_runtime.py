"""Low-latency runtime for the premium Findupto VPN UI."""
from __future__ import annotations
import json, threading, time
from pathlib import Path
import standalone_engine as engine
from gui_premium import App as PremiumBase

class App(PremiumBase):
    def __init__(self):
        self._search_job=None; self._server_index=(); self._index_signature=None
        self._catalog_running=False; self._catalog_generation=0
        super().__init__(); self.after(0,self._start_catalog_refresh)

    def _pump(self): self._premium_pump()
    @staticmethod
    def _server_key(s): return " ".join(str(s.get(k) or "") for k in ("country","city","host","ip","source","kind")).casefold()
    def _rebuild_server_index(self,servers=None):
        servers=list(servers if servers is not None else (getattr(self,"servers",[]) or [])); sig=(len(servers),tuple(str(s.get("id") or s.get("host") or s.get("ip") or "") for s in servers))
        if sig==self._index_signature:return
        self._index_signature=sig; self._server_index=tuple((i,self._server_key(s),s) for i,s in enumerate(servers))
    def _schedule_render(self):
        if self._search_job:
            try:self.after_cancel(self._search_job)
            except Exception:pass
        self._search_job=self.after_idle(self._render)
    def _render(self):
        if not hasattr(self,"tree"):return
        self._rebuild_server_index(); q=str(self.search_var.get() or "").strip().casefold()
        def v(n,d="All"):
            x=getattr(self,n,None); return x.get() if hasattr(x,"get") else d
        country,city,source=v("country"),v("city"),v("source")
        fast=bool(getattr(self,"fast_only",None).get()) if hasattr(getattr(self,"fast_only",None),"get") else False
        avail=bool(getattr(self,"available_only",None).get()) if hasattr(getattr(self,"available_only",None),"get") else False
        try:mx=float(self.max_ping.get())
        except Exception:mx=250.0
        matches=[]
        for i,text,s in self._server_index:
            if q and q not in text:continue
            if country!="All" and str(s.get("country") or "Unknown")!=country:continue
            if city!="All" and str(s.get("city") or "Unknown")!=city:continue
            if source!="All" and str(s.get("source") or "Unknown")!=source:continue
            ping=float(s.get("live_ping",s.get("ping",9999)) or 9999); ok=bool(s.get("available"))
            if avail and not ok:continue
            if fast and (not ok or ping>mx):continue
            matches.append((i,s,ping))
        old=self.tree.get_children()
        if old:self.tree.delete(*old)
        for i,s,ping in matches[:500]:
            speed=float(s.get("speed") or 0); tag="fast" if bool(s.get("available")) and ping<180 else ("normal" if bool(s.get("available")) else "catalog")
            self.tree.insert("","end",iid=str(i),tags=(tag,),values=("☆",s.get("country") or "—",s.get("city") or "—",s.get("host") or s.get("ip") or "—","—" if ping>=9999 else f"{ping:.0f} ms",f"{speed:.1f} Mbps" if speed else "—"))
        if hasattr(self,"count"):self.count.configure(text=f"{len(matches):,} servers")
    @staticmethod
    def _stale_catalog():
        try:
            data=json.loads(Path(engine.CACHE).read_text(encoding="utf-8")); return [s for s in data.get("servers",[]) if isinstance(s,dict)]
        except Exception:return []
    def _start_catalog_refresh(self):
        if self._catalog_running:return
        try:cached=engine._cache_load()
        except Exception:cached=[]
        if not cached:cached=self._stale_catalog()
        if cached:
            self.servers=list(cached); self._index_signature=None; self._render()
            try:self.status.set(f"{len(cached):,} routes ready • refreshing")
            except Exception:pass
        self._catalog_generation+=1; gen=self._catalog_generation; self._catalog_running=True
        threading.Thread(target=self._catalog_worker,args=(gen,),daemon=True,name="findupto-catalog-refresh").start()
    def _catalog_worker(self,gen):
        t=time.monotonic()
        try:s=list(engine.discover(deadline=7.0) or []); self.after(0,self._catalog_ready,gen,s,time.monotonic()-t)
        except Exception as e:self.after(0,self._catalog_ready,gen,[],time.monotonic()-t,e)
        finally:self._catalog_running=False
    def _catalog_ready(self,gen,servers,elapsed,error=None):
        if gen!=self._catalog_generation:return
        if servers:
            self.servers=servers; self._index_signature=None; self._render()
            try:self.status.set(f"{len(servers):,} routes ready • updated in {elapsed:.1f}s")
            except Exception:pass
        elif not getattr(self,"servers",None):
            try:self.status.set("No routes received — provider/network unavailable")
            except Exception:pass
    def refresh(self):
        if not self._catalog_running:self._start_catalog_refresh()
    def _connect_fast(self):
        self._set_busy(True); servers=[s for s in (getattr(self,"servers",[]) or []) if isinstance(s,dict)]
        servers.sort(key=lambda s:(0 if s.get("available") else 1,float(s.get("live_ping",s.get("ping",9999)) or 9999),-float(s.get("speed",0) or 0),-float(s.get("rank",0) or 0)))
        if servers and hasattr(self,"_start_connection"):self._start_connection(servers[0]);return
        self._start_catalog_refresh(); self.after(200,self._connect_when_catalog_ready)
    def _connect_when_catalog_ready(self):
        if getattr(self,"servers",None):self._connect_fast()
        elif self._catalog_running:self.after(200,self._connect_when_catalog_ready)
        else:self._set_busy(False)
    def _premium_pump(self):
        super()._premium_pump()
        if getattr(self,"servers",None):self._rebuild_server_index()
