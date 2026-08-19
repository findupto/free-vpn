import base64
import ctypes
import csv
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import zipfile
import winreg
import tkinter as tk
from tkinter import messagebox, ttk

APP_NAME = "Findupto Free VPN"
APP_VERSION = "2.0.0"
DATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA", tempfile.gettempdir()), "Findupto")
CACHE_FILE = os.path.join(DATA_DIR, "servers.json")
LOG_FILE = os.path.join(DATA_DIR, "findupto.log")
UA = f"Findupto-Free-VPN/{APP_VERSION}"
VPN_GATE_APIS = [
    "https://www.vpngate.net/api/iphone/",
    "https://download.vpngate.jp/api/iphone/",
    "https://vpngate.net/api/iphone/",
    "http://www.vpngate.net/api/iphone/",
]
OPENVPN_URLS = [
    "https://build.openvpn.net/downloads/releases/latest/openvpn-latest-stable-amd64.msi",
    "https://swupdate.openvpn.org/community/releases/OpenVPN-2.7.5-I001-amd64.msi",
    "https://swupdate.openvpn.org/community/releases/OpenVPN-2.7.4-I002-amd64.msi",
]

def log(msg):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8", errors="replace") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except OSError:
        pass

def which(name):
    return shutil.which(name)

def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False

def elevate():
    if is_admin():
        return True
    try:
        exe = sys.executable
        args = sys.argv if not getattr(sys, "frozen", False) else sys.argv[1:]
        params = " ".join('"' + str(a).replace('"', '\\"') + '"' for a in args)
        return ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, os.path.dirname(exe), 1) > 32
    except Exception as e:
        log(f"elevation failed: {e}")
        return False

def registry_openvpn_locations():
    out = []
    for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for parent in (r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall", r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"):
            try:
                with winreg.OpenKey(root, parent) as p:
                    for i in range(winreg.QueryInfoKey(p)[0]):
                        try:
                            with winreg.OpenKey(p, winreg.EnumKey(p, i)) as k:
                                name = str(winreg.QueryValueEx(k, "DisplayName")[0])
                                if "openvpn" not in name.lower():
                                    continue
                                for value in ("InstallLocation", "InstallDir", "Path"):
                                    try:
                                        v = winreg.QueryValueEx(k, value)[0]
                                        if isinstance(v, str): out.append(v)
                                    except OSError: pass
                        except OSError: pass
            except OSError: pass
    return out

def find_openvpn():
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    pf32 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    roots = [os.path.join(pf, "OpenVPN"), os.path.join(pf32, "OpenVPN")] + registry_openvpn_locations()
    candidates = []
    for root in roots:
        candidates += [os.path.join(root, "bin", "openvpn.exe"), os.path.join(root, "openvpn.exe")]
    candidates += [which("openvpn.exe"), which("openvpn")]
    for path in candidates:
        if path and os.path.isfile(path): return os.path.abspath(path)
    return None

def _curl(url, dst):
    exe = which("curl.exe") or which("curl")
    if not exe: raise RuntimeError("curl unavailable")
    # Keep arguments compatible with old Windows curl builds.
    cmd = [exe, "--fail", "--location", "--retry", "3", "--retry-delay", "1", "--connect-timeout", "8", "--max-time", "45", "-A", UA, "-o", dst, url]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if r.returncode: raise RuntimeError((r.stderr or r.stdout or "curl failed").strip())
    return os.path.getsize(dst)

def _powershell(url, dst):
    exe = which("powershell.exe") or which("pwsh.exe")
    if not exe: raise RuntimeError("PowerShell unavailable")
    u, d = url.replace("'", "''"), dst.replace("'", "''")
    script = f"$ProgressPreference='SilentlyContinue';[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12;Invoke-WebRequest -UseBasicParsing -Uri '{u}' -OutFile '{d}'"
    r = subprocess.run([exe, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script], capture_output=True, text=True, timeout=55)
    if r.returncode or not os.path.isfile(dst) or not os.path.getsize(dst):
        raise RuntimeError((r.stderr or r.stdout or "PowerShell failed").strip())
    return os.path.getsize(dst)

