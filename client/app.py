from __future__ import annotations
"""Compatibility entry point.

The VPN implementation lives in vpn_engine.py and the UI in gui.py.
This module intentionally contains no second copy of the connection logic.
"""
from gui import App

VERSION = '9.2.0'

if __name__ == '__main__':
    App().mainloop()
