from __future__ import annotations

"""Single application entry point for Findupto VPN."""
import ctypes, os, subprocess, sys, threading, tkinter as tk
from pathlib import Path
from privacy import redact_log_message
from session_controller import SessionController
VERSION="14.4.0"

def _is_admin():
    if os.name!="nt": return True
    try: return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception: return False

def _start_elevated():
    if os.name!="nt" or _is_admin(): return True
    script=str(Path(__file__).resolve()); result=ctypes.windll.shell32.ShellExecuteW(None,"runas",sys.executable,subprocess.list2cmdline([script]),str(Path(script).parent),1)
    if result<=32:
        try: ctypes.windll.user32.MessageBoxW(None,"Administrator permission is required for the VPN tunnel.","Findupto VPN",0x10)
        except Exception: pass
        return False
    return True

def _show_startup_error(exc):
    if os.name!="nt": return
    try:
        safe=redact_log_message(f"{type(exc).__name__}: {exc}"); ctypes.windll.user32.MessageBoxW(None,f"Findupto VPN could not start.\n\n{safe}","Findupto VPN",0x10)
    except Exception: pass

def _auth_failed(exc):
    text=str(exc).lower(); return any(x in text for x in ("authentication failed","auth_failed","auth failed","verification failed"))

def _refresh_candidates(engine,selected,existing,limit=5):
    seen={str(selected.get("id") or selected.get("host") or selected.get("ip") or "").lower()}; out=[]
    for item in existing:
        key=str(item.get("id") or item.get("host") or item.get("ip") or "").lower()
        if key and key not in seen: seen.add(key); out.append(item)
        if len(out)>=limit: break
    return out

def _fresh_recovery_candidates(engine,selected,existing,limit=14):
    out=_refresh_candidates(engine,selected,existing,limit)
    if len(out)>=limit: return out
    try:
        cache=getattr(engine,"CACHE",None)
        if cache: Path(cache).unlink(missing_ok=True)
        import smart_bootstrap
        smart_bootstrap.controller.blocked.clear()
        seen={str(selected.get("id") or selected.get("host") or selected.get("ip") or "").lower()}; seen.update(str(x.get("id") or x.get("host") or x.get("ip") or "").lower() for x in out)
        for item in engine.discover(deadline=10):
            key=str(item.get("id") or item.get("host") or item.get("ip") or "").lower()
            if key and key not in seen: seen.add(key); out.append(item)
            if len(out)>=limit: break
    except Exception as exc: engine.log(f"FRESH RECOVERY DISCOVERY ERROR={type(exc).__name__}: {exc}")
    return out