def _urllib(url, dst):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=18) as r, open(dst, "wb") as f:
        shutil.copyfileobj(r, f)
    return os.path.getsize(dst)

def download(url, dst, http_fallback=False):
    errors = []
    for method in (_curl, _powershell, _urllib):
        try:
            if os.path.exists(dst): os.remove(dst)
            if method(url, dst) > 0:
                log(f"download ok {method.__name__}: {url}")
                return dst
        except Exception as e:
            errors.append(f"{method.__name__}: {e}")
            log(errors[-1])
    if http_fallback and url.startswith("https://"):
        http = "http://" + url[8:]
        for method in (_curl, _powershell, _urllib):
            try:
                if os.path.exists(dst): os.remove(dst)
                if method(http, dst) > 0:
                    log(f"download ok HTTP {method.__name__}: {http}")
                    return dst
            except Exception as e:
                errors.append(f"{method.__name__} HTTP: {e}")
                log(errors[-1])
    raise RuntimeError("download failed: " + " | ".join(errors[-5:]))

def get_bytes(url, http_fallback=False):
    fd, path = tempfile.mkstemp(prefix="findupto-net-")
    os.close(fd)
    try:
        download(url, path, http_fallback)
        with open(path, "rb") as f: return f.read()
    finally:
        try: os.remove(path)
        except OSError: pass

def ensure_openvpn():
    found = find_openvpn()
    if found: return found
    if not is_admin(): raise PermissionError("Administrator permission is required for automatic OpenVPN installation.")
    base = os.path.dirname(sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__))
    local = [os.path.join(base, "openvpn-amd64.msi"), os.path.join(base, "installer", "openvpn-amd64.msi"), os.path.join(os.path.dirname(base), "installer", "openvpn-amd64.msi")]
    installer = next((p for p in local if os.path.isfile(p) and os.path.getsize(p) > 4000000), None)
    td = tempfile.mkdtemp(prefix="findupto-openvpn-")
    try:
        if not installer:
            installer = os.path.join(td, "openvpn.msi")
            errors = []
            for url in OPENVPN_URLS:
                try:
                    download(url, installer)
                    if os.path.getsize(installer) > 4000000: break
                except Exception as e: errors.append(str(e))
            else: raise RuntimeError("OpenVPN installer unavailable: " + " | ".join(errors[-3:]))
        msi_log = os.path.join(td, "openvpn-msi.log")
        r = subprocess.run(["msiexec.exe", "/i", installer, "/qn", "/norestart", "/L*v", msi_log], capture_output=True, text=True, timeout=300)
        log(f"OpenVPN MSI exit={r.returncode}")
        if r.returncode not in (0, 3010): raise RuntimeError(f"OpenVPN installation failed (MSI {r.returncode}).")
        for _ in range(60):
            found = find_openvpn()
            if found: return found
            time.sleep(.5)
        raise RuntimeError("OpenVPN installed but openvpn.exe was not found.")
    finally:
        shutil.rmtree(td, ignore_errors=True)

def parse_servers(text):
    lines = text.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    header_i = next((i for i, line in enumerate(lines) if line.startswith("#HostName,")), None)
    if header_i is None: raise RuntimeError("Invalid VPN Gate server list")
    fields = lines[header_i][1:].split(",")
    servers = []
    for raw in lines[header_i + 1:]:
        if not raw.strip() or raw.startswith("#") or raw.startswith("*"): continue
        try: row = next(csv.reader([raw]))
        except Exception: continue
        if len(row) < len(fields): continue
        d = dict(zip(fields, row))
        ip = (d.get("IP") or "").strip()
        b64 = (d.get("OpenVPN_ConfigData_Base64") or "").strip()
        if not ip or not b64: continue
        try: ping = float(d.get("Ping") or "")
        except Exception: ping = None
        try: speed = float(d.get("Speed") or 0) / 1000000
        except Exception: speed = 0
        try: score = int(float(d.get("Score") or 0))
        except Exception: score = 0
        servers.append({"ip": ip, "country": (d.get("CountryLong") or "Unknown").strip(), "ping_ms": ping, "speed_mbps": speed, "score": score, "config_b64": b64, "source": "VPN Gate"})
    servers.sort(key=lambda s: (s["ping_ms"] if s["ping_ms"] is not None else 99999, -s["speed_mbps"], -s["score"]))
    return servers[:150]

