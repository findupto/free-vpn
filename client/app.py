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

VERSION = "14.3.0"


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
    executable = sys.executable
    result = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", executable, subprocess.list2cmdline([script]), str(Path(script).parent), 1
    )
    if result <= 32:
        try:
            ctypes.windll.user32.MessageBoxW(None, "Administrator permission is required for the VPN tunnel.\n\nThe UAC request was cancelled or Windows could not start the elevated application.", "Findupto VPN", 0x10)
        except Exception:
            pass
        return False
    return True


def _show_startup_error(exc: Exception) -> None:
    if os.name != "nt":
        return
    try:
        safe_error = redact_log_message(f"{type(exc).__name__}: {exc}")
        ctypes.windll.user32.MessageBoxW(None, f"Findupto VPN could not start.\n\n{safe_error}", "Findupto VPN", 0x10)
    except Exception:
        pass


def _install_gui_compatibility() -> None:
    """Wire the Charm GUI to the real OpenVPN engine and lifecycle controller."""
    from gui import App as LegacyApp
    import standalone_engine as engine
    from browser_integration import open_secure_browser

    if not getattr(LegacyApp, "_findupto_runtime_wired", False):
        original_refresh = LegacyApp.refresh

        def refresh_with_status(self):
            if not hasattr(self, "status"):
                self.status = tk.StringVar(master=self, value="Preparing network scan…")
            return original_refresh(self)

        LegacyApp.refresh = refresh_with_status

        def _controller(self):
            controller = getattr(self, "_session_controller", None)
            if controller is None:
                controller = SessionController()
                self._session_controller = controller
            return controller

        def _set_status(self, message):
            try:
                self.events.put(("status", None, message))
            except Exception:
                pass

        def _connect_verified(self, server, previous_ip=None):
            process, work, logfile = engine.connect(server, total_deadline=75)
            try:
                vpn_ip = engine.verify_tunnel(previous_ip=previous_ip, timeout=10)
            except Exception:
                _controller(self).terminate_process(process)
                raise
            return process, work, logfile, vpn_ip

        def start_connection(self, server):
            controller = _controller(self)
            if not controller.begin_connect(server):
                self.events.put(("error", None, "A VPN operation is already in progress. Disconnect or wait for it to finish."))
                return

            def worker():
                previous_ip = None
                try:
                    self.events.put(("status", None, f"Connecting to {server.get('country', 'VPN')} • verifying the real tunnel…"))
                    try:
                        previous_ip = engine.public_ip(timeout=5)
                    except Exception as exc:
                        engine.log(f"PRECONNECT IP CHECK FAILED error={type(exc).__name__}: {exc}")
                    process, work, logfile, vpn_ip = _connect_verified(self, server, previous_ip)
                    self.process = process; self.tmp = work; self.current_log = logfile; self.selected_server = server
                    controller.mark_connected(process, vpn_ip)
                    engine.log(f"GUI VPN CONNECTED host={server.get('host')} vpn_ip={vpn_ip}")
                    self.events.put(("connected", None, f"CONNECTED • {server.get('country', 'VPN')} • exit IP {vpn_ip}"))
                except Exception as exc:
                    controller.mark_error()
                    engine.log(f"GUI VPN CONNECTION FAILED host={server.get('host')} error={type(exc).__name__}: {exc}")
                    self.events.put(("error", None, f"VPN connection failed for {server.get('host', 'selected server')}: {exc}"))

            threading.Thread(target=worker, daemon=True, name="findupto-vpn-connect").start()

        def disconnect(self):
            controller = _controller(self)
            controller.disconnect(getattr(self, "process", None))
            self.process = None; self.current_log = None; self.tmp = None; self.selected_server = None
            engine.log("GUI VPN DISCONNECTED")
            self.events.put(("disconnected", None, "DISCONNECTED • VPN tunnel closed"))

        def change_ip(self):
            controller = _controller(self)
            current = getattr(self, "selected_server", None)
            if not current or controller.state.value != "connected":
                self.events.put(("error", None, "Connect the VPN first, then use Change IP.")); return
            if not controller.begin_change_ip():
                self.events.put(("error", None, "Another VPN operation is already in progress.")); return
            candidates = controller.alternate_servers(getattr(self, "servers", []), current)
            if not candidates:
                controller.mark_error(); self.events.put(("error", None, "No alternate verified VPN server is available. Refresh the network and try again.")); return
            previous_ip = controller.session.public_ip
            controller.terminate_process(getattr(self, "process", None))
            self.process = None; self.tmp = None; self.current_log = None

            def worker():
                last_error = None
                for server in candidates[:8]:
                    controller.mark_change_target(server)
                    try:
                        self.events.put(("status", None, f"Changing IP • trying {server.get('country', 'VPN')}…"))
                        process, work, logfile, vpn_ip = _connect_verified(self, server, previous_ip)
                        if previous_ip and vpn_ip == previous_ip:
                            controller.terminate_process(process); last_error = RuntimeError("endpoint returned the existing exit IP"); continue
                        self.process = process; self.tmp = work; self.current_log = logfile; self.selected_server = server
                        controller.mark_connected(process, vpn_ip)
                        engine.log(f"GUI VPN IP CHANGED host={server.get('host')} old_ip={previous_ip} new_ip={vpn_ip}")
                        self.events.put(("connected", None, f"IP CHANGED • {server.get('country', 'VPN')} • new exit IP {vpn_ip}")); return
                    except Exception as exc:
                        last_error = exc; controller.mark_error(); engine.log(f"GUI VPN IP CHANGE FAILED host={server.get('host')} error={type(exc).__name__}: {exc}")
                self.process = None; self.selected_server = None
                message = "Could not obtain a different exit IP. The previous tunnel was closed."
                if last_error: message += f" Last error: {last_error}"
                self.events.put(("error", None, message))

            threading.Thread(target=worker, daemon=True, name="findupto-vpn-change-ip").start()

        def open_browser(self):
            process = getattr(self, "process", None)
            if process is None or process.poll() is not None:
                self.events.put(("error", None, "Connect the VPN first. The Secure Browser is locked until a verified VPN tunnel is active.")); return
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
        import smart_bootstrap  # noqa: F401
        _install_gui_compatibility()
        from gui_charm import App
        App().mainloop()
    except Exception as exc:
        _show_startup_error(exc)
        raise
