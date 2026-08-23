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

VERSION = "14.3.1"


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


def _refresh_candidates(engine, selected: dict, existing: list[dict], limit: int = 12) -> list[dict]:
    """Return unused endpoints, then force one fresh provider catalog."""
    seen = {str(selected.get("id") or selected.get("host") or "").lower()}
    candidates = []
    for item in existing:
        key = str(item.get("id") or item.get("host") or "").lower()
        if key and key not in seen:
            seen.add(key)
            candidates.append(item)
        if len(candidates) >= limit:
            return candidates
    try:
        cache = getattr(engine, "CACHE", None)
        if cache:
            Path(cache).unlink(missing_ok=True)
        import smart_bootstrap
        smart_bootstrap.controller.blocked.clear()
        for item in engine.discover(deadline=18):
            key = str(item.get("id") or item.get("host") or "").lower()
            if key and key not in seen:
                seen.add(key)
                candidates.append(item)
            if len(candidates) >= limit:
                break
    except Exception as exc:
        engine.log(f"FRESH DISCOVERY FAILOVER ERROR={type(exc).__name__}: {exc}")
    return candidates


def _install_gui_compatibility() -> None:
    from gui import App as LegacyApp
    import standalone_engine as engine
    from browser_integration import open_secure_browser

    if getattr(LegacyApp, "_findupto_runtime_wired", False):
        return

    original_refresh = LegacyApp.refresh

    def refresh_with_status(self):
        if not hasattr(self, "status"):
            self.status = tk.StringVar(master=self, value="Preparing network scan…")
        if not hasattr(self, "side_status"):
            self.side_status = tk.StringVar(master=self, value="Ready to connect")
        return original_refresh(self)

    LegacyApp.refresh = refresh_with_status

    def _controller(self):
        controller = getattr(self, "_session_controller", None)
        if controller is None:
            controller = SessionController()
            self._session_controller = controller
        return controller

    def _connect_verified(self, server, previous_ip=None):
        process, work, logfile = engine.connect(server, total_deadline=30)
        try:
            vpn_ip = engine.verify_tunnel(previous_ip=previous_ip, timeout=10)
        except Exception:
            _controller(self).terminate_process(process)
            raise
        return process, work, logfile, vpn_ip

    def start_connection(self, selected):
        controller = _controller(self)
        if not controller.begin_connect(selected):
            self.events.put(("error", None, "A VPN operation is already in progress."))
            return

        def worker():
            previous_ip = None
            attempted = []
            last_error = None
            try:
                try:
                    previous_ip = engine.public_ip(timeout=5)
                except Exception:
                    pass
                candidates = [selected] + _refresh_candidates(engine, selected, getattr(self, "servers", []), 12)
                self.events.put(("status", None, f"Finding a working VPN route • testing {len(candidates)} endpoints…"))
                for index, server in enumerate(candidates, 1):
                    host = str(server.get("host") or "VPN server")
                    attempted.append(host)
                    try:
                        self.events.put(("status", None, f"Connecting • {server.get('country', 'VPN')} • {index}/{len(candidates)}…"))
                        process, work, logfile, vpn_ip = _connect_verified(self, server, previous_ip)
                        self.process = process
                        self.tmp = work
                        self.current_log = logfile
                        self.selected_server = server
                        controller.mark_connected(process, vpn_ip)
                        engine.log(f"GUI CONNECTED host={host} ip={vpn_ip} attempts={len(attempted)}")
                        self.events.put(("connected", None, f"CONNECTED • {server.get('country', 'VPN')} • exit IP {vpn_ip}"))
                        return
                    except Exception as exc:
                        last_error = exc
                        controller.mark_error()
                        reason = "authentication rejected" if _auth_failed(exc) else str(exc)
                        engine.log(f"GUI ENDPOINT FAILED host={host} attempt={index}/{len(candidates)} reason={reason}")
                        if index < len(candidates):
                            self.events.put(("status", None, f"Endpoint failed • automatically switching ({index}/{len(candidates)})…"))
                if _auth_failed(last_error) if last_error else False:
                    detail = "the public endpoint credentials were rejected; the tested servers are not accepting their advertised credentials"
                else:
                    detail = str(last_error) if last_error else "no endpoint completed verification"
                self.events.put(("error", None, f"No working VPN endpoint was found after testing {len(attempted)} servers. {detail}."))
            except Exception as exc:
                controller.mark_error()
                engine.log(f"GUI CONNECTION WORKER ERROR={type(exc).__name__}: {exc}")
                self.events.put(("error", None, f"VPN connection failed: {exc}"))

        threading.Thread(target=worker, daemon=True, name="findupto-vpn-connect").start()

    def disconnect(self):
        controller = _controller(self)
        controller.disconnect(getattr(self, "process", None))
        self.process = None
        self.current_log = None
        self.tmp = None
        self.selected_server = None
        engine.log("GUI VPN DISCONNECTED")
        self.events.put(("disconnected", None, "DISCONNECTED • VPN tunnel closed"))

    def change_ip(self):
        controller = _controller(self)
        current = getattr(self, "selected_server", None)
        if not current or controller.state.value != "connected":
            self.events.put(("error", None, "Connect the VPN first, then use Change IP."))
            return
        if not controller.begin_change_ip():
            self.events.put(("error", None, "Another VPN operation is already in progress."))
            return
        previous_ip = controller.session.public_ip
        controller.terminate_process(getattr(self, "process", None))
        self.process = None
        self.tmp = None
        self.current_log = None
        candidates = _refresh_candidates(engine, current, getattr(self, "servers", []), 12)

        def worker():
            last_error = None
            for index, server in enumerate(candidates, 1):
                controller.mark_change_target(server)
                try:
                    self.events.put(("status", None, f"Changing IP • {server.get('country', 'VPN')} • {index}/{len(candidates)}…"))
                    process, work, logfile, vpn_ip = _connect_verified(self, server, previous_ip)
                    if previous_ip and vpn_ip == previous_ip:
                        controller.terminate_process(process)
                        last_error = RuntimeError("endpoint returned the existing exit IP")
                        continue
                    self.process = process
                    self.tmp = work
                    self.current_log = logfile
                    self.selected_server = server
                    controller.mark_connected(process, vpn_ip)
                    self.events.put(("connected", None, f"IP CHANGED • {server.get('country', 'VPN')} • new exit IP {vpn_ip}"))
                    return
                except Exception as exc:
                    last_error = exc
                    controller.mark_error()
            self.process = None
            self.selected_server = None
            self.events.put(("error", None, f"Could not obtain a different exit IP after testing {len(candidates)} endpoints." + (f" Last error: {last_error}" if last_error else "")))

        threading.Thread(target=worker, daemon=True, name="findupto-vpn-change-ip").start()

    def open_browser(self):
        process = getattr(self, "process", None)
        if process is None or process.poll() is not None:
            self.events.put(("error", None, "Connect the VPN first. The Secure Browser is locked until a verified VPN tunnel is active."))
            return
        try:
            open_secure_browser(self)
        except Exception as exc:
            self.events.put(("error", None, f"Secure Browser could not start: {exc}"))

    LegacyApp._start_connection = start_connection
    LegacyApp._disconnect = disconnect
    LegacyApp._change_ip = change_ip
    LegacyApp._open_browser = open_browser
    LegacyApp._findupto_session_controller = _controller
    LegacyApp._findupto_runtime_wired = True


if __name__ == "__main__":
    if os.name == "nt" and not _is_admin():
        if _start_elevated():
            raise SystemExit(0)
        raise SystemExit(1)
    try:
        import smart_bootstrap
        _install_gui_compatibility()
        from gui_charm import App
        App().mainloop()
    except Exception as exc:
        _show_startup_error(exc)
        raise
