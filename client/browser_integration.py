"""Findupto Browser integration helpers.

Keeps the secure-browser launcher visible even when the responsive VPN
layout switches to compact mode. The dashboard owns the actual browser UI;
this module only provides the launcher and visibility guard.
"""

import tkinter as tk


_BROWSER_BUTTON_TEXT = "🌐  OPEN SECURE BROWSER"


def open_secure_browser(parent=None):
    """Launch the Findupto secure browser window from the VPN UI."""
    parent = parent or tk._default_root
    try:
        from vpn_browser import VPNBrowser
        return VPNBrowser(parent)
    except Exception as exc:
        win = tk.Toplevel(parent)
        win.title("Findupto Browser Error")
        win.configure(bg="#060811")
        tk.Label(win, text=f"Browser could not start: {exc}", bg="#060811", fg="white").pack(padx=30, pady=30)
        return win


def _ensure_browser_sidebar(root):
    """Keep the sidebar and its browser launcher available in compact windows."""
    sidebar = getattr(root, "sidebar", None)
    if sidebar is None or not sidebar.winfo_exists():
        root.after(250, lambda: _ensure_browser_sidebar(root))
        return

    # The responsive dashboard previously hid the whole sidebar below 1040px.
    # Re-show it so the Browser button is always reachable.
    try:
        if sidebar.winfo_manager() != "pack":
            sidebar.pack(side="left", fill="y", before=getattr(root, "content", None))
    except Exception:
        try:
            sidebar.pack(side="left", fill="y")
        except Exception:
            pass

    # If a future UI revision removes the launcher, recreate it at the top.
    found = False
    for child in sidebar.winfo_children():
        if isinstance(child, tk.Button) and "BROWSER" in str(child.cget("text")).upper():
            found = True
            break
    if not found and hasattr(root, "_button"):
        button = root._button(sidebar, _BROWSER_BUTTON_TEXT, lambda: open_secure_browser(root), "primary")
        button.pack(fill="x", padx=12, pady=(0, 14), before=sidebar.winfo_children()[0] if sidebar.winfo_children() else None)

    root.after(1000, lambda: _ensure_browser_sidebar(root))


# gui.py imports this module before constructing App. Schedule a guard on
# every Tk root so the browser launcher survives responsive-layout changes.
_ORIGINAL_TK_INIT = tk.Tk.__init__
if not getattr(tk.Tk, "_findupto_browser_guard", False):
    def _findupto_tk_init(self, *args, **kwargs):
        _ORIGINAL_TK_INIT(self, *args, **kwargs)
        self.after_idle(lambda: _ensure_browser_sidebar(self))

    tk.Tk.__init__ = _findupto_tk_init
    tk.Tk._findupto_browser_guard = True
