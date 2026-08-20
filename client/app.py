from __future__ import annotations

"""Single application entry point for Findupto VPN."""

import os
import sys

VERSION = "13.1.2"


if __name__ == "__main__":
    # The GUI must start normally. VPN/OpenVPN operations can request the
    # privileges they need without making the entire application elevation
    # flow responsible for starting Tkinter.
    try:
        from gui import App
        App().mainloop()
    except Exception as exc:
        # pythonw.exe hides stderr; provide a visible diagnostic instead.
        if os.name == "nt":
            try:
                import ctypes
                ctypes.windll.user32.MessageBoxW(
                    None,
                    f"Findupto VPN could not start.\n\n{type(exc).__name__}: {exc}",
                    "Findupto VPN",
                    0x10,
                )
            except Exception:
                pass
        raise
