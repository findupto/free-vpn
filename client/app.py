import ctypes
import csv
import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import urllib.request
import zipfile
import tkinter as tk
from tkinter import messagebox, ttk

API_URL = os.environ.get("FINDUPTO_API_URL", "https://findupto-free-vpn.onrender.com")
VPN_GATE_CSV = "https://www.vpngate.net/api/iphone/"
APP_NAME = "Findupto Free VPN"
TUNNEL_NAME = "FinduptoVPN"


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin():
    if is_admin():
        return True
    try:
        executable = sys.executable
        if getattr(sys, "frozen", False):
            executable = sys.executable
            params = " ".join(f'"{arg}"' for arg in sys.argv[1:])
        else:
            params = " ".join(f'"{arg}"' for arg in sys.argv)
        result = ctypes.windll.shell32.ShellExecuteW(None, "runas", executable, params, None, 1)
        return result > 32
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


def openvpn_path():
    candidates = [
        os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "OpenVPN", "bin", "openvpn.exe"),
        os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), "OpenVPN", "bin", "openvpn.exe"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def fetch_servers():
    """Use our API when deployed; fall back directly to VPN Gate so the desktop app
    still works when the optional Findupto API is offline/not deployed yet."""
    api_error = None
    try:
        url = API_URL.rstrip("/") + "/api/v1/public/servers?limit=50"
        with urllib.request.urlopen(url, timeout=8) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        api_error = exc

    request = urllib.request.Request(
        VPN_GATE_CSV,
        headers={"User-Agent": "Findupto-Free-VPN/0.4"},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        text = response.read().decode("utf-8", errors="replace")

    servers = []
    for row in csv.DictReader(line for line in text.splitlines() if not line.startswith("#")):
        ip = row.get("IP", "").strip()
        country = row.get("CountryLong", row.get("CountryShort", "")).strip()
        if not ip or not country:
            continue
        try:
            ping = float(row.get("Ping", ""))
        except (TypeError, ValueError):
            ping = None
        try:
            speed = float(row.get("Speed", "")) / 1_000_000
        except (TypeError, ValueError):
            speed = None
        if ping is not None and ping > 300:
            continue
        if speed is not None and speed < 2:
            continue
        servers.append({
            "id": f"vpngate-{ip}",
            "country": country,
            "city": row.get("City", "Unknown") or "Unknown",
            "hostname": row.get("HostName", ""),
            "ip": ip,
            "protocol": "openvpn",
            "ping_ms": ping,
            "speed_mbps": speed,
            "source": "VPN Gate",
            "config_url": f"https://www.vpngate.net/common/openvpn_download.aspx?ip={ip}",
        })

    servers.sort(key=lambda s: (
        -(s.get("speed_mbps") or 0),
        s.get("ping_ms") if s.get("ping_ms") is not None else 9999,
    ))
    return servers[:50]


def download_config(url):
    request = urllib.request.Request(url, headers={"User-Agent": "Findupto-Free-VPN/0.4"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("900x560")
        self.minsize(760, 480)
        self.configure(padx=18, pady=18)
        self.servers = []
        self.connected = False
        self.config_path = None
        self.process = None
        self.build_ui()
        self.refresh()

    def build_ui(self):
        ttk.Label(self, text=APP_NAME, font=("Segoe UI", 20, "bold")).pack(anchor="w")
        ttk.Label(self, text="Free public servers • Windows desktop • OpenVPN / WireGuard").pack(anchor="w", pady=(2, 14))

        frame = ttk.Frame(self)
        frame.pack(fill="both", expand=True)

        columns = ("country", "city", "protocol", "ping", "speed", "source")
        self.tree = ttk.Treeview(frame, columns=columns, show="headings", height=15)
        for col, title, width in [
            ("country", "Country", 180), ("city", "City", 160), ("protocol", "Protocol", 100),
            ("ping", "Ping", 80), ("speed", "Speed", 90), ("source", "Source", 150)
        ]:
            self.tree.heading(col, text=title)
            self.tree.column(col, width=width, anchor="w")
        self.tree.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        scroll.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scroll.set)

        buttons = ttk.Frame(self)
        buttons.pack(fill="x", pady=(14, 8))
        ttk.Button(buttons, text="Refresh Servers", command=self.refresh).pack(side="left")
        self.connect_btn = ttk.Button(buttons, text="Connect", command=self.connect)
        self.connect_btn.pack(side="left", padx=8)
        ttk.Button(buttons, text="Disconnect", command=self.disconnect).pack(side="left")

        self.status = tk.StringVar(value="Finding free servers…")
        ttk.Label(self, textvariable=self.status).pack(anchor="w")

    def refresh(self):
        self.status.set("Finding free public servers…")
        threading.Thread(target=self._refresh_worker, daemon=True).start()

    def _refresh_worker(self):
        try:
            servers = fetch_servers()
            self.after(0, lambda: self._show_servers(servers))
        except Exception as exc:
            self.after(0, lambda: self.status.set(f"Unable to load free servers: {exc}"))

    def _show_servers(self, servers):
        self.servers = servers
        for item in self.tree.get_children():
            self.tree.delete(item)
        for index, server in enumerate(self.servers):
            ping = f"{server['ping_ms']:.0f} ms" if server.get("ping_ms") is not None else "-"
            speed = f"{server['speed_mbps']:.1f} Mbps" if server.get("speed_mbps") is not None else "-"
            self.tree.insert("", "end", iid=str(index), values=(
                server.get("country", ""), server.get("city", "Unknown"),
                server.get("protocol", "").upper(), ping, speed, server.get("source", "")))
        self.status.set(f"{len(self.servers)} free public server(s) available")

    def selected_server(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo(APP_NAME, "Select a server first.")
            return None
        return self.servers[int(selection[0])]

    def connect(self):
        if not sys.platform.startswith("win"):
            messagebox.showerror(APP_NAME, "The desktop client currently supports Windows only.")
            return
        if not is_admin():
            if relaunch_as_admin():
                self.destroy()
            else:
                messagebox.showerror(APP_NAME, "Administrator permission is required to create the VPN tunnel.")
            return
        server = self.selected_server()
        if not server:
            return
        protocol = server.get("protocol", "").lower()
        if protocol == "openvpn":
            self.connect_openvpn(server)
        elif protocol == "wireguard":
            self.connect_wireguard(server)
        else:
            messagebox.showerror(APP_NAME, f"Unsupported protocol: {protocol}")

    def connect_openvpn(self, server):
        ovpn = openvpn_path()
        if not ovpn:
            messagebox.showerror(APP_NAME, "OpenVPN is not installed. Install OpenVPN for Windows, then try again.")
            return
        self.status.set("Downloading VPN configuration…")
        threading.Thread(target=self._openvpn_worker, args=(ovpn, server), daemon=True).start()

    def _openvpn_worker(self, ovpn, server):
        try:
            data = download_config(server["config_url"])
            if data.startswith(b"PK"):
                with zipfile.ZipFile(io.BytesIO(data)) as archive:
                    configs = [n for n in archive.namelist() if n.lower().endswith(".ovpn")]
                    if not configs:
                        raise RuntimeError("No OpenVPN configuration was provided by the server.")
                    config = archive.read(configs[0])
            else:
                config = data
            fd, path = tempfile.mkstemp(prefix="findupto-", suffix=".ovpn")
            os.close(fd)
            with open(path, "wb") as handle:
                handle.write(config)
            self._stop_process()
            self.process = subprocess.Popen([ovpn, "--config", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.config_path = path
            self.connected = True
            self.after(0, lambda: self.status.set(f"Connecting to {server.get('city', server.get('country', 'server'))}…"))
        except Exception as exc:
            self.after(0, lambda: messagebox.showerror(APP_NAME, str(exc)))
            self.after(0, lambda: self.status.set("Connection failed"))

    def connect_wireguard(self, server):
        wg = wireguard_path()
        if not wg:
            messagebox.showerror(APP_NAME, "WireGuard for Windows is not installed.")
            return
        if not server.get("config_url"):
            messagebox.showwarning(APP_NAME, "This WireGuard server has no client configuration yet.")
            return
        self.status.set("Downloading WireGuard configuration…")
        threading.Thread(target=self._wireguard_worker, args=(wg, server), daemon=True).start()

    def _wireguard_worker(self, wg, server):
        try:
            config = download_config(server["config_url"]).decode("utf-8")
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
            self.after(0, lambda: self.status.set(f"Connected to {server.get('city', server.get('country', 'server'))}"))
        except Exception as exc:
            self.after(0, lambda: messagebox.showerror(APP_NAME, str(exc)))
            self.after(0, lambda: self.status.set("Connection failed"))

    def _stop_process(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
        self.process = None

    def disconnect(self):
        if not is_admin():
            if relaunch_as_admin():
                self.destroy()
            return
        wg = wireguard_path()
        if wg:
            subprocess.run([wg, "/uninstalltunnelservice", TUNNEL_NAME], capture_output=True)
        self._stop_process()
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
