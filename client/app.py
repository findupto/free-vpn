from __future__ import annotations

import base64, csv, gzip, io, json, os, queue, re, shutil, ssl, subprocess, tempfile, threading, time, urllib.request, urllib.error, zipfile, zlib
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

APP = "Findupto VPN"
VERSION = "7.2.0"
ROOT = Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir())) / "FinduptoVPN"
CACHE = ROOT / "servers.json"
LOG = ROOT / "client.log"
UA = f"FinduptoVPN/{VERSION}"
GATE_URLS = [
    "https://www.vpngate.net/api/iphone/",
    "https://download.vpngate.jp/api/iphone/",
]
VPNBOOK_PAGE = "https://www.vpnbook.com/freevpn/openvpn"
VPNBOOK_SERVERS = {
    "us16": ("United States", "US16"), "us178": ("United States", "US178"),
    "ca149": ("Canada", "CA149"), "ca196": ("Canada", "CA196"),
    "uk205": ("United Kingdom", "UK205"), "uk68": ("United Kingdom", "UK68"),
    "de20": ("Germany", "DE20"), "de220": ("Germany", "DE220"),
    "fr200": ("France", "FR200"), "fr2311": ("France", "FR2311"),
}


def log(msg: str):
    try:
        ROOT.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except OSError:
        pass


