import ctypes
import json
import os
import subprocess
import sys
import tempfile
import threading
import urllib.request
import tkinter as tk
from tkinter import messagebox, ttk

API_URL = os.environ.get("FINDUPTO_API_URL", "https://findupto-free-vpn.onrender.com")
APP_NAME = "Findupto Free VPN"
TUNNEL_NAME = "FinduptoVPN"


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def wireguard_path():
    candidates = [
        os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "WireGuard", "wireguard.exe"),
        os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), "WireGuard", "wireguard.exe"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def fetch_nodes():
    url = API_URL.rstrip("/") + "/api/v1/nodes"
    with urllib.request.urlopen(url, timeout=8) as response:
        return json.loads(response.read().decode("utf-8"))


def download_config(url):
    with urllib.request.urlopen(url, timeout=10) as response:
        return response.read().decode("utf-8")


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("760x500")
        self.minsize(680, 440)
        self.configure(padx=18, pady=18)
        self.nodes = []
        self.connected = False
        self.config_path = None
        self.build_ui()
        self.refresh()

    def build_ui(self):
        ttk.Label(self, text=APP_NAME, font=("Segoe UI", 20, "bold")).pack(anchor="w")
        ttk.Label(self, text="Fast Windows desktop client • WireGuard-first").pack(anchor="w", pady=(2, 14))

        frame = ttk.Frame(self)
        frame.pack(fill="both", expand=True)

        columns = ("country", "city", "protocol", "status")
        self.tree = ttk.Treeview(frame, columns=columns, show="headings", height=12)
        for col, title, width in [("country", "Country", 180), ("city", "City", 180), ("protocol", "Protocol", 120), ("status", "Status", 180)]:
            self.tree.heading(col, text=title)
            self.tree.column(col, width=width, anchor="w")
        self.tree.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        scroll.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scroll.set)

        buttons = ttk.Frame(self)
        buttons.pack(fill="x", pady=(14, 8))
        ttk.Button(buttons, text="Refresh", command=self.refresh).pack(side="left")
        self.connect_btn = ttk.Button(buttons, text="Connect", command=self.connect)
        self.connect_btn.pack(side="left", padx=8)
        ttk.Button(buttons, text="Disconnect", command=self.disconnect).pack(side="left")

        self.status = tk.StringVar(value="Ready")
        ttk.Label(self, textvariable=self.status).pack(anchor="w")

    def refresh(self):
        self.status.set("Finding healthy WireGuard servers…")
        threading.Thread(target=self._refresh_worker, daemon=True).start()

    def _refresh_worker(self):
        try:
            nodes = fetch_nodes()
            self.after(0, lambda: self._show_nodes(nodes))
        except Exception as exc:
            self.after(0, lambda: self.status.set(f"Unable to reach Findupto API: {exc}"))

    def _show_nodes(self, nodes):
        self.nodes = [n for n in nodes if n.get("protocol", "wireguard").lower() == "wireguard"]
        for item in self.tree.get_children():
            self.tree.delete(item)
        for index, node in enumerate(self.nodes):
            ready = "Ready" if node.get("config_url") else "No client config"
            self.tree.insert("", "end", iid=str(index), values=(node.get("country", ""), node.get("city", ""), "WireGuard", ready))
        self.status.set(f"{len(self.nodes)} healthy WireGuard server(s) available")

    def selected_node(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo(APP_NAME, "Select a server first.")
            return None
        return self.nodes[int(selection[0])]

    def connect(self):
        if not sys.platform.startswith("win"):
            messagebox.showerror(APP_NAME, "The desktop client currently supports Windows only.")
            return
        if not is_admin():
            messagebox.showerror(APP_NAME, "Administrator permission is required to create the VPN tunnel.")
            return
        wg = wireguard_path()
        if not wg:
            messagebox.showerror(APP_NAME, "WireGuard for Windows is not installed. Re-run the Findupto installer.")
            return
        node = self.selected_node()
        if not node:
            return
        if not node.get("config_url"):
            messagebox.showwarning(APP_NAME, "This server is registered, but it has no client configuration yet.")
            return
        self.status.set("Downloading short-lived VPN configuration…")
        threading.Thread(target=self._connect_worker, args=(wg, node), daemon=True).start()

    def _connect_worker(self, wg, node):
        try:
            config = download_config(node["config_url"])
            fd, path = tempfile.mkstemp(prefix="findupto-", suffix=".conf")
            os.close(fd)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(config)
            subprocess.run([wg, "/uninstalltunnelservice", TUNNEL_NAME], capture_output=True, text=True, timeout=20)
            result = subprocess.run([wg, "/installtunnelservice", path], capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "WireGuard failed to start")
            self.config_path = path
            self.connected = True
            self.after(0, lambda: self.status.set(f"Connected to {node.get('city', node.get('country', 'server'))}"))
        except Exception as exc:
            self.after(0, lambda: messagebox.showerror(APP_NAME, str(exc)))
            self.after(0, lambda: self.status.set("Connection failed"))

    def disconnect(self):
        wg = wireguard_path()
        if not wg or not is_admin():
            self.status.set("Administrator permission is required to disconnect.")
            return
        subprocess.run([wg, "/uninstalltunnelservice", TUNNEL_NAME], capture_output=True)
        if self.config_path:
            try:
                os.remove(self.config_path)
            except OSError:
                pass
            self.config_path = None
        self.connected = False
        self.status.set("Disconnected")


if __name__ == "__main__":
    App().mainloop()