def _install_gui_compatibility():
    from gui import App as LegacyApp
    import standalone_engine as engine
    from browser_integration import open_secure_browser
    if getattr(LegacyApp,"_findupto_runtime_wired",False): return
    def controller(self):
        c=getattr(self,"_session_controller",None)
        if c is None: c=SessionController(); self._session_controller=c
        return c
    def connect_verified(self,server,previous_ip=None):
        process,work,logfile=engine.connect(server,total_deadline=22)
        try: vpn_ip=engine.verify_tunnel(previous_ip=previous_ip,timeout=8)
        except Exception: controller(self).terminate_process(process); raise
        return process,work,logfile,vpn_ip
    def start_connection(self,selected):
        c=controller(self)
        if not c.begin_connect(selected): self.events.put(("error",None,"A VPN operation is already in progress.")); return
        def worker():
            previous=None; attempted=[]; last=None
            try:
                try: previous=engine.public_ip(timeout=4)
                except Exception: pass
                initial=[selected]+_refresh_candidates(engine,selected,getattr(self,"servers",[]),5)
                self.events.put(("status",None,"Connecting to the selected verified route…"))
                for i,server in enumerate(initial,1):
                    host=str(server.get("host") or server.get("ip") or "VPN server"); attempted.append(host)
                    try:
                        self.events.put(("status",None,f"Connecting • {server.get('country','VPN')} • {i}/{len(initial)}…")); process,work,logfile,vpn_ip=connect_verified(self,server,previous)
                        self.process=process; self.tmp=work; self.current_log=logfile; self.selected_server=server; c.mark_connected(process,vpn_ip); self.events.put(("connected",None,f"CONNECTED • {server.get('country','VPN')} • exit IP {vpn_ip}")); return
                    except Exception as exc: last=exc; c.mark_error(); engine.log(f"GUI ENDPOINT FAILED host={host} attempt={i} reason={type(exc).__name__}: {exc}")
                recovery=_fresh_recovery_candidates(engine,selected,getattr(self,"servers",[]),14)
                for i,server in enumerate(recovery,1):
                    host=str(server.get("host") or server.get("ip") or "VPN server")
                    if host in attempted: continue
                    attempted.append(host)
                    try:
                        self.events.put(("status",None,f"Recovery route • {server.get('country','VPN')} • {i}/{len(recovery)}…")); process,work,logfile,vpn_ip=connect_verified(self,server,previous)
                        self.process=process; self.tmp=work; self.current_log=logfile; self.selected_server=server; c.mark_connected(process,vpn_ip); self.events.put(("connected",None,f"CONNECTED • {server.get('country','VPN')} • exit IP {vpn_ip}")); return
                    except Exception as exc: last=exc; c.mark_error()
                detail="authentication rejected by the last tested public relay" if _auth_failed(last) else (str(last) if last else "no endpoint completed verification")
                self.events.put(("error",None,f"No working VPN endpoint was found after testing {len(attempted)} servers. {detail}."))
            except Exception as exc: c.mark_error(); self.events.put(("error",None,f"VPN connection failed: {exc}"))
        threading.Thread(target=worker,daemon=True,name="findupto-vpn-connect").start()
    def disconnect(self):
        c=controller(self); c.disconnect(getattr(self,"process",None)); self.process=None; self.current_log=None; self.tmp=None; self.selected_server=None; self.events.put(("disconnected",None,"DISCONNECTED • VPN tunnel closed"))
    def change_ip(self):
        c=controller(self); current=getattr(self,"selected_server",None)
        if not current or c.state.value!="connected": self.events.put(("error",None,"Connect the VPN first, then use Change IP.")); return
        if not c.begin_change_ip(): self.events.put(("error",None,"Another VPN operation is already in progress.")); return
        previous=c.session.public_ip; c.terminate_process(getattr(self,"process",None)); self.process=None; self.tmp=None; self.current_log=None; candidates=_fresh_recovery_candidates(engine,current,getattr(self,"servers",[]),12)
        def worker():
            last=None
            for i,server in enumerate(candidates,1):
                try:
                    self.events.put(("status",None,f"Changing IP • {server.get('country','VPN')} • {i}/{len(candidates)}…")); process,work,logfile,vpn_ip=connect_verified(self,server,previous)
                    if previous and vpn_ip==previous: c.terminate_process(process); last=RuntimeError("same exit IP"); continue
                    self.process=process; self.tmp=work; self.current_log=logfile; self.selected_server=server; c.mark_connected(process,vpn_ip); self.events.put(("connected",None,f"IP CHANGED • {server.get('country','VPN')} • new exit IP {vpn_ip}")); return
                except Exception as exc: last=exc; c.mark_error()
            self.events.put(("error",None,f"Could not obtain a different exit IP after testing {len(candidates)} endpoints."+(f" Last error: {last}" if last else "")))
        threading.Thread(target=worker,daemon=True,name="findupto-vpn-change-ip").start()
    def open_browser(self):
        if getattr(self,"process",None) is None: self.events.put(("error",None,"Connect the VPN first.")); return
        try: open_secure_browser(self)
        except Exception as exc: self.events.put(("error",None,f"Secure Browser could not start: {exc}"))
    LegacyApp._start_connection=start_connection; LegacyApp._disconnect=disconnect; LegacyApp._change_ip=change_ip; LegacyApp._open_browser=open_browser; LegacyApp._findupto_session_controller=controller; LegacyApp._findupto_runtime_wired=True

if __name__=="__main__":
    if os.name=="nt" and not _is_admin():
        if _start_elevated(): raise SystemExit(0)
        raise SystemExit(1)
    try:
        import smart_bootstrap
        _install_gui_compatibility()
        from gui_premium_runtime import App
        App().mainloop()
    except Exception as exc: _show_startup_error(exc); raise
