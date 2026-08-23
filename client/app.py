from __future__ import annotations

"""Single application entry point for Findupto VPN."""

import ctypes
import os
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path

from privacy import redact_log_message
from session_controller import SessionController

VERSION = "14.4.0"


def _is_admin() -> bool:
    if os.name != "nt":
        return True
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _start_elevated() -> bool:
    if os.name != "nt" or _is_admin():
        return True
    script = str(Path(__file__).resolve())
    result = ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, subprocess.list2cmdline([script]), str(Path(script).parent), 1)
    if result <= 32:
        try:
            ctypes.windll.user32.MessageBoxW(None, "Administrator permission is required for the VPN tunnel.", "Findupto VPN", 0x10)
        except Exception:
            pass
        return False
    return True


def _show_startup_error(exc: Exception) -> None:
    if os.name != "nt":
        return
    try:
        safe = redact_log_message(f"{type(exc).__name__}: {exc}")
        ctypes.windll.user32.MessageBoxW(None, f"Findupto VPN could not start.\n\n{safe}", "Findupto VPN", 0x10)
    except Exception:
        pass


def _auth_failed(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(x in text for x in ("authentication failed", "auth_failed", "auth failed", "verification failed"))


def _refresh_candidates(engine, selected: dict, existing: list[dict], limit: int = 10) -> list[dict]:
    """Build cheap local fallbacks first; fresh network discovery is recovery-only."""
    seen = {str(selected.get("id") or selected.get("host") or selected.get("ip") or "").lower()}
    candidates = []
    for item in existing:
        key = str(item.get("id") or item.get("host") or item.get("ip") or "").lower()
        if key and key not in seen:
            seen.add(key); candidates.append(item)
        if len(candidates) >= limit:
            return candidates
    return candidates


def _fresh_recovery_candidates(engine, selected: dict, existing: list[dict], limit: int = 14) -> list[dict]:
    candidates = _refresh_candidates(engine, selected, existing, limit)
    if len(candidates) >= limit:
        return candidates
    try:
        cache = getattr(engine, "CACHE", None)
        if cache:
            Path(cache).unlink(missing_ok=True)
        import smart_bootstrap
        smart_bootstrap.controller.blocked.clear()
        seen = {str(selected.get("id") or selected.get("host") or selected.get("ip") or "").lower()}
        seen.update(str(x.get("id") or x.get("host") or x.get("ip") or "").lower() for x in candidates)
        for item in engine.discover(deadline=10):
            key = str(item.get("id") or item.get("host") or item.get("ip") or "").lower()
            if key and key not in seen:
                seen.add(key); candidates.append(item)
            if len(candidates) >= limit:
                break
    except Exception as exc:
        engine.log(f"FRESH RECOVERY DISCOVERY ERROR={type(exc).__name__}: {exc}")
    return candidates


def _install_gui_compatibility() -> None:
    from gui import App as LegacyApp
    import standalone_engine as engine
    from browser_integration import open_secure_browser

    if getattr(LegacyApp, "_findupto_runtime_wired", False):
        return

    def _controller(self):
        controller = getattr(self, "_session_controller", None)
        if controller is None:
            controller = SessionController(); self._session_controller = controller
        return controller

    def _connect_verified(self, server, previous_ip=None):
        process, work, logfile = engine.connect(server, total_deadline=22)
        try:
            vpn_ip = engine.verify_tunnel(previous_ip=previous_ip, timeout=8)
        except Exception:
            _controller(self).terminate_process(process); raise
        return process, work, logfile, vpn_ip

    def start_connection(self, selected):
        controller = _controller(self)
        if not controller.begin_connect(selected):
            self.events.put(("error", None, "A VPN operation is already in progress.")); return

        def worker():
            previous_ip = None; attempted=[]; last_error=None
            try:
                try: previous_ip=engine.public_ip(timeout=4)
                except Exception: pass
                # Critical latency fix: attempt the user-selected/fastest endpoint immediately.
                initial = [selected] + _refresh_candidates(engine, selected, getattr(self,"servers",[]), 5)
                self.events.put(("status",None,"Connecting to the selected verified route…"))
                for index,server in enumerate(initial,1):
                    host=str(server.get("host") or server.get("ip") or "VPN server"); attempted.append(host)
                    try:
                        self.events.put(("status",None,f"Connecting • {server.get('country','VPN')} • {index}/{len(initial)}…"))
                        process,work,logfile,vpn_ip=_connect_verified(self,server,previous_ip)
                        self.process=process; self.tmp=work; self.current_log=logfile; self.selected_server=server; controller.mark_connected(process,vpn_ip)
                        self.events.put(("connected",None,f"CONNECTED • {server.get('country','VPN')} • exit IP {vpn_ip}")); return
                    except Exception as exc:
                        last_error=exc; controller.mark_error(); engine.log(f"GUI ENDPOINT FAILED host={host} attempt={index} reason={type(exc).__name__}: {exc}")
                # Only after the fast local pool fails do we pay the network-discovery cost.
                recovery=_fresh_recovery_candidates(engine,selected,getattr(self,"servers",[]),14)
                for index,server in enumerate(recovery,1):
                    if str(server.get("host") or server.get("ip") or "") in attempted: continue
                    host=str(server.get("host") or server.get("ip") or "VPN server"); attempted.append(host)
                    try:
                        self.events.put(("status",None,f"Recovery route • {server.get('country','VPN')} • {index}/{len(recovery)}…"))
                        process,work,logfile,vpn_ip=_connect_verified(self,server,previous_ip)
                        self.process=process; self.tmp=work; self.current_log=logfile; self.selected_server=server; controller.mark_connected(process,vpn_ip)
                        self.events.put(("connected",None,f"CONNECTED • {server.get('country','VPN')} • exit IP {vpn_ip}")); return
                    except Exception as exc:
                        last_error=exc; controller.mark_error()
                detail="authentication rejected by the last tested public relay" if _auth_failed(last_error) else (str(last_error) if last_error else "no endpoint completed verification")
                self.events.put(("error",None,f"No working VPN endpoint was found after testing {len(attempted)} servers. {detail}."))
            except Exception as exc:
                controller.mark_error(); self.events.put(("error",None,f"VPN connection failed: {exc}"))
        threading.Thread(target=worker,daemon=True,name="findupto-vpn-connect").start()

    def disconnect(self):
        controller=_controller(self); controller.disconnect(getattr(self,"process",None)); self.process=None; self.current_log=None; self.tmp=None; self.selected_server=None; self.events.put(("disconnected",None,"DISCONNECTED • VPN tunnel closed"))

    def change_ip(self):
        controller=_controller(self); current=getattr(self,"selected_server",None)
        if not current or controller.state.value!="connected": self.events.put(("error",None,"Connect the VPN first, then use Change IP.")); return
        if not controller.begin_change_ip(): self.events.put(("error",None,"Another VPN operation is already in progress.")); return
        previous_ip=controller.session.public_ip; controller.terminate_process(getattr(self,"process",None)); self.process=None; self.tmp=None; self.current_log=None
        candidates=_fresh_recovery_candidates(engine,current,getattr(self,"servers",[]),12)
        def worker():
            last=None
            for i,server in enumerate(candidates,1):
                try:
                    self.events.put(("status",None,f"Changing IP • {server.get('country','VPN')} • {i}/{len(candidates)}…")); process,work,logfile,vpn_ip=_connect_verified(self,server,previous_ip)
                    if previous_ip and vpn_ip==previous_ip: controller.terminate_process(process); last=RuntimeError("same exit IP"); continue
                    self.process=process; self.tmp=work; self.current_log=logfile; self.selected_server=server; controller.mark_connected(process,vpn_ip); self.events.put(("connected",None,f"IP CHANGED • {server.get('country','VPN')} • new exit IP {vpn_ip}")); return
                except Exception as exc: last=exc; controller.mark_error()
            self.events.put(("error",None,f"Could not obtain a different exit IP after testing {len(candidates)} endpoints." + (f" Last error: {last}" if last else "")))
        threading.Thread(target=worker,daemon=True,name="findupto-vpn-change-ip").start()

    def open_browser(self):
        if getattr(self,"process",None) is None: self.events.put(("error",None,"Connect the VPN first.")); return
        try: open_secure_browser(self)
        except Exception as exc: self.events.put(("error",None,f"Secure Browser could not start: {exc}"))

    LegacyApp._start_connection=start_connection; LegacyApp._disconnect=disconnect; LegacyApp._change_ip=change_ip; LegacyApp._open_browser=open_browser; LegacyApp._findupto_session_controller=_controller; LegacyApp._findupto_runtime_wired=True


if __name__ == "__main__":
    if os.name == "nt" and not _is_admin():
        if _start_elevated(): raise SystemExit(0)
        raise SystemExit(1)
    try:
        import smart_bootstrap
        _install_gui_compatibility()
        from gui_premium import App
        App().mainloop()
    except Exception as exc:
        _show_startup_error(exc); raise
