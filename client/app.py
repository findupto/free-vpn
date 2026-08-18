import ctypes
import csv
import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import zipfile
import tkinter as tk
from tkinter import messagebox, ttk

API_URL = os.environ.get("FINDUPTO_API_URL", "https://findupto-free-vpn.onrender.com")
VPN_GATE_URLS = ["https://www.vpngate.net/api/iphone/", "http://www.vpngate.net/api/iphone/"]
APP_NAME = "Findupto Free VPN"
TUNNEL_NAME = "FinduptoVPN"
CACHE_FILE = os.path.join(os.environ.get("LOCALAPPDATA", tempfile.gettempdir()), "Findupto", "servers.json")


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
        params = " ".join(f'"{arg}"' for arg in (sys.argv[1:] if getattr(sys, "frozen", False) else sys.argv))
        return ctypes.windll.shell32.ShellExecuteW(None, "runas", executable, params, None, 1) > 32
    except Exception:
        return False


def _find_executable(name, folders):
    for base in folders:
        path = os.path.join(base, name)
        if os.path.isfile(path):
            return path
    return None


def wireguard_path():
    return _find_executable("wireguard.exe", [os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "WireGuard"), os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), "WireGuard")])


def openvpn_path():
    return _find_executable("openvpn.exe", [os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "OpenVPN", "bin"), os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), "OpenVPN", "bin")])


