"""Findupto Browser integration helpers."""

import tkinter as tk


def open_secure_browser(parent):
    """Launch the Findupto secure browser window from the VPN UI."""
    try:
        from vpn_browser import VPNBrowser
        return VPNBrowser(parent)
    except Exception as exc:
        win = tk.Toplevel(parent)
        win.title("Findupto Browser Error")
        tk.Label(win, text=f"Browser could not start: {exc}").pack(padx=30, pady=30)
        return win
