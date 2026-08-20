from __future__ import annotations

"""Single application entry point for Findupto VPN."""

import ctypes
import os
import subprocess
import sys
from pathlib import Path

VERSION = "13.1.3"


def _is_admin() -> bool:
    if os.name != "nt":
        return True
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _start_elevated() -> bool:
    """Start one elevated copy of this script and return True on success."""
    if os.name != "nt" or _is_admin():
        return True

    script = str(Path(__file__).resolve())
    executable = sys.executable
    # Preserve normal Python invocation semantics and avoid a second GUI in
    # the non-elevated process. ShellExecuteW('runas') is the Windows UAC path.
    result = ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        executable,
        subprocess.list2cmdline([script]),
        str(Path(script).parent),
        1,
    )
    if result <= 32:
        try:
            ctypes.windll.user32.MessageBoxW(
                None,
                "Administrator permission is required for the VPN tunnel.\n\n"
                "The UAC request was cancelled or Windows could not start the elevated application.",
                "Findupto VPN",
                0x10,
            )
        except Exception:
            pass
        return False
    return True


def _show_startup_error(exc: Exception) -> None:
    if os.name != "nt":
        return
    try:
        ctypes.windll.user32.MessageBoxW(
            None,
            f"Findupto VPN could not start.\n\n{type(exc).__name__}: {exc}",
            "Findupto VPN",
            0x10,
        )
    except Exception:
        pass


if __name__ == "__main__":
    if os.name == "nt" and not _is_admin():
        # The elevated child runs the GUI. The original process must exit so
        # only one Tk window and one application controller remain active.
        if _start_elevated():
            raise SystemExit(0)
        raise SystemExit(1)

    try:
        from gui import App
        App().mainloop()
    except Exception as exc:
        _show_startup_error(exc)
        raise