def _download(url, timeout=8):
    request = urllib.request.Request(url, headers={"User-Agent": "Findupto-Free-VPN/0.6"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def parse_vpngate_csv(text):
    lines = text.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    header_index = next((i for i, line in enumerate(lines) if line.startswith("#HostName,")), None)
    if header_index is None:
        raise RuntimeError("VPN Gate returned an unexpected server-list format.")
    header = lines[header_index][1:]
    data_lines = [line for line in lines[header_index + 1:] if line.strip() and not line.startswith("#") and not line.startswith("*")]
    reader = csv.DictReader(io.StringIO("\n".join([header] + data_lines)))
    servers = []
    for row in reader:
        ip = (row.get("IP") or "").strip()
        country = (row.get("CountryLong") or row.get("CountryShort") or "").strip()
        if not ip or not country:
            continue
        try: ping = float(row.get("Ping") or "")
        except (TypeError, ValueError): ping = None
        try: speed = float(row.get("Speed") or "") / 1_000_000
        except (TypeError, ValueError): speed = None
        try: score = int(float(row.get("Score") or 0))
        except (TypeError, ValueError): score = 0
        if ping is not None and ping > 500:
            continue
        servers.append({
            "id": f"vpngate-{ip}", "country": country, "city": (row.get("City") or "Unknown").strip() or "Unknown",
            "hostname": (row.get("HostName") or "").strip(), "ip": ip, "protocol": "openvpn",
            "ping_ms": ping, "speed_mbps": speed, "score": score, "source": "VPN Gate",
            "config_url": f"https://www.vpngate.net/common/openvpn_download.aspx?ip={ip}",
        })
    servers.sort(key=lambda s: (s.get("ping_ms") if s.get("ping_ms") is not None else 9999, -(s.get("speed_mbps") or 0), -(s.get("score") or 0)))
    return servers[:100]


def save_cache(servers):
    try:
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump({"time": time.time(), "servers": servers}, f)
    except OSError:
        pass


def load_cache(max_age=1800):
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if time.time() - float(data.get("time", 0)) <= max_age and isinstance(data.get("servers"), list):
            return data["servers"]
    except (OSError, ValueError, TypeError):
        pass
    return []


def fetch_servers():
    # Fast path: the API is cached server-side. A 4-second cap prevents a slow API
    # deployment from blocking the client.
    try:
        raw = _download(API_URL.rstrip("/") + "/api/v1/public/servers?limit=100", timeout=4)
        result = json.loads(raw.decode("utf-8"))
        if isinstance(result, list) and result:
            save_cache(result)
            return result
    except Exception:
        pass

    cached = load_cache()
    if cached:
        return cached

    last_error = None
    for url in VPN_GATE_URLS:
        try:
            servers = parse_vpngate_csv(_download(url, timeout=8).decode("utf-8-sig", errors="replace"))
            if servers:
                save_cache(servers)
                return servers
            last_error = RuntimeError("VPN Gate returned no usable servers.")
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"Unable to load free servers: {last_error}")


def download_config(url):
    return _download(url, timeout=15)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("1080x640")
        self.minsize(850, 520)
        self.configure(padx=18, pady=18)
        self.servers = []
        self.connected = False
        self.config_path = None
        self.process = None
        self.build_ui()
        self.refresh()

    def build_ui(self):
        ttk.Label(self, text=APP_NAME, font=("Segoe UI", 20, "bold")).pack(anchor="w")
        ttk.Label(self, text="Fast server discovery • OpenVPN + WireGuard • Automatic fallback").pack(anchor="w", pady=(2, 14))
        frame = ttk.Frame(self); frame.pack(fill="both", expand=True)
        columns = ("country", "city", "ip", "protocol", "ping", "speed", "source")
        self.tree = ttk.Treeview(frame, columns=columns, show="headings", height=17)
        for col, title, width in [("country","Country",150),("city","City",140),("ip","IP Address",125),("protocol","Protocol",90),("ping","Ping",75),("speed","Speed",95),("source","Source",120)]:
            self.tree.heading(col, text=title); self.tree.column(col, width=width, anchor="w")
        self.tree.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview); scroll.pack(side="right", fill="y"); self.tree.configure(yscrollcommand=scroll.set)
        buttons = ttk.Frame(self); buttons.pack(fill="x", pady=(14, 8))
        ttk.Button(buttons, text="Refresh Servers", command=self.refresh).pack(side="left")
        ttk.Button(buttons, text="Best Server", command=self.connect_best).pack(side="left", padx=8)
        self.connect_btn = ttk.Button(buttons, text="Connect", command=self.connect); self.connect_btn.pack(side="left")
        ttk.Button(buttons, text="Disconnect", command=self.disconnect).pack(side="left", padx=8)
        self.status = tk.StringVar(value="Finding free servers…"); ttk.Label(self, textvariable=self.status).pack(anchor="w")

    def refresh(self):
        self.status.set("Loading servers…")
        threading.Thread(target=self._refresh_worker, daemon=True).start()

    def _refresh_worker(self):
        try:
            servers = fetch_servers(); self.after(0, lambda: self._show_servers(servers))
        except Exception as exc:
            self.after(0, lambda: self.status.set(f"Unable to load servers: {exc}"))

    def _show_servers(self, servers):
        self.servers = servers
        for item in self.tree.get_children(): self.tree.delete(item)
        for index, server in enumerate(servers):
            ping = f"{server['ping_ms']:.0f} ms" if server.get("ping_ms") is not None else "-"
            speed = f"{server['speed_mbps']:.1f} Mbps" if server.get("speed_mbps") is not None else "-"
            self.tree.insert("", "end", iid=str(index), values=(server.get("country",""), server.get("city","Unknown"), server.get("ip",""), server.get("protocol","").upper(), ping, speed, server.get("source","")))
        if servers: self.tree.selection_set("0")
        self.status.set(f"{len(servers)} server(s) ready")

    def selected_server(self, silent=False):
        selection = self.tree.selection()
        if not selection:
            if not silent: messagebox.showinfo(APP_NAME, "Select a server first.")
            return None
        return self.servers[int(selection[0])]

    def connect_best(self):
        if not self.servers:
            return messagebox.showinfo(APP_NAME, "No servers are available yet.")
        self.tree.selection_set("0"); self.tree.see("0"); self.connect()

    def connect(self):
        if not sys.platform.startswith("win"): return messagebox.showerror(APP_NAME, "Windows is required for VPN connections.")
        server = self.selected_server()
        if not server: return
        if not is_admin():
            if relaunch_as_admin(): self.destroy()
            else: messagebox.showerror(APP_NAME, "Administrator permission is required to create the VPN tunnel.")
            return
        protocol = server.get("protocol", "").lower()
        if protocol == "openvpn": self.connect_openvpn(server)
        elif protocol == "wireguard": self.connect_wireguard(server)
        else: messagebox.showerror(APP_NAME, f"Unsupported VPN protocol: {protocol or 'unknown'}")

    def connect_openvpn(self, server):
        ovpn = openvpn_path()
        if not ovpn:
            messagebox.showerror(APP_NAME, "OpenVPN is missing. Re-run the Findupto installer and make sure OpenVPN Community is installed.")
            return
        self.status.set(f"Preparing {server.get('city', 'server')}…")
        threading.Thread(target=self._openvpn_worker, args=(ovpn, server), daemon=True).start()

    def _openvpn_worker(self, ovpn, server):
        path = None
        try:
            data = download_config(server["config_url"])
            if data.startswith(b"PK"):
                with zipfile.ZipFile(io.BytesIO(data)) as archive:
                    configs = [n for n in archive.namelist() if n.lower().endswith(".ovpn")]
                    if not configs: raise RuntimeError("No OpenVPN configuration was provided.")
                    config = archive.read(configs[0])
            else: config = data
            fd, path = tempfile.mkstemp(prefix="findupto-", suffix=".ovpn"); os.close(fd)
            with open(path, "wb") as handle: handle.write(config)
            self._stop_process()
            log_path = path + ".log"
            log = open(log_path, "w", encoding="utf-8", errors="replace")
            self.process = subprocess.Popen([ovpn, "--config", path, "--log", log_path, "--auth-nocache"], stdout=log, stderr=log, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            self.config_path = path; self.connected = True
            self.after(0, lambda: self.status.set(f"Connecting to {server.get('city', server.get('country', 'server'))}…"))
            threading.Thread(target=self._watch_openvpn, args=(server, log), daemon=True).start()
        except Exception as exc:
            if path:
                try: os.remove(path)
                except OSError: pass
            self.after(0, lambda: messagebox.showerror(APP_NAME, str(exc))); self.after(0, lambda: self.status.set("Connection failed"))

    def _watch_openvpn(self, server, log):
        if not self.process: return
        code = self.process.wait(); log.close()
        if self.connected:
            self.after(0, lambda: self.status.set(f"VPN stopped (exit code {code})"))
            self.connected = False

    def connect_wireguard(self, server):
        wg = wireguard_path()
        if not wg: return messagebox.showerror(APP_NAME, "WireGuard for Windows is missing. Re-run the Findupto installer.")
        if not server.get("config_url"): return messagebox.showwarning(APP_NAME, "This WireGuard server has no client configuration.")
        self.status.set("Preparing WireGuard…"); threading.Thread(target=self._wireguard_worker, args=(wg, server), daemon=True).start()

    def _wireguard_worker(self, wg, server):
        path = None
        try:
            config = download_config(server["config_url"]).decode("utf-8")
            fd, path = tempfile.mkstemp(prefix="findupto-", suffix=".conf"); os.close(fd)
            with open(path, "w", encoding="utf-8") as handle: handle.write(config)
            subprocess.run([wg, "/uninstalltunnelservice", TUNNEL_NAME], capture_output=True, timeout=15)
            result = subprocess.run([wg, "/installtunnelservice", path], capture_output=True, text=True, timeout=30)
            if result.returncode != 0: raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "WireGuard failed to start")
            self.config_path = path; self.connected = True
            self.after(0, lambda: self.status.set(f"Connected to {server.get('city', server.get('country', 'server'))}"))
        except Exception as exc:
            if path:
                try: os.remove(path)
                except OSError: pass
            self.after(0, lambda: messagebox.showerror(APP_NAME, str(exc))); self.after(0, lambda: self.status.set("Connection failed"))

    def _stop_process(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try: self.process.wait(timeout=5)
            except subprocess.TimeoutExpired: self.process.kill()
        self.process = None

    def disconnect(self):
        if not is_admin():
            if relaunch_as_admin(): self.destroy()
            return
        wg = wireguard_path()
        if wg: subprocess.run([wg, "/uninstalltunnelservice", TUNNEL_NAME], capture_output=True)
        self._stop_process(); self.connected = False
        if self.config_path:
            try: os.remove(self.config_path)
            except OSError: pass
            self.config_path = None
        self.status.set("Disconnected")


if __name__ == "__main__":
    App().mainloop()
