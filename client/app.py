import ctypes
import csv
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import zipfile
import winreg
import tkinter as tk
from tkinter import messagebox, ttk

APP_NAME = "Findupto Free VPN"
APP_VERSION = "0.9.0"
API_URL = os.environ.get("FINDUPTO_API_URL", "https://findupto-free-vpn.onrender.com")
OPENVPN_INSTALLER_URLS = [
    os.environ.get("FINDUPTO_OPENVPN_INSTALLER_URL", "https://swupdate.openvpn.org/community/releases/OpenVPN-2.7.5-I001-amd64.msi"),
    "https://swupdate.openvpn.org/community/releases/OpenVPN-2.7.4-I001-amd64.msi",
]
VPN_GATE_URLS = [
    "https://www.vpngate.net/api/iphone/",
    "https://vpngate.net/api/iphone/",
    "http://www.vpngate.net/api/iphone/",
    "http://vpngate.net/api/iphone/",
]
TUNNEL_NAME = "FinduptoVPN"
BASE_DIR = os.path.dirname(sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__))
DATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA", tempfile.gettempdir()), "Findupto")
CACHE_FILE = os.path.join(DATA_DIR, "servers.json")
LOG_FILE = os.path.join(DATA_DIR, "findupto.log")


def log(message):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8", errors="replace") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
    except OSError:
        pass


def is_windows():
    return sys.platform.startswith("win")


def is_admin():
    if not is_windows():
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin():
    if is_admin():
        return True
    try:
        executable = sys.executable
        args = sys.argv if not getattr(sys, "frozen", False) else sys.argv[1:]
        params = " ".join('"' + str(a).replace('"', '\\"') + '"' for a in args)
        rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", executable, params, BASE_DIR, 1)
        return rc > 32
    except Exception as exc:
        log(f"Elevation failed: {exc}")
        return False


def _which(name):
    try:
        return shutil.which(name)
    except Exception:
        return None


def _candidate_executables(name):
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    pf32 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    pd = os.environ.get("ProgramData", r"C:\ProgramData")
    local = os.environ.get("LOCALAPPDATA", "")
    candidates = []
    if name.lower() == "openvpn.exe":
        roots = [
            os.path.join(pf, "OpenVPN"), os.path.join(pf32, "OpenVPN"),
            os.path.join(pd, "OpenVPN"), os.path.join(local, "OpenVPN"),
        ]
        for root in roots:
            candidates.extend([os.path.join(root, "bin", name), os.path.join(root, name)])
    else:
        roots = [os.path.join(pf, "WireGuard"), os.path.join(pf32, "WireGuard"), os.path.join(local, "WireGuard")]
        for root in roots:
            candidates.append(os.path.join(root, name))
    return candidates


def _registry_install_locations(product_words):
    found = []
    uninstall_roots = [
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
        r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
    ]
    roots = [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]
    for root in roots:
        for uninstall_root in uninstall_roots:
            try:
                with winreg.OpenKey(root, uninstall_root) as parent:
                    count = winreg.QueryInfoKey(parent)[0]
                    for i in range(count):
                        try:
                            sub = winreg.EnumKey(parent, i)
                            with winreg.OpenKey(parent, sub) as key:
                                name = str(winreg.QueryValueEx(key, "DisplayName")[0])
                                if not any(w.lower() in name.lower() for w in product_words):
                                    continue
                                for value_name in ("InstallLocation", "InstallDir", "Path"):
                                    try:
                                        value = winreg.QueryValueEx(key, value_name)[0]
                                        if isinstance(value, str) and value:
                                            found.append(value)
                                    except OSError:
                                        pass
                        except OSError:
                            continue
            except OSError:
                continue
    return found


def openvpn_path():
    seen = set()
    candidates = _candidate_executables("openvpn.exe")
    candidates += [os.path.join(p, "bin", "openvpn.exe") for p in _registry_install_locations(["OpenVPN"]) ]
    candidates += [os.path.join(p, "openvpn.exe") for p in _registry_install_locations(["OpenVPN"]) ]
    candidates.append(_which("openvpn.exe"))
    for path in candidates:
        if not path or path in seen:
            continue
        seen.add(path)
        if os.path.isfile(path):
            return path
    return None


def wireguard_path():
    candidates = _candidate_executables("wireguard.exe")
    candidates.append(_which("wireguard.exe"))
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    return None


def _powershell_download(url, destination):
    scripts = [
        "$ProgressPreference='SilentlyContinue'; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -UseBasicParsing -Uri '%s' -OutFile '%s'" % (url.replace("'", "''"), destination.replace("'", "''")),
        "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; (New-Object Net.WebClient).DownloadFile('%s','%s')" % (url.replace("'", "''"), destination.replace("'", "''")),
    ]
    last = None
    for script in scripts:
        try:
            r = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script], capture_output=True, text=True, timeout=90)
            if r.returncode == 0 and os.path.isfile(destination) and os.path.getsize(destination) > 0:
                return True
            last = (r.stderr or r.stdout or "").strip()
        except Exception as exc:
            last = str(exc)
    raise RuntimeError(last or "PowerShell download failed")


