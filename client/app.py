import base64
import csv
import ctypes
import io
import json
import os
import queue
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
APP_VERSION = "2.2.0"
DATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA", tempfile.gettempdir()), "Findupto")
CACHE_FILE = os.path.join(DATA_DIR, "servers.json")
LOG_FILE = os.path.join(DATA_DIR, "findupto.log")
UA = f"Findupto-Free-VPN/{APP_VERSION}"
VPN_GATE_SOURCES = ["https://www.vpngate.net/api/iphone/", "https://download.vpngate.jp/api/iphone/", "http://www.vpngate.net/api/iphone/"]
OPENVPN_URLS = ["https://build.openvpn.net/downloads/releases/latest/openvpn-latest-stable-amd64.msi", "https://swupdate.openvpn.org/community/releases/OpenVPN-2.7.5-I001-amd64.msi", "https://swupdate.openvpn.org/community/releases/OpenVPN-2.7.4-I002-amd64.msi"]


def log(msg):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8", errors="replace") as f: f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except OSError: pass


def which(name): return shutil.which(name)


def is_admin():
    try: return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception: return False


def elevate():
    if is_admin(): return True
    try:
        exe = sys.executable
        params = " ".join('"' + str(a).replace('"', '\\"') + '"' for a in sys.argv)
        return ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, os.path.dirname(exe), 1) > 32
    except Exception as e:
        log(f"elevation failed: {e}"); return False


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
                                if "openvpn" not in name.lower(): continue
                                for value in ("InstallLocation", "InstallDir", "Path"):
                                    try:
                                        v = winreg.QueryValueEx(k, value)[0]
                                        if isinstance(v, str): out.append(v)
                                    except OSError: pass
                        except OSError: pass
            except OSError: pass
    return out


def find_openvpn():
    pf, pf32 = os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    roots = [os.path.join(pf, "OpenVPN"), os.path.join(pf32, "OpenVPN"), *registry_openvpn_locations()]
    candidates = []
    for root in roots: candidates += [os.path.join(root, "bin", "openvpn.exe"), os.path.join(root, "openvpn.exe")]
    candidates += [which("openvpn.exe"), which("openvpn")]
    for path in candidates:
        if path and os.path.isfile(path): return os.path.abspath(path)
    return None


def _run_capture(cmd, timeout):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def _curl(url, dst, timeout=7):
    exe = which("curl.exe") or which("curl")
    if not exe: raise RuntimeError("curl unavailable")
    r = _run_capture([exe, "--silent", "--show-error", "--fail", "--location", "--connect-timeout", "3", "--max-time", str(timeout), "-A", UA, "-o", dst, url], timeout + 2)
    if r.returncode: raise RuntimeError((r.stderr or r.stdout or "curl failed").strip())
    if not os.path.isfile(dst) or not os.path.getsize(dst): raise RuntimeError("curl returned an empty file")
    return os.path.getsize(dst)


def _powershell(url, dst, timeout=7):
    exe = which("powershell.exe") or which("pwsh.exe")
    if not exe: raise RuntimeError("PowerShell unavailable")
    u, d = url.replace("'", "''"), dst.replace("'", "''")
    script = "$ProgressPreference='SilentlyContinue';[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12;" + f"Invoke-WebRequest -UseBasicParsing -Uri '{u}' -OutFile '{d}' -TimeoutSec {int(timeout)}"
    r = _run_capture([exe, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script], timeout + 3)
    if r.returncode or not os.path.isfile(dst) or not os.path.getsize(dst): raise RuntimeError((r.stderr or r.stdout or "PowerShell failed").strip())
    return os.path.getsize(dst)


def _urllib(url, dst, timeout=7):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r, open(dst, "wb") as f: shutil.copyfileobj(r, f)
    if not os.path.getsize(dst): raise RuntimeError("urllib returned an empty file")
    return os.path.getsize(dst)


def download(url, dst, software=False):
    errors = []
    for method in (_curl, _powershell, _urllib):
        try:
            if os.path.exists(dst): os.remove(dst)
            method(url, dst); log(f"download ok {method.__name__}: {url}"); return dst
        except Exception as e:
            text = str(e); errors.append(f"{method.__name__}: {text}"); log(f"{method.__name__}: {text}")
            if any(x in text.lower() for x in ("404", "not found", "410")): break
    raise RuntimeError("download failed: " + " | ".join(errors[-3:]))


