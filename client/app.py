from __future__ import annotations

import base64, csv, gzip, io, json, os, queue, re, shutil, socket, ssl, subprocess, tempfile, threading, time, urllib.request, urllib.error, zipfile, zlib
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

APP = "Findupto VPN"
VERSION = "7.1.0"
ROOT = Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir())) / "FinduptoVPN"
CACHE = ROOT / "servers.json"
LOG = ROOT / "client.log"
USER_AGENT = f"FinduptoVPN/{VERSION}"
VPNGATE_API = "https://www.vpngate.net/api/iphone/"
VPNBOOK_PAGE = "https://www.vpnbook.com/freevpn/openvpn"
IP_CHECK = "https://api.ipify.org?format=json"


def log(message: str) -> None:
    try:
        ROOT.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as f: f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
    except OSError: pass


def http_get(url: str, timeout: float = 12, max_bytes: int = 8_000_000) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/plain,text/html,application/json,application/zip,*/*", "Accept-Encoding": "gzip, deflate", "Connection": "close"})
    with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as response:
        if response.status != 200: raise RuntimeError(f"HTTP {response.status} from {url}")
        chunks, total = [], 0
        while True:
            chunk = response.read(64 * 1024)
            if not chunk: break
            total += len(chunk)
            if total > max_bytes: raise RuntimeError(f"response too large: {url}")
            chunks.append(chunk)
        data = b"".join(chunks); encoding = (response.headers.get("Content-Encoding") or "").lower()
    if "gzip" in encoding: data = gzip.decompress(data)
    elif "deflate" in encoding: data = zlib.decompress(data)
    return data


def cache_load() -> list[dict]:
    try:
        obj = json.loads(CACHE.read_text(encoding="utf-8")); servers = obj.get("servers", [])
        if isinstance(servers, list) and time.time() - float(obj.get("updated", 0)) <= 7 * 86400: return servers
    except Exception: pass
    return []


def cache_save(servers: list[dict]) -> None:
    try:
        ROOT.mkdir(parents=True, exist_ok=True); tmp = CACHE.with_suffix(".tmp")
        tmp.write_text(json.dumps({"updated": time.time(), "servers": servers}, separators=(",", ":")), encoding="utf-8"); tmp.replace(CACHE)
    except OSError as exc: log(f"cache: {exc}")


def parse_vpngate(data: bytes) -> list[dict]:
    text = data.decode("utf-8-sig", "replace").replace("\r", ""); lines = text.split("\n")
    hi = next((i for i, line in enumerate(lines) if line.startswith("#HostName,")), -1)
    if hi < 0: raise RuntimeError("VPN Gate CSV header not found")
    fields = lines[hi][1:].split(","); result = []
    for line in lines[hi + 1:]:
        if not line or line.startswith("#"): continue
        try: row = next(csv.reader([line]))
        except Exception: continue
        if len(row) < len(fields): continue
        d = dict(zip(fields, row)); ip = (d.get("IP") or "").strip(); encoded = (d.get("OpenVPN_ConfigData_Base64") or "").strip()
        if not ip or not encoded: continue
        try: ping = float(d.get("Ping") or 9999)
        except ValueError: ping = 9999
        try: speed = float(d.get("Speed") or 0) / 1_000_000
        except ValueError: speed = 0
        try: uptime = float(d.get("Uptime") or 0) / 86400
        except ValueError: uptime = 0
        try: score = float(d.get("Score") or 0)
        except ValueError: score = 0
        if ping > 2500 or speed < 0.10: continue
        rank = speed * 5 - ping * 0.10 + uptime * 0.5 + score * 0.01
        result.append({"id": f"gate:{ip}:{d.get('HostName','')}", "source": "VPN Gate", "country": d.get("CountryLong") or d.get("CountryShort") or "Unknown", "city": d.get("City") or "Unknown", "host": d.get("HostName") or ip, "ip": ip, "ping": round(ping, 1), "speed": round(speed, 2), "rank": round(rank, 3), "config_b64": encoded})
    return sorted(result, key=lambda s: s["rank"], reverse=True)[:150]


def parse_vpnbook(page: bytes) -> list[dict]:
    html = page.decode("utf-8", "replace"); hosts = []
    for host in re.findall(r"\b((?:us|ca|uk|de|fr)\d+)\.vpnbook\.com\b", html, re.I):
        host = host.lower()
        if host not in hosts: hosts.append(host)
    if not hosts: raise RuntimeError("VPNBook published no OpenVPN hostnames")
    bundles = []
    for href in re.findall(r"(?:href|data-href)=[\"']([^\"']+)[\"']", html, re.I):
        if ".zip" not in href.lower(): continue
        url = href if href.startswith("http") else "https://www.vpnbook.com" + (href if href.startswith("/") else "/" + href)
        if url not in bundles: bundles.append(url)
    out = []
    for host in hosts:
        code = host.split(".", 1)[0].upper(); bundle = next((u for u in bundles if code in u.upper()), None)
        country = {"US": "United States", "CA": "Canada", "UK": "United Kingdom", "DE": "Germany", "FR": "France"}.get(code[:2], code[:2])
        out.append({"id": f"book:{host}", "source": "VPNBook", "country": country, "city": code, "host": host, "ip": host, "ping": 9999, "speed": 0, "rank": 10, "bundle": bundle})
    return out


def normalize(servers: list[dict]) -> list[dict]:
    unique = {}
    for s in servers: unique[s.get("id") or f"{s.get('source')}:{s.get('host')}"] = s
    return sorted(unique.values(), key=lambda s: float(s.get("rank", 0)), reverse=True)[:250]


class Discovery:
    def __init__(self, emit): self.emit = emit; self.lock = threading.Lock(); self.servers = {}
    def start(self):
        cached = cache_load()
        if cached: self._merge(cached, "Offline cache")
        providers = [("VPN Gate", lambda: parse_vpngate(http_get(VPNGATE_API, 18))), ("VPNBook", lambda: parse_vpnbook(http_get(VPNBOOK_PAGE, 10)))]
        for name, fn in providers: threading.Thread(target=self._run, args=(name, fn), daemon=True, name=f"discover-{name}").start()
        threading.Thread(target=self._deadline, daemon=True).start()
    def _run(self, name, fn):
        started = time.monotonic()
        try:
            items = fn(); self._merge(items, name); log(f"{name}: {len(items)} servers in {time.monotonic()-started:.1f}s")
        except Exception as exc:
            log(f"{name}: {type(exc).__name__}: {exc}"); self.emit(("status", 0, f"{name}: unavailable; other sources continue"))
    def _merge(self, items, source):
        with self.lock:
            for item in items: self.servers[item["id"]] = item
            merged = normalize(list(self.servers.values()))
        cache_save(merged); self.emit(("servers", merged, f"{source}: {len(items)} candidates"))
    def _deadline(self):
        time.sleep(20)
        with self.lock: count = len(self.servers)
        self.emit(("done", count, f"Discovery complete: {count} candidates"))


def decode_config(server: dict) -> str:
    if server.get("config_text"): return server["config_text"]
    if server.get("config_b64"): return base64.b64decode(server["config_b64"] + "===").decode("utf-8-sig", "replace")
    bundle = server.get("bundle")
    if not bundle: raise RuntimeError("This server has no published OpenVPN configuration")
    raw = http_get(bundle, 15, 10_000_000)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        ovpns = [n for n in archive.namelist() if n.lower().endswith(".ovpn")]
        if not ovpns: raise RuntimeError("VPNBook bundle contains no OpenVPN profiles")
        order = ("tcp443", "tcp80", "udp53", "udp25000")
        chosen = sorted(ovpns, key=lambda n: next((i for i, x in enumerate(order) if x in n.lower()), 99))[0]
        return archive.read(chosen).decode("utf-8-sig", "replace")


def openvpn_exe() -> str | None:
    candidates = [shutil.which("openvpn.exe"), os.path.expandvars(r"%ProgramFiles%\OpenVPN\bin\openvpn.exe"), os.path.expandvars(r"%ProgramFiles(x86)%\OpenVPN\bin\openvpn.exe")]
    return next((p for p in candidates if p and os.path.isfile(p)), None)


def make_variants(config: str, fallback_host: str) -> list[str]:
    lines = config.splitlines(); variants = []
    specs = [(None, None), ("tcp-client", "443"), ("tcp-client", "80"), ("udp", "53"), ("udp", "25000")]
    for proto, port in specs:
        out = []; replaced = False
        for line in lines:
            p = line.split()
            if len(p) >= 2 and p[0].lower() == "remote" and not replaced:
                out.append(f"remote {fallback_host} {port}" if proto else line); replaced = True
            elif p and p[0].lower() == "proto" and proto: out.append(f"proto {proto}")
            else: out.append(line)
        if not replaced and proto: out.append(f"remote {fallback_host} {port}")
        if proto: out += ["resolv-retry infinite", "connect-timeout 8", "connect-retry 1 2", "auth-nocache", "verb 3"]
        text = "\n".join(out) + "\n"
        if text not in variants: variants.append(text)
    return variants


def current_ip() -> str | None:
    try: return json.loads(http_get(IP_CHECK, 4).decode("utf-8")).get("ip")
    except Exception: return None


def verify_public_ip(before: str | None) -> tuple[bool, str]:
    try:
        after = json.loads(http_get(IP_CHECK, 5).decode("utf-8")).get("ip")
        if not after: return False, "public IP check returned no IP"
        if before and after == before: return False, f"public IP did not change ({after})"
        return True, after
    except Exception as exc: return False, f"IP verification unavailable: {exc}"


def connect_one(server: dict, before: str | None):
    exe = openvpn_exe()
    if not exe: raise RuntimeError("OpenVPN Community is not installed. Install OpenVPN, then try again.")
    config = decode_config(server); fallback = server.get("ip") or server.get("host")
    last = ""
    for index, variant in enumerate(make_variants(config, fallback)):
        temp = tempfile.mkdtemp(prefix="findupto-"); cfg = os.path.join(temp, "client.ovpn"); lp = os.path.join(temp, "openvpn.log")
        Path(cfg).write_text(variant, encoding="utf-8")
        proc = subprocess.Popen([exe, "--config", cfg, "--log", lp, "--route-delay", "1"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        try:
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                text = Path(lp).read_text(encoding="utf-8", errors="replace") if os.path.exists(lp) else ""
                if "Initialization Sequence Completed" in text:
                    ok, detail = verify_public_ip(before)
                    if ok: return proc, temp, detail, index
                    last = detail; break
                for marker, msg in (("AUTH_FAILED", "authentication failed"), ("TLS Error", "TLS negotiation failed"), ("Connection refused", "connection refused")):
                    if marker in text: last = msg
                if proc.poll() is not None: break
                time.sleep(.25)
        finally:
            if proc.poll() is not None: shutil.rmtree(temp, ignore_errors=True)
        if proc.poll() is None:
            proc.terminate()
            try: proc.wait(2)
            except subprocess.TimeoutExpired: proc.kill()
        shutil.rmtree(temp, ignore_errors=True)
    raise RuntimeError(last or "all OpenVPN transport variants failed")


class App(tk.Tk):
    def __init__(self):
        super().__init__(); self.title(f"{APP} {VERSION}"); self.geometry("1050x650"); self.minsize(850, 520)
        self.q=queue.Queue(); self.servers=[]; self.proc=None; self.temp=None; self.connecting=False; self.build_ui(); self.after(100,self.pump); self.refresh()
    def build_ui(self):
        top=ttk.Frame(self,padding=12); top.pack(fill="x"); ttk.Label(top,text=APP,font=("Segoe UI",20,"bold")).pack(side="left"); ttk.Label(top,text=f"  Smart Multi-Source {VERSION}").pack(side="left",pady=7)
        self.status=tk.StringVar(value="Starting..."); ttk.Label(self,textvariable=self.status,padding=(12,0,12,8)).pack(fill="x")
        cols=("country","city","ping","speed","source"); self.tree=ttk.Treeview(self,columns=cols,show="headings",height=20)
        for c,w in zip(cols,(150,180,100,120,220)): self.tree.heading(c,text=c.title()); self.tree.column(c,width=w)
        self.tree.pack(fill="both",expand=True,padx=12)
        bar=ttk.Frame(self,padding=12); bar.pack(fill="x"); ttk.Button(bar,text="Refresh",command=self.refresh).pack(side="left"); ttk.Button(bar,text="Import .ovpn",command=self.import_ovpn).pack(side="left",padx=6); ttk.Button(bar,text="Connect Best",command=self.connect_best).pack(side="left",padx=6); ttk.Button(bar,text="Connect Selected",command=self.connect_selected).pack(side="left"); ttk.Button(bar,text="Disconnect",command=self.disconnect).pack(side="right")
    def refresh(self):
        if self.connecting: return
        self.status.set("Loading cache and racing independent providers..."); self.tree.delete(*self.tree.get_children()); self.servers=[]; Discovery(self.q.put).start()
    def pump(self):
        try:
            while True:
                typ,data,msg=self.q.get_nowait(); self.status.set(msg)
                if typ=="servers": self.servers=data; self.render()
                elif typ=="connected": self.connecting=False; self.status.set(f"CONNECTED — public IP {msg}")
                elif typ=="error": self.connecting=False; messagebox.showerror(APP,msg); self.status.set("Connection failed")
        except queue.Empty: pass
        self.after(100,self.pump)
    def render(self):
        self.tree.delete(*self.tree.get_children())
        for i,s in enumerate(self.servers):
            ping=s.get("ping",9999); self.tree.insert("","end",iid=str(i),values=(s.get("country",""),s.get("city",""),"-" if ping>=9999 else f"{ping:.0f} ms",f"{float(s.get('speed',0)):.2f} Mbps",s.get("source","")))
    def connect_best(self): self._connect_many(self.servers[:12])
    def connect_selected(self):
        sel=self.tree.selection(); self._connect_many([self.servers[int(sel[0])]] if sel else [])
    def _connect_many(self, candidates):
        if not candidates: messagebox.showwarning(APP,"No server is available. Refresh or import an .ovpn profile."); return
        if self.connecting: return
        self.connecting=True; self.status.set(f"Testing up to {len(candidates)} servers with automatic failover..."); threading.Thread(target=self._worker,args=(candidates,),daemon=True).start()
    def _worker(self,candidates):
        before=current_ip(); errors=[]
        try:
            self.disconnect()
            for candidate in candidates:
                try:
                    self.status.set(f"Trying {candidate.get('source')} / {candidate.get('host')}...")
                    proc,temp,public_ip,variant=connect_one(candidate,before); self.proc,self.temp=proc,temp; log(f"connected {candidate.get('host')} variant {variant} public_ip={public_ip}"); self.q.put(("connected",None,public_ip)); return
                except Exception as exc:
                    errors.append(f"{candidate.get('host')}: {exc}"); log(errors[-1])
            raise RuntimeError("No candidate connected successfully.\n\n" + "\n".join(errors[:8]))
        except Exception as exc: self.q.put(("error",None,str(exc)))
        finally: self.connecting=False
    def import_ovpn(self):
        path=filedialog.askopenfilename(filetypes=[("OpenVPN profile","*.ovpn")])
        if not path: return
        try:
            text=Path(path).read_text(encoding="utf-8-sig",errors="replace"); rem=re.search(r"(?im)^remote\s+([^\s]+)(?:\s+(\d+))?",text); host=rem.group(1) if rem else Path(path).stem
            self.servers.insert(0,{"id":f"import:{path}","source":"Imported","country":"Imported","city":"","host":host,"ip":host,"ping":9999,"speed":0,"rank":999,"config_text":text}); self.render(); self.status.set(f"Imported {Path(path).name}")
        except Exception as exc: messagebox.showerror(APP,f"Could not read profile: {exc}")
    def disconnect(self):
        if self.proc:
            try:self.proc.terminate()
            except Exception:pass
            self.proc=None
        if self.temp: shutil.rmtree(self.temp,ignore_errors=True); self.temp=None
        self.connecting=False
    def destroy(self): self.disconnect(); super().destroy()

if __name__=="__main__": App().mainloop()
