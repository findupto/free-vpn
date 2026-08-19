from __future__ import annotations

import base64
import concurrent.futures
import ctypes
import csv
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
APP_VERSION = "3.0.0"
DATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA", tempfile.gettempdir()), "Findupto")
CACHE_FILE = os.path.join(DATA_DIR, "servers.json")
LOG_FILE = os.path.join(DATA_DIR, "findupto.log")
UA = f"Findupto-Free-VPN/{APP_VERSION}"
SOURCES = (
    "https://www.vpngate.net/api/iphone/",
    "https://download.vpngate.jp/api/iphone/",
    "http://www.vpngate.net/api/iphone/",
)
OPENVPN_INSTALLERS = (
    "https://build.openvpn.net/downloads/releases/latest/openvpn-latest-stable-amd64.msi",
    "https://swupdate.openvpn.org/community/releases/OpenVPN-2.7.5-I001-amd64.msi",
    "https://swupdate.openvpn.org/community/releases/OpenVPN-2.7.4-I002-amd64.msi",
)


def log(message: str):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8", errors="replace") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
    except OSError:
        pass


def which(name: str):
    return shutil.which(name)


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin() -> bool:
    try:
        exe = sys.executable
        args = " ".join('"' + str(x).replace('"', '\\"') + '"' for x in sys.argv)
        return ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, args, os.path.dirname(exe), 1) > 32
    except Exception as exc:
        log(f"elevation failed: {exc}")
        return False


def registry_openvpn_locations() -> list[str]:
    result = []
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
                                for key in ("InstallLocation", "InstallDir", "Path"):
                                    try:
                                        value = winreg.QueryValueEx(k, key)[0]
                                        if isinstance(value, str):
                                            result.append(value)
                                    except OSError:
                                        pass
                        except OSError:
                            pass
            except OSError:
                pass
    return result


def find_openvpn() -> str | None:
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    pf32 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    roots = [os.path.join(pf, "OpenVPN"), os.path.join(pf32, "OpenVPN"), *registry_openvpn_locations()]
    candidates = []
    for root in roots:
        candidates.extend((os.path.join(root, "bin", "openvpn.exe"), os.path.join(root, "openvpn.exe")))
    candidates.extend((which("openvpn.exe"), which("openvpn")))
    for path in candidates:
        if path and os.path.isfile(path):
            return os.path.abspath(path)
    return None