def http_get(url: str, timeout=10, limit=10_000_000) -> bytes:
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/plain,text/html,application/zip,*/*",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "close",
    })
    with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as r:
        if getattr(r, "status", 200) != 200:
            raise RuntimeError(f"HTTP {r.status}")
        chunks, total = [], 0
        while True:
            b = r.read(64 * 1024)
            if not b:
                break
            total += len(b)
            if total > limit:
                raise RuntimeError("response too large")
            chunks.append(b)
        data = b"".join(chunks)
        enc = (r.headers.get("Content-Encoding") or "").lower()
    if "gzip" in enc:
        data = gzip.decompress(data)
    elif "deflate" in enc:
        data = zlib.decompress(data)
    return data


def parse_gate(raw: bytes):
    text = raw.decode("utf-8-sig", "replace").replace("\r", "")
    lines = text.split("\n")
    header = next((x for x in lines if x.startswith("#HostName,")), None)
    if not header:
        raise RuntimeError("VPN Gate header missing")
    fields = header[1:].split(",")
    out = []
    for line in lines:
        if not line or line.startswith("#"):
            continue
        try:
            row = next(csv.reader([line]))
        except Exception:
            continue
        if len(row) < len(fields):
            continue
        d = dict(zip(fields, row))
        ip = (d.get("IP") or "").strip()
        cfg = (d.get("OpenVPN_ConfigData_Base64") or "").strip()
        if not ip or not cfg:
            continue
        try: ping = float(d.get("Ping") or 9999)
        except Exception: ping = 9999
        try: speed = float(d.get("Speed") or 0) / 1_000_000
        except Exception: speed = 0
        try: uptime = float(d.get("Uptime") or 0)
        except Exception: uptime = 0
        try: score = float(d.get("Score") or 0)
        except Exception: score = 0
        rank = speed * 3 - min(ping, 1500) * .18 + uptime * .1 + score * .008
        out.append({
            "id": f"gate-{ip}-{d.get('HostName','')}", "ip": ip,
            "host": d.get("HostName") or ip,
            "country": d.get("CountryLong") or d.get("CountryShort") or "Unknown",
            "city": d.get("City") or "Unknown", "ping": ping,
            "speed": round(speed, 1), "rank": rank, "config": cfg,
            "source": "VPN Gate", "kind": "gate"
        })
    return sorted(out, key=lambda x: x["rank"], reverse=True)[:100]


def vpnbook_servers():
    # VPNBook publishes these exact server names and exposes a bundle per server.
    # Do not guess old /free-openvpn-account URLs or scrape absent href attributes.
    out = []
    for sid, (country, label) in VPNBOOK_SERVERS.items():
        bundle = f"https://www.vpnbook.com/free-openvpn-account/vpnbook-openvpn-{sid}.zip"
        out.append({
            "id": f"book-{sid}", "ip": f"{sid}.vpnbook.com", "host": f"{sid}.vpnbook.com",
            "country": country, "city": label, "ping": 9999, "speed": 0,
            "rank": 50, "bundle": bundle, "source": "VPNBook", "kind": "book"
        })
    return out


def cache_load():
    try:
        d = json.loads(CACHE.read_text(encoding="utf-8"))
        if time.time() - float(d.get("time", 0)) < 7 * 86400:
            return d.get("servers", [])
    except Exception:
        pass
    return []


def cache_save(servers):
    try:
        ROOT.mkdir(parents=True, exist_ok=True)
        tmp = CACHE.with_suffix(".tmp")
        tmp.write_text(json.dumps({"time": time.time(), "servers": servers}, separators=(",", ":")), encoding="utf-8")
        tmp.replace(CACHE)
    except OSError:
        pass


def vpnbook_password():
    html = http_get(VPNBOOK_PAGE, 8).decode("utf-8", "replace")
    # Current VPNBook page publishes the credential next to 'Password'.
    m = re.search(r"Password\s*</[^>]+>\s*.*?([A-Za-z0-9]{6,20})", html, re.I | re.S)
    if not m:
        m = re.search(r"Password.{0,500}?([A-Za-z0-9]{6,20})", html, re.I | re.S)
    if not m:
        raise RuntimeError("VPNBook current password could not be read")
    return m.group(1)


def vpnbook_bundle(server):
    raw = http_get(server["bundle"], 10, 5_000_000)
    if not raw.startswith(b"PK"):
        raise RuntimeError(f"VPNBook bundle HTTP response is not a ZIP ({len(raw)} bytes)")
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        profiles = [n for n in z.namelist() if n.lower().endswith(".ovpn")]
        if not profiles:
            raise RuntimeError("VPNBook ZIP contains no .ovpn profile")
        # Prefer TCP 443; it is the most useful fallback on restricted networks.
        preferred = next((n for n in profiles if "tcp443" in n.lower()), profiles[0])
        cfg = z.read(preferred).decode("utf-8-sig", "replace")
    return cfg


def normalize_openvpn(cfg: str, username=None, password=None):
    # Keep certificates/keys exactly as published; only normalize transport and auth.
    cfg = re.sub(r"(?im)^\s*auth-user-pass.*$", "", cfg)
    if username and password:
        cfg += f"\n<auth-user-pass>\n{username}\n{password}\n</auth-user-pass>\n"
    cfg += "\nresolv-retry infinite\nconnect-retry 1 2\nconnect-timeout 8\nauth-nocache\nverb 3\n"
    return cfg


def config_for(server):
    if server.get("kind") == "gate":
        return base64.b64decode(server["config"] + "===").decode("utf-8-sig", "replace")
    cfg = vpnbook_bundle(server)
    password = vpnbook_password()
    return normalize_openvpn(cfg, "vpnbook", password)


def openvpn_exe():
    candidates = [
        shutil.which("openvpn.exe"),
        r"C:\Program Files\OpenVPN\bin\openvpn.exe",
        r"C:\Program Files\OpenVPN\bin\openvpn-gui.exe",
        r"C:\Program Files\OpenVPN Connect\OpenVPNConnect.exe",
    ]
    for p in candidates:
        if p and os.path.isfile(p) and p.lower().endswith("openvpn.exe"):
            return p
    return None


def variants(cfg, host):
    lines = cfg.splitlines()
    found = []
    for line in lines:
        p = line.split()
        if len(p) >= 3 and p[0].lower() == "remote":
            found.append((p[1], p[2]))
    targets = []
    if found:
        targets.append(None)
    for port, proto in [("443", "tcp-client"), ("80", "tcp-client"), ("53", "udp"), ("25000", "udp")]:
        targets.append((port, proto))
    result = []
    for target in targets:
        out = []
        for line in lines:
            p = line.split()
            if len(p) >= 3 and p[0].lower() == "remote":
                if target:
                    out.append(f"remote {host} {target[0]}")
                else:
                    out.append(line)
            elif p and p[0].lower() == "proto" and target:
                out.append("proto " + target[1])
            else:
                out.append(line)
        text = "\n".join(out) + "\n"
        if text not in result:
            result.append(text)
    return result


def connect_one(server):
    exe = openvpn_exe()
    if not exe:
        raise RuntimeError("OpenVPN Community is not installed. Install OpenVPN Community, then retry.")
    cfg = config_for(server)
    last = ""
    for n, variant in enumerate(variants(cfg, server["ip"]), 1):
        td = tempfile.mkdtemp(prefix="findupto-")
        conf = os.path.join(td, "client.ovpn")
        logfile = os.path.join(td, "openvpn.log")
        Path(conf).write_text(variant, encoding="utf-8")
        p = subprocess.Popen([exe, "--config", conf, "--log", logfile, "--route-delay", "2"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        deadline = time.monotonic() + 15
        try:
            while time.monotonic() < deadline:
                if os.path.exists(logfile):
                    text = Path(logfile).read_text(encoding="utf-8", errors="replace")
                    if "Initialization Sequence Completed" in text:
                        return p, td
                    if "AUTH_FAILED" in text:
                        last = "authentication failed"
                        break
                    if "TLS Error" in text:
                        last = "TLS error"
                if p.poll() is not None:
                    last = f"OpenVPN exited with code {p.returncode}"
                    break
                time.sleep(.25)
        finally:
            if p.poll() is not None:
                shutil.rmtree(td, ignore_errors=True)
        if p.poll() is None:
            try:
                p.terminate(); p.wait(2)
            except Exception:
                try: p.kill()
                except Exception: pass
        shutil.rmtree(td, ignore_errors=True)
    raise RuntimeError(last or "all OpenVPN transport variants failed")


class Discovery:
    def __init__(self, emit):
        self.emit = emit
        self.results = {}
        self.lock = threading.Lock()

    def start(self):
        cached = cache_load()
        # Always seed VPNBook directly: it is a real published source and does not depend on VPN Gate.
        seed = vpnbook_servers()
        merged = {s["id"]: s for s in seed + cached}
        with self.lock:
            self.results.update(merged)
        self.emit(("servers", self.sorted(), "Built-in VPNBook catalog ready; testing live sources..."))
        for url in GATE_URLS:
            threading.Thread(target=self._gate, args=(url,), daemon=True).start()
        threading.Thread(target=self._deadline, daemon=True).start()

    def _gate(self, url):
        try:
            servers = parse_gate(http_get(url, 6, 8_000_000))
            with self.lock:
                for s in servers: self.results[s["id"]] = s
                data = self.sorted()
            cache_save(data)
            self.emit(("servers", data, f"VPN Gate updated: {len(servers)} candidates"))
        except Exception as e:
            log(f"VPN Gate {url}: {e}")

    def _deadline(self):
        time.sleep(7)
        with self.lock: count = len(self.results)
        self.emit(("done", count, f"Discovery ready: {count} candidates"))

    def sorted(self):
        return sorted(self.results.values(), key=lambda s: (s.get("rank", 0), -s.get("ping", 9999)), reverse=True)[:150]


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP} {VERSION}")
        self.geometry("1050x650")
        self.minsize(850, 520)
        self.q = queue.Queue(); self.servers = []; self.proc = None; self.tmp = None
        self._build(); self.after(100, self._pump); self.refresh()

    def _build(self):
        top = ttk.Frame(self, padding=12); top.pack(fill="x")
        ttk.Label(top, text=APP, font=("Segoe UI", 20, "bold")).pack(side="left")
        ttk.Label(top, text=f"  Smart Multi-Source {VERSION}").pack(side="left", pady=7)
        self.status = tk.StringVar(value="Starting...")
        ttk.Label(self, textvariable=self.status, padding=(12, 0, 12, 8)).pack(fill="x")
        cols = ("country", "city", "ping", "speed", "source")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=20)
        for c, w in zip(cols, (150, 190, 100, 120, 180)):
            self.tree.heading(c, text=c.title()); self.tree.column(c, width=w)
        self.tree.pack(fill="both", expand=True, padx=12)
        bar = ttk.Frame(self, padding=12); bar.pack(fill="x")
        ttk.Button(bar, text="Refresh", command=self.refresh).pack(side="left")
        ttk.Button(bar, text="Connect Best", command=self.best).pack(side="left", padx=8)
        ttk.Button(bar, text="Connect Selected", command=self.selected).pack(side="left")
        ttk.Button(bar, text="Disconnect", command=self.disconnect).pack(side="right")

    def refresh(self):
        self.status.set("Loading cached catalog and racing live sources...")
        self.tree.delete(*self.tree.get_children()); self.servers = []
        Discovery(self.q.put).start()

    def _pump(self):
        try:
            while True:
                typ, data, msg = self.q.get_nowait()
                self.status.set(msg)
                if typ == "servers":
                    self.servers = data; self.tree.delete(*self.tree.get_children())
                    for i, s in enumerate(data):
                        ping = "-" if s.get("ping", 9999) >= 9999 else f"{s['ping']:.0f} ms"
                        speed = "-" if not s.get("speed") else f"{s['speed']:.1f} Mbps"
                        self.tree.insert("", "end", iid=str(i), values=(s.get("country"), s.get("city"), ping, speed, s.get("source")))
                elif typ == "connected":
                    self.status.set("CONNECTED: " + msg)
                elif typ == "error":
                    messagebox.showerror(APP, msg); self.status.set("No candidate connected successfully")
        except queue.Empty:
            pass
        self.after(100, self._pump)

    def best(self):
        self._connect_many(self.servers[:12])

    def selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning(APP, "Select a server first."); return
        self._connect_many([self.servers[int(sel[0])]])

    def _connect_many(self, candidates):
        if not candidates:
            messagebox.showwarning(APP, "No server candidates available. Refresh and try again."); return
        self.disconnect(); self.status.set(f"Testing {len(candidates)} candidates with OpenVPN failover...")
        threading.Thread(target=self._connect_worker, args=(candidates,), daemon=True).start()

    def _connect_worker(self, candidates):
        errors = []
        for s in candidates:
            try:
                self.status.set(f"Trying {s['host']}...")
                p, td = connect_one(s)
                self.proc, self.tmp = p, td
                self.q.put(("connected", None, f"{s['country']} / {s['host']}")); return
            except Exception as e:
                err = f"{s['host']}: {e}"; errors.append(err); log(err)
        self.q.put(("error", None, "No candidate connected successfully.\n\n" + "\n".join(errors[:12])))

    def disconnect(self):
        if self.proc:
            try: self.proc.terminate()
            except Exception: pass
            self.proc = None
        if self.tmp:
            shutil.rmtree(self.tmp, ignore_errors=True); self.tmp = None

    def destroy(self):
        self.disconnect(); super().destroy()


if __name__ == "__main__":
    App().mainloop()