def _curl_download(url, destination):
    curl = _which("curl.exe") or _which("curl")
    if not curl:
        raise RuntimeError("curl.exe is not available")
    r = subprocess.run([curl, "--fail", "--location", "--retry", "3", "--retry-delay", "2", "--connect-timeout", "15", "--max-time", "120", "-A", "Findupto-Free-VPN/0.9", "-o", destination, url], capture_output=True, text=True, timeout=140)
    if r.returncode != 0 or not os.path.isfile(destination) or os.path.getsize(destination) == 0:
        raise RuntimeError((r.stderr or r.stdout or "curl failed").strip())
    return True


def download_file(url, destination, allow_http=True):
    """Download using several Windows-native methods without disabling TLS verification."""
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    errors = []
    request = urllib.request.Request(url, headers={"User-Agent": f"Findupto-Free-VPN/{APP_VERSION}", "Accept": "*/*"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response, open(destination, "wb") as out:
            shutil.copyfileobj(response, out)
        if os.path.getsize(destination) > 0:
            return destination
    except Exception as exc:
        errors.append("urllib: " + str(exc))
        log(errors[-1])
    for method in (_curl_download, _powershell_download):
        try:
            method(url, destination)
            if os.path.getsize(destination) > 0:
                return destination
        except Exception as exc:
            errors.append(method.__name__ + ": " + str(exc))
            log(errors[-1])
    if allow_http and url.lower().startswith("https://"):
        http_url = "http://" + url[8:]
        try:
            request = urllib.request.Request(http_url, headers={"User-Agent": f"Findupto-Free-VPN/{APP_VERSION}"})
            with urllib.request.urlopen(request, timeout=30) as response, open(destination, "wb") as out:
                shutil.copyfileobj(response, out)
            if os.path.getsize(destination) > 0:
                return destination
        except Exception as exc:
            errors.append("http fallback: " + str(exc))
            log(errors[-1])
    raise RuntimeError("Download failed using all methods: " + " | ".join(errors[-4:]))


def download_bytes(url, timeout=25):
    fd, path = tempfile.mkstemp(prefix="findupto-net-")
    os.close(fd)
    try:
        download_file(url, path)
        with open(path, "rb") as f:
            return f.read()
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def ensure_openvpn():
    existing = openvpn_path()
    if existing:
        log(f"OpenVPN found: {existing}")
        return existing
    if not is_windows():
        raise RuntimeError("Windows is required for VPN connections.")
    if not is_admin():
        raise PermissionError("Administrator permission is required to install OpenVPN.")

    local_candidates = [
        os.path.join(BASE_DIR, "openvpn-amd64.msi"),
        os.path.join(BASE_DIR, "installer", "openvpn-amd64.msi"),
        os.path.join(os.path.dirname(BASE_DIR), "installer", "openvpn-amd64.msi"),
    ]
    installer = next((p for p in local_candidates if os.path.isfile(p) and os.path.getsize(p) > 1_000_000), None)
    temp_dir = tempfile.mkdtemp(prefix="findupto-openvpn-")
    try:
        if not installer:
            installer = os.path.join(temp_dir, "openvpn.msi")
            errors = []
            for url in OPENVPN_INSTALLER_URLS:
                try:
                    log(f"Downloading OpenVPN MSI: {url}")
                    download_file(url, installer, allow_http=False)
                    if os.path.getsize(installer) >= 1_000_000:
                        break
                except Exception as exc:
                    errors.append(str(exc))
                    try: os.remove(installer)
                    except OSError: pass
            else:
                raise RuntimeError("Unable to download the official OpenVPN installer. " + " | ".join(errors[-2:]))

        log(f"Installing OpenVPN from {installer}")
        log_path = os.path.join(temp_dir, "openvpn-msi.log")
        result = subprocess.run(["msiexec.exe", "/i", installer, "/qn", "/norestart", "/L*v", log_path], capture_output=True, text=True, timeout=240)
        log(f"OpenVPN MSI exit code: {result.returncode}")
        if result.returncode not in (0, 3010):
            detail = (result.stderr or result.stdout or "").strip()
            if os.path.isfile(log_path):
                try:
                    with open(log_path, "r", encoding="utf-16", errors="ignore") as f:
                        lines = f.readlines()[-30:]
                    detail += "\n" + "".join(lines)
                except OSError:
                    pass
            raise RuntimeError(f"OpenVPN installation failed (MSI {result.returncode}).\n{detail[-3500:]}")

        for _ in range(45):
            found = openvpn_path()
            if found:
                return found
            time.sleep(1)
        raise RuntimeError("OpenVPN installer completed, but openvpn.exe is not visible yet. Windows may require a restart. See log: " + LOG_FILE)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def parse_vpngate_csv(text):
    lines = text.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    header_index = next((i for i, line in enumerate(lines) if line.startswith("#HostName,")), None)
    if header_index is None:
        raise RuntimeError("VPN Gate returned an unexpected server-list format.")
    header = lines[header_index][1:]
    data_lines = [line for line in lines[header_index + 1:] if line.strip() and not line.startswith("#") and not line.startswith("*")]
    servers = []
    for row in csv.DictReader(io.StringIO("\n".join([header] + data_lines))):
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
        if ping is not None and ping > 500: continue
        servers.append({"id": f"vpngate-{ip}", "country": country, "city": (row.get("City") or "Unknown").strip() or "Unknown", "hostname": (row.get("HostName") or "").strip(), "ip": ip, "protocol": "openvpn", "ping_ms": ping, "speed_mbps": speed, "score": score, "source": "VPN Gate", "config_url": f"https://www.vpngate.net/common/openvpn_download.aspx?ip={ip}"})
    servers.sort(key=lambda s: (s.get("ping_ms") if s.get("ping_ms") is not None else 9999, -(s.get("speed_mbps") or 0), -(s.get("score") or 0)))
    return servers[:100]


def save_cache(servers):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f: json.dump({"time": time.time(), "servers": servers}, f)
    except OSError: pass


def load_cache(max_age=1800):
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f: data = json.load(f)
        if time.time() - float(data.get("time", 0)) <= max_age and isinstance(data.get("servers"), list): return data["servers"]
    except (OSError, ValueError, TypeError): pass
    return []


def fetch_servers():
    api_urls = [API_URL.rstrip("/") + "/api/v1/public/servers?limit=100", API_URL.rstrip("/") + "/api/v1/public/servers"]
    errors = []
    for url in api_urls:
        try:
            result = json.loads(download_bytes(url, 15).decode("utf-8"))
            if isinstance(result, list) and result:
                save_cache(result); return result
        except Exception as exc: errors.append(str(exc))
    cached = load_cache()
    if cached: return cached
    for url in VPN_GATE_URLS:
        try:
            servers = parse_vpngate_csv(download_bytes(url, 20).decode("utf-8-sig", errors="replace"))
            if servers: save_cache(servers); return servers
        except Exception as exc: errors.append(str(exc)); log(f"Server source failed: {url}: {exc}")
    raise RuntimeError("Unable to load free servers. " + " | ".join(errors[-3:]))


def download_config(url):
    return download_bytes(url, 30)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} {APP_VERSION}")
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
        ttk.Label(self, text="Multi-method networking • automatic OpenVPN repair • Windows native fallbacks").pack(anchor="w", pady=(2, 14))
        frame = ttk.Frame(self); frame.pack(fill="both", expand=True)
        columns = ("country", "city", "ip", "protocol", "ping", "speed", "source")
        self.tree = ttk.Treeview(frame, columns=columns, show="headings", height=17)
        for col, title, width in [("country", "Country", 150), ("city", "City", 140), ("ip", "IP Address", 125), ("protocol", "Protocol", 90), ("ping", "Ping", 75), ("speed", "Speed", 95), ("source", "Source", 120)]:
            self.tree.heading(col, text=title); self.tree.column(col, width=width, anchor="w")
        self.tree.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview); scroll.pack(side="right", fill="y"); self.tree.configure(yscrollcommand=scroll.set)
        buttons = ttk.Frame(self); buttons.pack(fill="x", pady=(14, 8))
        for text, command in [("Refresh Servers", self.refresh), ("Best Server", self.connect_best), ("Connect", self.connect), ("Disconnect", self.disconnect), ("Diagnostics", self.diagnostics)]:
            ttk.Button(buttons, text=text, command=command).pack(side="left", padx=(0, 8))
        self.status = tk.StringVar(value="Finding free servers…"); ttk.Label(self, textvariable=self.status).pack(anchor="w")

    def refresh(self):
        self.status.set("Loading servers using multiple network methods…")
        threading.Thread(target=self._refresh_worker, daemon=True).start()

    def _refresh_worker(self):
        try: self.after(0, lambda: self._show_servers(fetch_servers()))
        except Exception as exc: self.after(0, lambda: self.status.set(f"Unable to load servers: {exc}"))

    def _show_servers(self, servers):
        self.servers = servers
        for item in self.tree.get_children(): self.tree.delete(item)
        for i, s in enumerate(servers):
            ping = f"{s['ping_ms']:.0f} ms" if s.get("ping_ms") is not None else "-"
            speed = f"{s['speed_mbps']:.1f} Mbps" if s.get("speed_mbps") is not None else "-"
            self.tree.insert("", "end", iid=str(i), values=(s.get("country", ""), s.get("city", "Unknown"), s.get("ip", ""), s.get("protocol", "").upper(), ping, speed, s.get("source", "")))
        if servers: self.tree.selection_set("0")
        self.status.set(f"{len(servers)} server(s) ready")

    def selected_server(self):
        selection = self.tree.selection()
        if not selection: messagebox.showinfo(APP_NAME, "Select a server first."); return None
        return self.servers[int(selection[0])]

    def connect_best(self):
        if not self.servers: messagebox.showinfo(APP_NAME, "No servers are available yet."); return
        self.tree.selection_set("0"); self.tree.see("0"); self.connect()

    def connect(self):
        if not is_windows(): messagebox.showerror(APP_NAME, "Windows is required for VPN connections."); return
        server = self.selected_server()
        if not server: return
        if not is_admin():
            if relaunch_as_admin(): self.destroy()
            else: messagebox.showerror(APP_NAME, "Administrator permission is required to create the VPN tunnel.")
            return
        if server.get("protocol", "").lower() == "openvpn": self.connect_openvpn(server)
        else: messagebox.showerror(APP_NAME, "Unsupported VPN protocol: " + str(server.get("protocol", "unknown")))

    def connect_openvpn(self, server):
        self.status.set("Checking and repairing OpenVPN runtime…")
        threading.Thread(target=self._prepare_openvpn, args=(server,), daemon=True).start()

    def _prepare_openvpn(self, server):
        try:
            ovpn = ensure_openvpn(); self.after(0, lambda: self._start_openvpn(ovpn, server))
        except Exception as exc:
            log(f"OpenVPN prepare failed: {exc}")
            self.after(0, lambda: messagebox.showerror(APP_NAME, f"OpenVPN could not be installed or found.\n\n{exc}\n\nDiagnostics log:\n{LOG_FILE}"))
            self.after(0, lambda: self.status.set("OpenVPN runtime unavailable"))

    def _start_openvpn(self, ovpn, server):
        self.status.set(f"Downloading VPN configuration for {server.get('city', 'server')}…")
        threading.Thread(target=self._openvpn_worker, args=(ovpn, server), daemon=True).start()

    def _openvpn_worker(self, ovpn, server):
        path = None
        try:
            data = download_config(server["config_url"])
            if data.startswith(b"PK"):
                with zipfile.ZipFile(io.BytesIO(data)) as archive:
                    configs = [n for n in archive.namelist() if n.lower().endswith(".ovpn")]
                    if not configs: raise RuntimeError("No OpenVPN configuration was provided by the server.")
                    config = archive.read(configs[0])
            else: config = data
            if b"client" not in config.lower(): raise RuntimeError("Downloaded configuration is not a valid OpenVPN profile.")
            fd, path = tempfile.mkstemp(prefix="findupto-", suffix=".ovpn"); os.close(fd)
            with open(path, "wb") as f: f.write(config)
            self._stop_process()
            log_path = path + ".log"
            self.process = subprocess.Popen([ovpn, "--config", path, "--log", log_path, "--auth-nocache"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            self.config_path = path; self.connected = True
            self.after(0, lambda: self.status.set(f"Connecting to {server.get('city', server.get('country', 'server'))}…"))
            threading.Thread(target=self._watch_openvpn, daemon=True).start()
        except Exception as exc:
            log(f"OpenVPN connection failed: {exc}")
            if path:
                try: os.remove(path)
                except OSError: pass
            self.after(0, lambda: messagebox.showerror(APP_NAME, f"Connection failed.\n\n{exc}\n\nLog: {LOG_FILE}")); self.after(0, lambda: self.status.set("Connection failed"))

    def _watch_openvpn(self):
        process = self.process
        if not process: return
        code = process.wait()
        if self.connected:
            self.connected = False; self.after(0, lambda: self.status.set(f"VPN stopped (exit code {code})"))

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
        self._stop_process(); self.connected = False
        if self.config_path:
            try: os.remove(self.config_path)
            except OSError: pass
            self.config_path = None
        self.status.set("Disconnected")

    def diagnostics(self):
        info = [f"Findupto {APP_VERSION}", f"Admin: {is_admin()}", f"OpenVPN: {openvpn_path() or 'NOT FOUND'}", f"WireGuard: {wireguard_path() or 'NOT FOUND'}", f"curl: {_which('curl.exe') or _which('curl') or 'NOT FOUND'}", f"PowerShell: {_which('powershell.exe') or 'NOT FOUND'}", f"Log: {LOG_FILE}"]
        messagebox.showinfo(APP_NAME + " Diagnostics", "\n".join(info))


if __name__ == "__main__":
    App().mainloop()