def run_capture(command, timeout: float):
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def download_bytes(url: str, timeout: float = 20.0) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/plain,*/*", "Connection": "close"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        data = response.read()
    if len(data) < 100:
        raise RuntimeError("source returned an empty/invalid response")
    return data


def download_to_file(url: str, destination: str, timeout: float = 30.0):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*", "Connection": "close"})
    with urllib.request.urlopen(req, timeout=timeout) as response, open(destination, "wb") as out:
        shutil.copyfileobj(response, out, length=1024 * 256)
    if not os.path.isfile(destination) or os.path.getsize(destination) < 1024:
        raise RuntimeError("download returned an invalid file")


def parse_servers(payload: bytes) -> list[dict]:
    text = payload.decode("utf-8-sig", errors="replace")
    lines = text.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    header_index = next((i for i, line in enumerate(lines) if line.startswith("#HostName,")), None)
    if header_index is None:
        raise RuntimeError("VPN Gate CSV header not found")
    fields = lines[header_index][1:].split(",")
    result = []
    for raw in lines[header_index + 1:]:
        if not raw.strip() or raw.startswith(("#", "*")):
            continue
        try:
            row = next(csv.reader([raw]))
        except Exception:
            continue
        if len(row) < len(fields):
            continue
        item = dict(zip(fields, row))
        ip = (item.get("IP") or "").strip()
        config = (item.get("OpenVPN_ConfigData_Base64") or "").strip()
        country = (item.get("CountryLong") or item.get("CountryShort") or "Unknown").strip()
        if not ip or not config:
            continue
        try:
            ping = float(item.get("Ping") or "")
        except Exception:
            ping = None
        try:
            speed = float(item.get("Speed") or 0) / 1_000_000
        except Exception:
            speed = 0.0
        try:
            uptime = min(100.0, max(0.0, float(item.get("Uptime") or 0)))
        except Exception:
            uptime = 0.0
        try:
            gate_score = float(item.get("Score") or 0)
        except Exception:
            gate_score = 0.0
        if ping is not None and ping > 900:
            continue
        if speed and speed < 0.5:
            continue
        score = (speed * 2.5) - ((ping if ping is not None else 250) * 0.25) + uptime * 0.2 + gate_score * 0.01
        result.append({
            "id": f"vpngate-{ip}-{item.get('HostName','').strip()}",
            "ip": ip,
            "hostname": (item.get("HostName") or "").strip(),
            "country": country,
            "city": (item.get("City") or "Unknown").strip() or "Unknown",
            "ping_ms": ping,
            "speed_mbps": round(speed, 2),
            "uptime": round(uptime, 1),
            "score": round(score, 2),
            "config_b64": config,
            "source": "VPN Gate",
        })
    result.sort(key=lambda x: x["score"], reverse=True)
    return result[:120]


def save_cache(servers: list[dict]):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        tmp = CACHE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"time": time.time(), "servers": servers}, f)
        os.replace(tmp, CACHE_FILE)
    except OSError:
        pass


def load_cache(max_age: int = 24 * 3600) -> list[dict]:
    try:
        with open(CACHE_FILE, encoding="utf-8") as f:
            data = json.load(f)
        if time.time() - float(data.get("time", 0)) <= max_age:
            return data.get("servers", [])
    except Exception:
        pass
    return []


def fetch_source(url: str):
    try:
        servers = parse_servers(download_bytes(url, 20))
        return url, servers, None
    except Exception as exc:
        return url, [], str(exc)


def fetch_servers() -> list[dict]:
    # Race all mirrors. The first valid result wins; a slow mirror cannot block the UI.
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(SOURCES)) as pool:
        futures = [pool.submit(fetch_source, url) for url in SOURCES]
        failures = []
        for future in concurrent.futures.as_completed(futures, timeout=22):
            try:
                url, servers, error = future.result()
            except Exception as exc:
                failures.append(str(exc))
                continue
            if servers:
                save_cache(servers)
                log(f"server source selected: {url} ({len(servers)} servers)")
                return servers
            failures.append(f"{url}: {error}")
    cached = load_cache()
    if cached:
        log("all live sources slow/unavailable; using cached server list")
        return cached
    raise RuntimeError("No VPN server source available: " + " | ".join(failures[-3:]))


def ensure_openvpn() -> str:
    found = find_openvpn()
    if found:
        return found
    if not is_admin():
        raise PermissionError("Administrator permission is required to install OpenVPN.")
    temp_dir = tempfile.mkdtemp(prefix="findupto-openvpn-")
    try:
        installer = os.path.join(temp_dir, "openvpn.msi")
        errors = []
        for url in OPENVPN_INSTALLERS:
            try:
                download_to_file(url, installer, 45)
                if os.path.getsize(installer) > 4_000_000:
                    break
            except Exception as exc:
                errors.append(f"{url}: {exc}")
                try:
                    os.remove(installer)
                except OSError:
                    pass
        else:
            raise RuntimeError("OpenVPN installer download failed: " + " | ".join(errors[-3:]))
        result = subprocess.run(["msiexec.exe", "/i", installer, "/qn", "/norestart"], timeout=180, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if result.returncode not in (0, 3010):
            raise RuntimeError(f"OpenVPN installation failed (MSI {result.returncode}).")
        for _ in range(60):
            found = find_openvpn()
            if found:
                return found
            time.sleep(0.5)
        raise RuntimeError("OpenVPN installed but openvpn.exe was not found.")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def decode_profile(server: dict) -> str:
    raw = base64.b64decode(server["config_b64"] + "===")
    if raw[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            names = [n for n in archive.namelist() if n.lower().endswith(".ovpn")]
            if not names:
                raise RuntimeError("VPN Gate archive contains no OpenVPN profile")
            raw = archive.read(names[0])
    text = raw.decode("utf-8-sig", errors="replace")
    if "client" not in text.lower() or "remote " not in text.lower():
        raise RuntimeError("Invalid OpenVPN profile")
    return text


def profile_variants(server: dict) -> list[tuple[str, str]]:
    text = decode_profile(server)
    lines = text.splitlines()
    remotes = []
    default_proto = "udp"
    for line in lines:
        parts = line.strip().split()
        if len(parts) >= 2 and parts[0].lower() == "proto":
            default_proto = "udp" if parts[1].lower().startswith("udp") else "tcp"
        if len(parts) >= 3 and parts[0].lower() == "remote":
            try:
                port = int(parts[2])
            except ValueError:
                continue
            proto = parts[3].lower() if len(parts) >= 4 else default_proto
            remotes.append(("udp" if proto.startswith("udp") else "tcp", port))

    def build(mode: tuple[str, int] | None = None) -> str:
        output = []
        had_remote = False
        for line in lines:
            parts = line.strip().split()
            if parts and parts[0].lower() == "auth-user-pass":
                continue
            if len(parts) >= 3 and parts[0].lower() == "remote":
                had_remote = True
                if mode:
                    proto, port = mode
                else:
                    proto = "udp" if (parts[3].lower() if len(parts) >= 4 else default_proto).startswith("udp") else "tcp"
                    port = int(parts[2])
                output.append(f"remote {server['ip']} {port}")
                if mode:
                    output.append(f"proto {'udp' if proto == 'udp' else 'tcp-client'}")
            elif parts and parts[0].lower() == "proto" and mode:
                continue
            else:
                output.append(line)
        if not had_remote:
            raise RuntimeError("OpenVPN profile has no remote endpoint")
        return "\n".join(output) + "\n"

    variants = [("original", build())]
    if any(proto == "udp" for proto, _ in remotes):
        variants.append(("tcp443", build(("tcp", 443))))
        for proto, port in remotes:
            if proto == "udp" and port != 443:
                variants.append((f"tcp{port}", build(("tcp", port))))
                break
    unique = []
    seen = set()
    for name, cfg in variants:
        if cfg not in seen:
            unique.append((name, cfg))
            seen.add(cfg)
    return unique[:3]


def tcp_reachable(ip: str, port: int) -> bool:
    try:
        with socket.create_connection((ip, port), timeout=1.2):
            return True
    except OSError:
        return False


def write_profile(config: str, auth_path: str) -> str:
    lines = [line for line in config.splitlines() if not line.strip().lower().startswith("auth-user-pass")]
    lines.extend((f'auth-user-pass "{auth_path}"', "auth-nocache", "resolv-retry infinite", "connect-retry 1 2", "connect-timeout 8", "verb 3"))
    return "\n".join(lines) + "\n"


def try_openvpn(ovpn: str, config: str, auth_path: str, server: dict, variant: str):
    temp_dir = tempfile.mkdtemp(prefix="findupto-vpn-")
    config_path = os.path.join(temp_dir, "client.ovpn")
    log_path = os.path.join(temp_dir, "openvpn.log")
    with open(config_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(write_profile(config, auth_path))
    command = [ovpn, "--config", config_path, "--log", log_path]
    process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    deadline = time.monotonic() + 14
    try:
        while time.monotonic() < deadline:
            if process.poll() is not None:
                break
            try:
                with open(log_path, encoding="utf-8", errors="replace") as f:
                    text = f.read()
                if "Initialization Sequence Completed" in text:
                    return process, temp_dir
                if "AUTH_FAILED" in text or "TLS Error" in text and time.monotonic() + 2 < deadline:
                    # Give this endpoint a short chance, then fail over quickly.
                    pass
            except OSError:
                pass
            time.sleep(0.2)
        detail = ""
        try:
            with open(log_path, encoding="utf-8", errors="replace") as f:
                detail = f.read()[-3000:]
        except OSError:
            pass
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
        raise RuntimeError(f"{server['ip']} {variant}: {detail[-1200:] or 'connection timeout'}")
    except Exception:
        if process.poll() is None:
            try:
                process.kill()
            except Exception:
                pass
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} {APP_VERSION}")
        self.geometry("1100x680")
        self.minsize(900, 540)
        self.servers: list[dict] = []
        self.process = None
        self.vpn_dir = None
        self.loading = False
        self.connecting = False
        self.events = queue.Queue()
        self._build_ui()
        self.after(100, self._pump)
        self._startup()

    def _build_ui(self):
        header = ttk.Frame(self, padding=16)
        header.pack(fill="x")
        ttk.Label(header, text=APP_NAME, font=("Segoe UI", 22, "bold")).pack(anchor="w")
        ttk.Label(header, text="Smart free-server selection • cached startup • parallel source failover • OpenVPN fallback").pack(anchor="w", pady=(3, 0))
        body = ttk.Frame(self, padding=(16, 0, 16, 0))
        body.pack(fill="both", expand=True)
        columns = ("country", "city", "ip", "ping", "speed", "uptime", "score")
        self.tree = ttk.Treeview(body, columns=columns, show="headings", selectmode="browse")
        headings = {"country": "Country", "city": "City", "ip": "IP", "ping": "Ping", "speed": "Speed", "uptime": "Uptime", "score": "Smart Score"}
        widths = {"country": 180, "city": 130, "ip": 145, "ping": 80, "speed": 110, "uptime": 80, "score": 100}
        for col in columns:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=widths[col], anchor="center")
        self.tree.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(body, orient="vertical", command=self.tree.yview)
        scroll.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scroll.set)
        controls = ttk.Frame(self, padding=16)
        controls.pack(fill="x")
        ttk.Button(controls, text="Refresh", command=self.refresh).pack(side="left")
        ttk.Button(controls, text="⚡ Fast Connect", command=self.fast_connect).pack(side="left", padx=8)
        ttk.Button(controls, text="Connect Selected", command=self.connect_selected).pack(side="left")
        ttk.Button(controls, text="Disconnect", command=self.disconnect).pack(side="left", padx=8)
        ttk.Button(controls, text="Diagnostics", command=self.diagnostics).pack(side="right")
        self.status = tk.StringVar(value="Starting…")
        ttk.Label(self, textvariable=self.status, relief="sunken", anchor="w", padding=7).pack(fill="x", side="bottom")

    def _pump(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "servers":
                    self.show_servers(value)
                elif kind == "status":
                    self.status.set(value)
                elif kind == "error":
                    messagebox.showerror(APP_NAME, value)
        except queue.Empty:
            pass
        self.after(100, self._pump)

    def _startup(self):
        cached = load_cache()
        if cached:
            self.show_servers(cached)
            self.status.set(f"{len(cached)} cached servers ready • refreshing live sources in background")
        self.refresh(background=True)

    def refresh(self, background=False):
        if self.loading:
            return
        self.loading = True
        if not background:
            self.status.set("Refreshing server list…")
        threading.Thread(target=self._refresh_worker, daemon=True).start()

    def _refresh_worker(self):
        try:
            servers = fetch_servers()
            self.events.put(("servers", servers))
            self.events.put(("status", f"{len(servers)} smart-ranked free servers ready"))
        except Exception as exc:
            log(f"refresh: {exc}")
            self.events.put(("status", "Live sources unavailable; keeping the cached list" if self.servers else "No server list available"))
        finally:
            self.loading = False

    def show_servers(self, servers):
        self.servers = servers or []
        for item in self.tree.get_children():
            self.tree.delete(item)
        for index, server in enumerate(self.servers[:80]):
            ping = "—" if server.get("ping_ms") is None else f"{server['ping_ms']:.0f} ms"
            self.tree.insert("", "end", iid=str(index), values=(server.get("country", "Unknown"), server.get("city", "Unknown"), server.get("ip", ""), ping, f"{server.get('speed_mbps', 0):.1f} Mbps", f"{server.get('uptime', 0):.0f}%", f"{server.get('score', 0):.1f}"))
        if self.servers:
            self.tree.selection_set("0")

    def selected(self):
        selected = self.tree.selection()
        return self.servers[int(selected[0])] if selected else None

    def _require_admin(self) -> bool:
        if is_admin():
            return True
        if relaunch_as_admin():
            self.after(100, self.destroy)
        else:
            messagebox.showerror(APP_NAME, "Administrator permission is required for VPN tunnel changes.")
        return False

    def fast_connect(self):
        if self.connecting:
            return
        if not self.servers:
            self.refresh()
            return
        if not self._require_admin():
            return
        self.connecting = True
        self.status.set("Fast Connect: probing the best free relays…")
        threading.Thread(target=self._connect_worker, args=(self.servers[:12],), daemon=True).start()

    def connect_selected(self):
        if self.connecting:
            return
        server = self.selected()
        if not server:
            messagebox.showinfo(APP_NAME, "Select a server first.")
            return
        if not self._require_admin():
            return
        self.connecting = True
        self.status.set(f"Connecting to {server['country']} {server['ip']}…")
        threading.Thread(target=self._connect_worker, args=([server],), daemon=True).start()

    def _connect_worker(self, candidates):
        auth_fd, auth_path = tempfile.mkstemp(prefix="findupto-auth-")
        os.close(auth_fd)
        try:
            with open(auth_path, "w", encoding="utf-8", newline="\n") as f:
                f.write("vpn\nvpn\n")
            try:
                ovpn = ensure_openvpn()
            except Exception as exc:
                self.events.put(("error", f"OpenVPN is unavailable: {exc}"))
                return

            # Probe TCP endpoints concurrently so dead relays are skipped before starting OpenVPN.
            live = []
            lock = threading.Lock()
            def probe(server):
                try:
                    for variant, cfg in profile_variants(server):
                        text = cfg.splitlines()
                        endpoints = []
                        for line in text:
                            p = line.split()
                            if len(p) >= 3 and p[0].lower() == "remote":
                                try:
                                    endpoints.append((p[1], int(p[2])))
                                except ValueError:
                                    pass
                        if not endpoints or any(tcp_reachable(ip, port) for ip, port in endpoints):
                            with lock:
                                live.append((server, variant, cfg))
                            return
                except Exception as exc:
                    log(f"probe {server.get('ip')}: {exc}")

            with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(candidates))) as pool:
                list(pool.map(probe, candidates))

            ordered = []
            for server in candidates:
                ordered.extend(x for x in live if x[0] is server)
            if not ordered:
                for server in candidates[:6]:
                    try:
                        for variant, cfg in profile_variants(server):
                            ordered.append((server, variant, cfg))
                    except Exception as exc:
                        log(f"profile {server.get('ip')}: {exc}")

            for server, variant, cfg in ordered[:18]:
                self.events.put(("status", f"Trying {server['country']} {server['ip']} • {variant}"))
                try:
                    process, vpn_dir = try_openvpn(ovpn, cfg, auth_path, server, variant)
                    self.process = process
                    self.vpn_dir = vpn_dir
                    self.events.put(("status", f"Connected • {server['country']} {server['ip']} • OpenVPN"))
                    threading.Thread(target=self._watch, args=(process, server), daemon=True).start()
                    return
                except Exception as exc:
                    log(str(exc))
            self.events.put(("error", "No free relay could establish a VPN tunnel. The server list is still available; try Fast Connect again to use a different set of relays."))
            self.events.put(("status", "Connection failed — ready to retry"))
        finally:
            try:
                os.remove(auth_path)
            except OSError:
                pass
            self.connecting = False

    def _watch(self, process, server):
        code = process.wait()
        log(f"OpenVPN stopped {server['ip']} exit={code}")
        self.events.put(("status", f"VPN stopped • exit {code}"))
        self.process = None
        if self.vpn_dir:
            shutil.rmtree(self.vpn_dir, ignore_errors=True)
            self.vpn_dir = None

    def disconnect(self):
        if not self._require_admin():
            return
        process = self.process
        if process and process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=4)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass
        self.process = None
        if self.vpn_dir:
            shutil.rmtree(self.vpn_dir, ignore_errors=True)
            self.vpn_dir = None
        self.status.set("Disconnected")

    def diagnostics(self):
        messagebox.showinfo("Diagnostics", "\n".join((
            f"OpenVPN: {find_openvpn() or 'NOT FOUND'}",
            f"curl: {which('curl.exe') or which('curl') or 'not used'}",
            f"PowerShell: {which('powershell.exe') or which('pwsh.exe') or 'NOT FOUND'}",
            f"Administrator: {is_admin()}",
            f"Servers: {len(self.servers)}",
            f"Cache: {CACHE_FILE}",
            f"Log: {LOG_FILE}",
        )))


if __name__ == "__main__":
    App().mainloop()