def save_cache(servers):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f: json.dump({"time": time.time(), "servers": servers}, f)
    except OSError: pass

def load_cache():
    try:
        with open(CACHE_FILE, encoding="utf-8") as f: d = json.load(f)
        if time.time() - float(d.get("time", 0)) < 900: return d.get("servers", [])
    except Exception: pass
    return []

def fetch_servers():
    errors = []
    # The broken Findupto /api/v1/public/servers endpoint is intentionally not used.
    for url in VPN_GATE_APIS:
        try:
            servers = parse_servers(get_bytes(url, url.startswith("https://")).decode("utf-8-sig", errors="replace"))
            if servers:
                save_cache(servers)
                return servers
        except Exception as e:
            errors.append(str(e)); log(f"server source failed: {url}: {e}")
    cached = load_cache()
    if cached: return cached
    raise RuntimeError("No VPN server source available: " + " | ".join(errors[-4:]))

def make_config(server, auth_path):
    raw = base64.b64decode(server["config_b64"] + "===")
    if raw[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            names = [n for n in z.namelist() if n.lower().endswith(".ovpn")]
            if not names: raise RuntimeError("VPN Gate archive has no .ovpn profile")
            raw = z.read(names[0])
    text = raw.decode("utf-8-sig", errors="replace")
    if "client" not in text.lower() or "remote " not in text.lower(): raise RuntimeError("Invalid OpenVPN profile")
    lines = []
    for line in text.splitlines():
        parts = line.strip().split()
        if len(parts) >= 3 and parts[0].lower() == "remote":
            line = "remote " + server["ip"] + " " + parts[2] + (" " + parts[3] if len(parts) >= 4 else "")
        lines.append(line)
    text = "\n".join(lines) + "\n"
    # VPN Gate's public credential is vpn/vpn. Never allow a GUI prompt in the background.
    if "auth-user-pass" not in text.lower(): text += f'auth-user-pass "{auth_path}"\n'
    else:
        text = "\n".join(line for line in text.splitlines() if not line.strip().lower().startswith("auth-user-pass")) + f'\nauth-user-pass "{auth_path}"\n'
    text += "resolv-retry infinite\nconnect-retry 2 5\nconnect-timeout 12\nverb 3\n"
    return text.encode("utf-8")

def config_port(config):
    for line in config.decode("utf-8", errors="replace").splitlines():
        p = line.split()
        if len(p) >= 3 and p[0].lower() == "remote":
            try: return int(p[2])
            except ValueError: pass
    return None

def tcp_reachable(ip, port):
    if not port: return True
    try:
        with socket.create_connection((ip, port), timeout=1.5): return True
    except OSError: return False

def openvpn_try(ovpn, server, auth_path):
    td = tempfile.mkdtemp(prefix="findupto-vpn-")
    config_path, log_path = os.path.join(td, "client.ovpn"), os.path.join(td, "openvpn.log")
    config = make_config(server, auth_path)
    with open(config_path, "wb") as f: f.write(config)
    p = subprocess.Popen([ovpn, "--config", config_path, "--log", log_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    deadline = time.time() + 30
    while time.time() < deadline:
        if p.poll() is not None: break
        try:
            with open(log_path, encoding="utf-8", errors="replace") as f: text = f.read()
            if "Initialization Sequence Completed" in text:
                return p, td
        except OSError: pass
        time.sleep(.4)
    try: p.terminate(); p.wait(timeout=3)
    except Exception:
        try: p.kill()
        except Exception: pass
    try:
        with open(log_path, encoding="utf-8", errors="replace") as f: detail = f.read()[-1600:]
    except OSError: detail = "No OpenVPN log available."
    shutil.rmtree(td, ignore_errors=True)
    raise RuntimeError(f"{server['ip']} failed: {detail}")

def l2tp_connect(server):
    ps = which("powershell.exe") or which("pwsh.exe")
    rasdial = which("rasdial.exe") or os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "rasdial.exe")
    if not ps or not os.path.isfile(rasdial): raise RuntimeError("Windows L2TP tools unavailable")
    name = "FinduptoVPN"
    ip = server["ip"].replace("'", "''")
    script = (f"$ErrorActionPreference='Stop';if(Get-VpnConnection -Name '{name}' -ErrorAction SilentlyContinue){{Remove-VpnConnection -Name '{name}' -Force -ErrorAction SilentlyContinue}};"
              f"Add-VpnConnection -Name '{name}' -ServerAddress '{ip}' -TunnelType L2tp -L2tpPsk 'vpn' -AuthenticationMethod MSChapv2 -EncryptionLevel Optional -RememberCredential -Force -SplitTunneling:$false")
    r = subprocess.run([ps, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script], capture_output=True, text=True, timeout=40)
    if r.returncode: raise RuntimeError((r.stderr or r.stdout or "L2TP setup failed").strip())
    r = subprocess.run([rasdial, name, "vpn", "vpn"], capture_output=True, text=True, timeout=45)
    if r.returncode: raise RuntimeError((r.stderr or r.stdout or "L2TP connection failed").strip())
    return name

class App(tk.Tk):
    def __init__(self):
        super().__init__(); self.title(f"{APP_NAME} {APP_VERSION}"); self.geometry("1080x650"); self.minsize(850, 520)
        self.servers=[]; self.process=None; self.vpn_mode=None; self.vpn_dir=None; self.build_ui(); threading.Thread(target=self.startup, daemon=True).start()
    def build_ui(self):
        ttk.Label(self, text=APP_NAME, font=("Segoe UI", 20, "bold")).pack(anchor="w")
        ttk.Label(self, text="Fast automatic VPN • OpenVPN multi-server failover • Windows L2TP fallback").pack(anchor="w", pady=(2,14))
        frame=ttk.Frame(self); frame.pack(fill="both", expand=True)
        cols=("country","ip","ping","speed","source"); self.tree=ttk.Treeview(frame, columns=cols, show="headings")
        for c,t,w in (("country","Country",260),("ip","IP",180),("ping","Ping",100),("speed","Speed",130),("source","Source",130)): self.tree.heading(c,text=t); self.tree.column(c,width=w)
        self.tree.pack(side="left", fill="both", expand=True); sb=ttk.Scrollbar(frame,orient="vertical",command=self.tree.yview); sb.pack(side="right",fill="y"); self.tree.configure(yscrollcommand=sb.set)
        b=ttk.Frame(self); b.pack(fill="x",pady=(14,8)); ttk.Button(b,text="Refresh",command=self.refresh).pack(side="left"); ttk.Button(b,text="⚡ Fast Connect",command=self.fast_connect).pack(side="left",padx=8); ttk.Button(b,text="Connect",command=self.connect).pack(side="left"); ttk.Button(b,text="Disconnect",command=self.disconnect).pack(side="left",padx=8); ttk.Button(b,text="Diagnostics",command=self.diagnostics).pack(side="right")
        self.status=tk.StringVar(value="Loading VPN servers…"); ttk.Label(self,textvariable=self.status).pack(anchor="w")
    def startup(self):
        try: self.after(0, lambda: self.show_servers(fetch_servers()))
        except Exception as e: log(f"startup: {e}"); self.after(0,lambda:self.status.set("Server discovery failed; retrying sources automatically is exhausted"))
    def refresh(self): self.status.set("Refreshing…"); threading.Thread(target=self.startup,daemon=True).start()
    def show_servers(self,servers):
        self.servers=servers
        for x in self.tree.get_children(): self.tree.delete(x)
        for i,s in enumerate(servers): self.tree.insert("","end",iid=str(i),values=(s["country"],s["ip"],"-" if s["ping_ms"] is None else f"{s['ping_ms']:.0f} ms",f"{s['speed_mbps']:.1f} Mbps",s["source"]))
        if servers:self.tree.selection_set("0")
        self.status.set(f"{len(servers)} servers ready")
    def selected(self):
        q=self.tree.selection(); return self.servers[int(q[0])] if q else None
    def fast_connect(self):
        if not self.servers:return
        if not is_admin():
            if elevate(): self.destroy()
            return
        self.status.set("Fast Connect: testing the best servers…"); threading.Thread(target=self.auto_connect,args=(self.servers[:12],),daemon=True).start()
    def connect(self):
        s=self.selected()
        if not s:return messagebox.showinfo(APP_NAME,"Select a server first.")
        if not is_admin():
            if elevate(): self.destroy()
            else: messagebox.showerror(APP_NAME,"Administrator permission is required.")
            return
        self.status.set("Connecting…"); threading.Thread(target=self.auto_connect,args=([s],),daemon=True).start()
    def auto_connect(self,candidates):
        try: ovpn=ensure_openvpn()
        except Exception as e: log(f"OpenVPN unavailable: {e}"); ovpn=None
        fd,auth=tempfile.mkstemp(prefix="findupto-auth-"); os.close(fd)
        try:
            with open(auth,"w",encoding="utf-8",newline="\n") as f:f.write("vpn\nvpn\n")
            ranked=sorted(candidates,key=lambda s:(s["ping_ms"] if s["ping_ms"] is not None else 99999,-s["speed_mbps"],-s["score"]))
            if ovpn:
                for s in ranked:
                    try:
                        cfg=make_config(s,auth); port=config_port(cfg)
                        if port and not tcp_reachable(s["ip"],port):
                            log(f"skip unreachable {s['ip']}:{port}"); continue
                        p,td=openvpn_try(ovpn,s,auth); self.process,self.vpn_dir,self.vpn_mode=p,td,"openvpn"; self.after(0,lambda ss=s:self.status.set(f"Connected • OpenVPN • {ss['country']} {ss['ip']}")); threading.Thread(target=self.watch,args=(p,s),daemon=True).start(); return
                    except Exception as e:
                        log(str(e)); self.after(0,lambda ss=s:self.status.set(f"{ss['ip']} failed — trying next server…"))
            for s in ranked[:5]:
                try:
                    l2tp_connect(s); self.vpn_mode="l2tp"; self.after(0,lambda ss=s:self.status.set(f"Connected • Windows L2TP • {ss['country']} {ss['ip']}")); return
                except Exception as e: log(f"L2TP {s['ip']}: {e}")
            self.after(0,lambda:messagebox.showerror(APP_NAME,"No tunnel could be established. Multiple servers and both OpenVPN/L2TP were tried. See Diagnostics/log.")); self.after(0,lambda:self.status.set("All automatic methods failed"))
        finally:
            try:os.remove(auth)
            except OSError:pass
    def watch(self,p,s):
        code=p.wait(); log(f"OpenVPN stopped {s['ip']} exit={code}"); self.after(0,lambda:self.status.set(f"VPN stopped (exit {code}) — choose Fast Connect to retry"))
    def disconnect(self):
        if not is_admin():
            if elevate(): self.destroy()
            return
        if self.vpn_mode=="l2tp":
            rasdial=which("rasdial.exe") or os.path.join(os.environ.get("SystemRoot",r"C:\Windows"),"System32","rasdial.exe")
            try:subprocess.run([rasdial,"FinduptoVPN","/disconnect"],capture_output=True,text=True,timeout=15)
            except Exception as e:log(f"L2TP disconnect: {e}")
        if self.process and self.process.poll() is None:
            try:self.process.terminate(); self.process.wait(timeout=5)
            except Exception:
                try:self.process.kill()
                except Exception:pass
        self.process=None; self.vpn_mode=None; shutil.rmtree(self.vpn_dir,ignore_errors=True) if self.vpn_dir else None; self.vpn_dir=None; self.status.set("Disconnected")
    def diagnostics(self):
        messagebox.showinfo("Diagnostics",f"OpenVPN: {find_openvpn() or 'NOT FOUND'}\ncurl: {which('curl.exe') or which('curl') or 'NOT FOUND'}\nPowerShell: {which('powershell.exe') or which('pwsh.exe') or 'NOT FOUND'}\nAdmin: {is_admin()}\nServers: {len(self.servers)}\nLog: {LOG_FILE}")

if __name__=="__main__": App().mainloop()
