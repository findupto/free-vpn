from __future__ import annotations

"""Single application entry point for Findupto VPN."""

import ctypes
import os
import subprocess
import sys
from pathlib import Path

VERSION = "12.0.2"


def _is_admin() -> bool:
    if os.name != "nt":
        return True
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _elevate() -> None:
    """Relaunch elevated so OpenVPN can create the tunnel and install Windows routes."""
    if os.name != "nt" or _is_admin():
        return

    if getattr(sys, "frozen", False):
        executable = sys.executable
        parameters = ""
    else:
        executable = sys.executable
        parameters = subprocess.list2cmdline([str(Path(__file__).resolve())])

    result = ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        executable,
        parameters,
        str(Path(executable).resolve().parent),
        1,
    )
    if result <= 32:
        raise RuntimeError(
            "Administrator permission is required to create the Windows VPN tunnel. "
            "Please allow the UAC prompt and start Findupto VPN again."
        )
    raise SystemExit(0)


if __name__ == "__main__":
    _elevate()
    from gui import App

    App().mainloop()