def get_bytes(url):
    fd, path = tempfile.mkstemp(prefix="findupto-net-"); os.close(fd)
    try:
        download(url, path)
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
            for url in OPENVPN_URLS:
                try:
                    download(url, installer, software=True)
                    if os.path.getsize(installer) > 4000000: break
                except Exception as e: log(f"OpenVPN installer source failed: {url}: {e}")
            else: raise RuntimeError("OpenVPN installer could not be downloaded.")
        msi_log = os.path.join(td, "openvpn-msi.log")
        r = subprocess.run(["msiexec.exe", "/i", installer, "/qn", "/norestart", "/L*v", msi_log], capture_output=True, text=True, timeout=180, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        log(f"OpenVPN MSI exit={r.returncode}")
        if r.returncode not in (0, 3010): raise RuntimeError(f"OpenVPN installation failed (MSI {r.returncode}).")
        for _ in range(40):
            found = find_openvpn()
            if found: return found
            time.sleep(.5)
        raise RuntimeError("OpenVPN installed but openvpn.exe was not found.")
    finally: shutil.rmtree(td, ignore_errors=True)


def parse_servers(text):
    lines = text.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    header_i = next((i for i, line in enumerate(lines) if line.startswith("#HostName,")), None)
    if header_i is None: raise RuntimeError("Invalid VPN Gate server list")
    fields, servers = lines[header_i][1:].split(","), []
    for raw in lines[header_i + 1:]:
        if not raw.strip() or raw.startswith("#") or raw.startswith("*"): continue
        try: row = next(csv.reader([raw]))
        except Exception: continue
        if len(row) < len(fields): continue
        d = dict(zip(fields, row)); ip, b64 = (d.get("IP") or "").strip(), (d.get("OpenVPN_ConfigData_Base64") or "").strip()
        if not ip or not b64: continue
        try: ping = float(d.get("Ping") or "")
        except Exception: ping = None
        try: speed = float(d.get("Speed") or 0) / 1_000_000
        except Exception: speed = 0
        try: score = int(float(d.get("Score") or 0))
        except Exception: score = 0
        servers.append({"ip": ip, "country": (d.get("CountryLong") or "Unknown").strip(), "ping_ms": ping, "speed_mbps": speed, "score": score, "config_b64": b64, "source": "VPN Gate"})
    servers.sort(key=lambda s: (s["ping_ms"] if s["ping_ms"] is not None else 99999, -s["speed_mbps"], -s["score"]))
    return servers[:80]


def save_cache(servers):
    try:
        os.makedirs(DATA_DIR, exist_ok=True); tmp = CACHE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f: json.dump({"time": time.time(), "servers": servers}, f)
        os.replace(tmp, CACHE_FILE)
    except OSError: pass


def load_cache(max_age=21600):
    try:
        with open(CACHE_FILE, encoding="utf-8") as f: d = json.load(f)
        if time.time() - float(d.get("time", 0)) < max_age: return d.get("servers", [])
    except Exception: pass
    return []


def fetch_one_source(url, result_q):
    try:
        servers = parse_servers(get_bytes(url).decode("utf-8", errors="replace")); result_q.put(("ok", url, servers)) if servers else result_q.put(("bad", url, "empty"))
    except Exception as e: result_q.put(("bad", url, str(e)))


def fetch_servers():
    result_q = queue.Queue()
    for url in VPN_GATE_SOURCES: threading.Thread(target=fetch_one_source, args=(url, result_q), daemon=True).start()
    deadline, failures = time.monotonic() + 9, []
    while time.monotonic() < deadline:
        try: kind, url, value = result_q.get(timeout=.25)
        except queue.Empty: continue
        if kind == "ok": save_cache(value); log(f"server source selected: {url} ({len(value)} servers)"); return value
        failures.append(f"{url}: {value}")
    cached = load_cache()
    if cached: log("using cached VPN server list after source timeout"); return cached
    raise RuntimeError("No VPN server source available: " + " | ".join(failures[-3:]))


def decode_profile(server):
    raw = base64.b64decode(server["config_b64"] + "===")
    if raw[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            names = [n for n in z.namelist() if n.lower().endswith(".ovpn")]
            if not names: raise RuntimeError("VPN Gate archive has no .ovpn profile")
            raw = z.read(names[0])
    text = raw.decode("utf-8-sig", errors="replace")
    if "client" not in text.lower() or "remote " not in text.lower(): raise RuntimeError("Invalid OpenVPN profile")
    return text


def profile_variants(server):
    text = decode_profile(server); lines = text.splitlines(); remotes, default_proto = [], "udp"
    for line in lines:
        p = line.strip().split()
        if p and p[0].lower() == "proto" and len(p) >= 2: default_proto = "udp" if p[1].lower().startswith("udp") else "tcp-client"
        if len(p) >= 3 and p[0].lower() == "remote":
            try: port = int(p[2])
            except ValueError: continue
            explicit = p[3].lower() if len(p) >= 4 else default_proto
            remotes.append(("udp" if explicit.startswith("udp") else "tcp", port))

    def build(mode=None):
        out, had_remote = [], False
        for line in lines:
            p = line.strip().split()
            if p and p[0].lower() == "auth-user-pass": continue
            if len(p) >= 3 and p[0].lower() == "remote":
                had_remote = True
                if mode: proto, port = mode
                else:
                    explicit = p[3].lower() if len(p) >= 4 else default_proto
                    proto, port = ("udp" if explicit.startswith("udp") else "tcp"), int(p[2])
                out.append(f"remote {server['ip']} {port}")
                if mode: out.append(f"proto {'udp' if proto == 'udp' else 'tcp-client'}")
            elif p and p[0].lower() == "proto" and mode: continue
            else: out.append(line)
        if not had_remote: raise RuntimeError("OpenVPN profile has no remote endpoint")
        return "\n".join(out) + "\n"

    variants = []
    if remotes:
        variants.append(("original", build()))
        if any(proto == "udp" for proto, _ in remotes): variants.append(("tcp443", build(("tcp", 443))))
        for proto, port in remotes:
            if proto == "udp" and port != 443: variants.append((f"tcp{port}", build(("tcp", port)))); break
    else: variants.append(("original", build()))
    unique, seen = [], set()
    for name, cfg in variants:
        if cfg not in seen: seen.add(cfg); unique.append((name, cfg))
    return unique[:3]


def add_auth(config, auth_path):
    lines = [x for x in config.splitlines() if not x.strip().lower().startswith("auth-user-pass")]
    lines += [f'auth-user-pass "{auth_path}"', "auth-nocache", "resolv-retry infinite", "connect-retry 1 3", "connect-timeout 8", "verb 3"]
    return "\n".join(lines) + "\n"


def config_endpoints(config):
    out = []
    for line in config.splitlines():
        p = line.split()
        if len(p) >= 3 and p[0].lower() == "remote":
            try: out.append((p[1], int(p[2])))
            except ValueError: pass
    return out


def tcp_reachable(ip, port):
    try:
        with socket.create_connection((ip, port), timeout=1.0): return True
    except OSError: return False


def openvpn_try(ovpn, config, server, auth_path, variant):
    td = tempfile.mkdtemp(prefix="findupto-vpn-"); config_path, log_path, stdout_path = os.path.join(td, "client.ovpn"), os.path.join(td, "openvpn.log"), os.path.join(td, "openvpn-stdout.log")
    with open(config_path, "w", encoding="utf-8", newline="\n") as f: f.write(add_auth(config, auth_path))
    proc = None; stdout_file = open(stdout_path, "w", encoding="utf-8", errors="replace")
    try:
        proc = subprocess.Popen([ovpn, "--config", config_path, "--log", log_path, "--writepid", os.path.join(td, "openvpn.pid")], stdout=stdout_file, stderr=subprocess.STDOUT, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            if proc.poll() is not None: break
            try:
                if os.path.isfile(log_path):
                    with open(log_path, encoding="utf-8", errors="replace") as f: text = f.read()
                    if "Initialization Sequence Completed" in text: stdout_file.close(); return proc, td
                    if "AUTH_FAILED" in text: time.sleep(.3); break
            except OSError: pass
            time.sleep(.2)
        if proc.poll() is None:
            try: proc.terminate(); proc.wait(timeout=2)
            except Exception:
                try: proc.kill()
                except Exception: pass
        try: stdout_file.flush(); stdout_file.close()
        except Exception: pass
        output = []
        for path in (stdout_path, log_path):
            try:
                with open(path, encoding="utf-8", errors="replace") as f: output.append(f.read()[-3500:])
            except OSError: pass
        detail = "\n".join(x for x in output if x).strip() or f"OpenVPN exited with code {proc.returncode if proc else 'unknown'} without diagnostics."
        raise RuntimeError(f"{server['ip']} {variant}: {detail[-5000:]}")
    except Exception:
        if proc and proc.poll() is None:
            try: proc.kill()
            except Exception: pass
        try: stdout_file.close()
        except Exception: pass
        shutil.rmtree(td, ignore_errors=True); raise


class App(tk.Tk):
    def __init__(self):
        super().__init__(); self.title(f"{APP_NAME} {APP_VERSION}"); self.geometry("1080x650"); self.minsize(850, 520)
        self.servers, self.process, self.vpn_mode, self.vpn_dir = [], None, None, None; self.loading, self.connecting = False, False; self.events = queue.Queue()
        self.build_ui(); self.after(100, self.pump_events); self.startup()

    def build_ui(self):
        ttk.Label(self, text=APP_NAME, font=("Segoe UI", 20, "bold")).pack(anchor="w")
        ttk.Label(self, text="Fast automatic VPN • instant cache • OpenVPN multi-server/protocol fallback").pack(anchor="w", pady=(2, 14))
        frame = ttk.Frame(self); frame.pack(fill="both", expand=True); cols = ("country", "ip", "ping", "speed", "source")
        self.tree = ttk.Treeview(frame, columns=cols, show="headings")
        for c, t, w in (("country", "Country", 260), ("ip", "IP", 180), ("ping", "Ping", 100), ("speed", "Speed", 130), ("source", "Source", 130)): self.tree.heading(c, text=t); self.tree.column(c, width=w)
        self.tree.pack(side="left", fill="both", expand=True); sb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview); sb.pack(side="right", fill="y"); self.tree.configure(yscrollcommand=sb.set)
        b = ttk.Frame(self); b.pack(fill="x", pady=(14, 8)); ttk.Button(b, text="Refresh", command=self.refresh).pack(side="left'); ttk.Button(b, text="⚡ Fast Connect", command=self.fast_connect).pack(side="left", padx=8); ttk.Button(b, text="Connect", command=self.connect).pack(side="left"); ttk.Button(b, text="Disconnect", command=self.disconnect).pack(side="left", padx=8); ttk.Button(b, text="Diagnostics", command=self.diagnostics).pack(side="right")
        self.status = tk.StringVar(value="Ready — loading servers in background…"); ttk.Label(self, textvariable=self.status).pack(anchor="w")

    def pump_events(self):
        try:
            while True:
                kind, data = self.events.get_nowait()
                if kind == "servers": self.show_servers(data)
                elif kind == "status": self.status.set(str(data))
                elif kind == "error": messagebox.showerror(APP_NAME, str(data))
                elif kind == "connected": self.connecting = False
        except queue.Empty: pass
        self.after(100, self.pump_events)

    def startup(self):
        cached = load_cache()
        if cached: self.show_servers(cached); self.status.set(f"{len(cached)} cached servers ready • updating in background…")
        self.refresh(background=True)

    def refresh(self, background=False):
        if self.loading:
            if not background: self.status.set("Server refresh already running…")
            return
        self.loading = True
        if not background: self.status.set("Refreshing in background…")
        threading.Thread(target=self._refresh_worker, daemon=True).start()

    def _refresh_worker(self):
        try:
            servers = fetch_servers(); self.events.put(("servers", servers)); self.events.put(("status", f"{len(servers)} servers ready"))
        except Exception as e:
            log(f"refresh: {e}")
            if not self.servers: self.events.put(("status", "Network unavailable — cached list will be used when available"))
        finally: self.loading = False

    def show_servers(self, servers):
        self.servers = servers or []
        for x in self.tree.get_children(): self.tree.delete(x)
        for i, s in enumerate(self.servers[:60]): self.tree.insert("", "end", iid=str(i), values=(s.get("country", "Unknown"), s.get("ip", ""), "-" if s.get("ping_ms") is None else f"{s['ping_ms']:.0f} ms", f"{s.get('speed_mbps', 0):.1f} Mbps", s.get("source", "VPN Gate")))
        if self.servers: self.tree.selection_set("0")

    def selected(self):
        q = self.tree.selection(); return self.servers[int(q[0])] if q else None

    def fast_connect(self):
        if self.connecting: return
        if not self.servers: self.status.set("Waiting for server discovery…"); self.refresh(); return
        if not is_admin():
            if elevate(): self.destroy()
            return
        self.connecting = True; self.status.set("Fast Connect: testing best servers…"); threading.Thread(target=self.auto_connect, args=(self.servers[:8],), daemon=True).start()

    def connect(self):
        if self.connecting: return
        s = self.selected()
        if not s: messagebox.showinfo(APP_NAME, "Select a server first."); return
        if not is_admin():
            if elevate(): self.destroy()
            else: messagebox.showerror(APP_NAME, "Administrator permission is required.")
            return
        self.connecting = True; self.status.set("Connecting in background…"); threading.Thread(target=self.auto_connect, args=([s],), daemon=True).start()

    def auto_connect(self, candidates):
        fd, auth = tempfile.mkstemp(prefix="findupto-auth-"); os.close(fd)
        try:
            with open(auth, "w", encoding="utf-8", newline="\n") as f: f.write("vpn\nvpn\n")
            try: ovpn = ensure_openvpn()
            except Exception as e: log(f"OpenVPN unavailable: {e}"); self.events.put(("error", f"OpenVPN is unavailable: {e}")); return
            live, lock = [], threading.Lock()
            def probe(s):
                try:
                    for name, cfg in profile_variants(s):
                        for ip, port in config_endpoints(cfg):
                            if tcp_reachable(ip, port):
                                with lock: live.append((s, name, cfg))
                                return
                except Exception as e: log(f"probe {s.get('ip')}: {e}")
            threads = [threading.Thread(target=probe, args=(s,), daemon=True) for s in candidates]
            for t in threads: t.start()
            deadline = time.monotonic() + 3.5
            for t in threads:
                remaining = deadline - time.monotonic()
                if remaining > 0: t.join(remaining)
            ordered = []
            for s in candidates: ordered.extend(item for item in live if item[0]["ip"] == s["ip"])
            if not ordered:
                for s in candidates[:5]:
                    for name, cfg in profile_variants(s): ordered.append((s, name, cfg))
            for s, name, cfg in ordered[:10]:
                self.events.put(("status", f"Trying {s['country']} {s['ip']} ({name})…"))
                try:
                    p, td = openvpn_try(ovpn, cfg, s, auth, name); self.process, self.vpn_dir, self.vpn_mode = p, td, "openvpn"
                    self.events.put(("connected", True)); self.events.put(("status", f"Connected • OpenVPN • {s['country']} {s['ip']}")); threading.Thread(target=self.watch, args=(p, s), daemon=True).start(); return
                except Exception as e: log(str(e))
            self.events.put(("status", "No OpenVPN relay connected")); self.events.put(("error", "No VPN tunnel could be established. Multiple public relays and OpenVPN protocol variants were tested. See Diagnostics/log for the exact errors."))
        finally:
            try: os.remove(auth)
            except OSError: pass
            self.connecting = False

    def watch(self, p, s):
        code = p.wait(); log(f"OpenVPN stopped {s['ip']} exit={code}"); self.events.put(("status", f"VPN stopped (exit {code})"))

    def disconnect(self):
        if not is_admin():
            if elevate(): self.destroy()
            return
        if self.process and self.process.poll() is None:
            try: self.process.terminate(); self.process.wait(timeout=4)
            except Exception:
                try: self.process.kill()
                except Exception: pass
        self.process, self.vpn_mode = None, None
        if self.vpn_dir: shutil.rmtree(self.vpn_dir, ignore_errors=True)
        self.vpn_dir = None; self.status.set("Disconnected")

    def diagnostics(self):
        messagebox.showinfo("Diagnostics", f"OpenVPN: {find_openvpn() or 'NOT FOUND'}\ncurl: {which('curl.exe') or which('curl') or 'NOT FOUND'}\nPowerShell: {which('powershell.exe') or which('pwsh.exe') or 'NOT FOUND'}\nAdmin: {is_admin()}\nServers: {len(self.servers)}\nLog: {LOG_FILE}")


if __name__ == "__main__": App().mainloop()
