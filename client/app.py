from __future__ import annotations

"""Single application entry point for Findupto VPN."""

import ctypes
import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path

from privacy import redact_log_message

VERSION = "14.1.0"


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
    """Provide legacy GUI state required by the newer premium dashboard."""
    from gui import App as LegacyApp

    original_refresh = LegacyApp.refresh
    if getattr(LegacyApp.refresh, "_findupto_status_compat", False):
        return

    def refresh_with_status(self):
        if not hasattr(self, "status"):
            self.status = tk.StringVar(master=self, value="Preparing network scan…")
        return original_refresh(self)

    refresh_with_status._findupto_status_compat = True
    LegacyApp.refresh = refresh_with_status


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
