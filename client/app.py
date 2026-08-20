from __future__ import annotations

"""Single application entry point for Findupto VPN."""

import ctypes
import os
import subprocess
import sys
from pathlib import Path

VERSION = "13.1.1"


def _is_admin() -> bool:
    if os.name != "nt":
        return True
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _elevate() -> bool:
    """Start an elevated copy and return whether the current process should continue."""
    if os.name != "nt" or _is_admin():
        return True

    executable = sys.executable
    script = str(Path(__file__).resolve())
    parameters = subprocess.list2cmdline([script])
    result = ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        executable,
        parameters,
        str(Path(script).parent),
        1,
    )
    return result > 32


def _show_elevation_error() -> None:
    try:
        ctypes.windll.user32.MessageBoxW(
            None,
            "Findupto VPN needs Administrator permission to create the VPN tunnel.\n\n"
            "Please run app.py again and click Yes on the Windows permission prompt.",
            "Findupto VPN",
            0x10,
        )
    except Exception:
        pass


if __name__ == "__main__":
    if os.name == "nt" and not _is_admin():
        # A successful UAC launch means the elevated child is now responsible
        # for the GUI. The original process must exit immediately.
        if _elevate():
            raise SystemExit(0)
        _show_elevation_error()
        raise SystemExit(1)

    from gui import App
    App().mainloop()
