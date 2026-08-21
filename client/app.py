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

VERSION = "14.2.0"


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
            ctypes.windll.user32.MessageBoxW(
                None,
                "Administrator permission is required for the VPN tunnel.\n\nThe UAC request was cancelled or Windows could not start the elevated application.",
                "Findupto VPN", 0x10,
            )
        except Exception:
            pass
        return False
    return True


def _show_startup_error(exc: Exception) -> None:
    if os.name != "nt":
        return
    try:
        safe_error = redact_log_message(f"{type(exc).__name__}: {exc}")
        ctypes.windll.user32.MessageBoxW(
            None, f"Findupto VPN could not start.\n\n{safe_error}", "Findupto VPN", 0x10
        )
    except Exception:
        pass


def _install_gui_compatibility() -> None:
    """Wire the premium GUI to the real OpenVPN engine and browser."""
    from gui import App as LegacyApp
    import standalone_engine as engine
    from browser_integration import open_secure_browser

    if not getattr(LegacyApp, "_findupto_runtime_wired", False):
        original_refresh = LegacyApp.refresh

        def refresh_with_status(self):
            if not hasattr(self, "status"):
                self.status = tk.StringVar(master=self, value="Preparing network scan…")
            return original_refresh(self)

        refresh_with_status._findupto_status_compat = True
        LegacyApp.refresh = refresh_with_status

        def start_connection(self, server):
            if getattr(self, "process", None) is not None and self.process.poll() is None:
                self.events.put(("error", None, "A VPN tunnel is already connected. Disconnect it before changing servers."))
                return

            def worker():
                previous_ip = None
                try:
                    self.events.put(("status", None, f"Connecting to {server.get('country', 'VPN')} • testing the real tunnel…"))
                    try:
                        previous_ip = engine.public_ip(timeout=5)
                    except Exception as exc:
                        engine.log(f"PRECONNECT IP CHECK FAILED error={type(exc).__name__}: {exc}")

                    process, work, logfile = engine.connect(server, total_deadline=75)
                    vpn_ip = engine.verify_tunnel(previous_ip=previous_ip, timeout=10)
                    self.process = process
                    self.tmp = work
                    self.current_log = logfile
                    self.selected_server = server
                    engine.log(f"GUI VPN CONNECTED host={server.get('host')} vpn_ip={vpn_ip}")
                    self.events.put(("connected", None, f"CONNECTED • {server.get('country', 'VPN')} • exit IP {vpn_ip}"))
                except Exception as exc:
                    engine.log(f"GUI VPN CONNECTION FAILED host={server.get('host')} error={type(exc).__name__}: {exc}")
                    self.events.put(("error", None, f"VPN connection failed for {server.get('host', 'selected server')}: {exc}"))

            threading.Thread(target=worker, daemon=True, name="findupto-vpn-connect").start()

        def disconnect(self):
            process = getattr(self, "process", None)
            if process is not None:
                try:
                    if process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(timeout=5)
                        except Exception:
                            process.kill()
                except Exception as exc:
                    engine.log(f"GUI DISCONNECT FAIL error={type(exc).__name__}: {exc}")
            self.process = None
            self.current_log = None
            self.tmp = None
            engine.log("GUI VPN DISCONNECTED")

        def open_browser(self):
            process = getattr(self, "process", None)
            if process is None or process.poll() is not None:
                message = "Connect the VPN first. The Secure Browser is locked until a verified VPN tunnel is active."
                self.events.put(("error", None, message))
                return
            try:
                open_secure_browser(self)
            except Exception as exc:
                self.events.put(("error", None, f"Secure Browser could not start: {exc}"))

        LegacyApp._start_connection = start_connection
        LegacyApp._disconnect = disconnect
        LegacyApp._open_browser = open_browser
        LegacyApp._findupto_runtime_wired = True

    # The production app is gui_spinner -> gui_elite -> gui_pro. Add the browser
    # launcher to the actual visible elite sidebar and keep it visible at compact widths.
    try:
        from gui_elite import App as EliteApp
        if not getattr(EliteApp, "_findupto_browser_ui_wired", False):
            original_sidebar = EliteApp._build_premium_sidebar

            def sidebar_with_browser(self):
                original_sidebar(self)
                button = self._button(self.sidebar, "BROWSER", self._open_browser, "primary")
                nav = getattr(self, "nav_items", [])
                before = nav[0] if nav else None
                if before is not None:
                    button.pack(fill="x", padx=12, pady=(0, 10), before=before)
                else:
                    button.pack(fill="x", padx=12, pady=(0, 10))
                self.browser_button = button

            def resize_with_browser(self, width):
                """Safe responsive layout: never call pack_forget on child widgets.

                The previous responsive chain could call pack_forget on a widget that
                had already been re-parented/repacked by the premium UI, producing
                TclError: '...buttonX isn't packed'. The sidebar is intentionally
                persistent because it contains the Secure Browser launcher.
                """
                try:
                    if not self.sidebar.winfo_ismapped():
                        self.sidebar.pack(side="left", fill="y", before=self.content)
                except tk.TclError:
                    pass
                try:
                    compact = width < 1080
                    pad = 14 if width < 860 else 18 if compact else 30
                    for widget in (self.header, self.hero, self.command, self.metrics,
                                   self.filters, self.quick, self.server_card, self.action_bar):
                        try:
                            widget.pack_configure(padx=pad)
                        except tk.TclError:
                            pass
                    if width < 900:
                        self.sidebar.configure(width=210)
                    else:
                        self.sidebar.configure(width=244)
                    try:
                        self.table_hint.configure(text="Scroll horizontally • double-click to connect" if width < 860 else "Live verified endpoints")
                    except tk.TclError:
                        pass
                    try:
                        self._set_table_mode("narrow" if width < 860 else "compact" if compact else "wide")
                    except (AttributeError, tk.TclError, KeyError):
                        pass
                except tk.TclError:
                    pass

            EliteApp._build_premium_sidebar = sidebar_with_browser
            EliteApp._apply_responsive_layout = resize_with_browser
            EliteApp._findupto_browser_ui_wired = True
    except Exception as exc:
        try:
            engine.log(f"BROWSER UI WIRING FAIL error={type(exc).__name__}: {exc}")
        except Exception:
            pass


if __name__ == "__main__":
    if os.name == "nt" and not _is_admin():
        if _start_elevated():
            raise SystemExit(0)
        raise SystemExit(1)
    try:
        import smart_bootstrap  # noqa: F401
        _install_gui_compatibility()
        from gui_spinner import App
        App().mainloop()
    except Exception as exc:
        _show_startup_error(exc)
        raise
