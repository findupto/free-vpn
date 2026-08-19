from __future__ import annotations

import base64, csv, io, json, os, queue, re, shutil, socket, subprocess, tempfile, threading, time, urllib.request, zipfile
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

APP = "Findupto Free VPN"
VERSION = "6.0.0"
DATA = Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir())) / "FinduptoVPN"
CACHE = DATA / "servers.json"
LOG = DATA / "client.log"
UA = f"FinduptoVPN/{VERSION}"

GATE = [
    "https://www.vpngate.net/api/iphone/",
    "https://download.vpngate.jp/api/iphone/",
    "http://www.vpngate.net/api/iphone/",
]
VPNBOOK = "https://www.vpnbook.com/freevpn/openvpn"


def log(msg):
    try:
        DATA.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as f: f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except OSError: pass


def get(url, timeout=6):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/plain,text/html,application/zip,*/*", "Accept-Encoding": "gzip, deflate", "Connection": "close"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
        enc = (r.headers.get("Content-Encoding") or "").lower()
    if "gzip" in enc:
        import gzip; data = gzip.decompress(data)
    elif "deflate" in enc:
        import zlib; data = zlib.decompress(data)
    return data


def parse_gate(raw):
    text = raw.decode("utf-8-sig", "replace")
    lines = text.replace("\r", "").split("\n")
    h = next((i for i,x in enumerate(lines) if x.startswith("#HostName,")), None)
    if h is None: raise RuntimeError("VPN Gate header missing")
    fields = lines[h][1:].split(","); out=[]
    for line in lines[h+1:]:
        if not line or line.startswith(("#","*")): continue
        try: row=next(csv.reader([line]))
        except Exception: continue
        if len(row)<len(fields): continue
        d=dict(zip(fields,row)); ip=(d.get("IP") or "").strip(); cfg=(d.get("OpenVPN_ConfigData_Base64") or "").strip()
        if not ip or not cfg: continue
        try: ping=float(d.get("Ping") or 9999)
        except: ping=9999
        try: speed=float(d.get("Speed") or 0)/1e6
        except: speed=0
        try: uptime=float(d.get("Uptime") or 0)
        except: uptime=0
        try: score=float(d.get("Score") or 0)
        except: score=0
        if ping>1200 or (speed and speed<0.25): continue
        rank=speed*3.0- ping*.20 + uptime*.12 + score*.008
        out.append({"id":"gate-"+ip+"-"+str(d.get("HostName","")),"ip":ip,"host":d.get("HostName",ip),"country":d.get("CountryLong") or d.get("CountryShort") or "Unknown","city":d.get("City") or "Unknown","ping":ping,"speed":round(speed,1),"uptime":round(uptime,1),"rank":round(rank,2),"config":cfg,"source":"VPN Gate"})
    return sorted(out,key=lambda x:x["rank"],reverse=True)[:100]


def vpnbook_servers(page):
    html=page.decode("utf-8","replace")
    urls=[]
    for href in re.findall(r'href=["\']([^"\']+\.zip)["\']',html,re.I):
        if "openvpn" in href.lower():
            u=href if href.startswith("http") else "https://www.vpnbook.com"+(href if href.startswith("/") else "/"+href)
            if u not in urls: urls.append(u)
    # Known bundle naming is only a fallback; no connection is attempted until its bundle is fetched.
    if not urls:
        urls=[f"https://www.vpnbook.com/free-openvpn-account/VPNBook.com-OpenVPN-{x}.zip" for x in ("US1","US2","CA1","CA2","UK1","UK2","DE1","DE2","FR1","FR2")]
    pw=""
    m=re.search(r"(?:Password|Passwort).*?([A-Za-z0-9]{6,20})",html,re.I|re.S)
    if m: pw=m.group(1)
    out=[]
    for u in urls[:12]:
        name=u.rsplit("-",1)[-1].split(".")[0]
        out.append({"id":"book-"+name,"ip":name+".vpnbook.com","host":name+".vpnbook.com","country":name[:2],"city":name,"ping":9999,"speed":0,"uptime":99,"rank":15,"bundle":u,"password":pw,"source":"VPNBook"})
    return out


def load_cache():
    try:
        d=json.loads(CACHE.read_text(encoding="utf-8"));
        if time.time()-float(d.get("time",0))<7*86400: return d.get("servers",[])
    except Exception: pass
    return []


def save_cache(s):
    try:
        DATA.mkdir(parents=True,exist_ok=True); tmp=CACHE.with_suffix('.tmp'); tmp.write_text(json.dumps({"time":time.time(),"servers":s},separators=(",",":")),encoding="utf-8"); tmp.replace(CACHE)
    except OSError: pass


class Engine:
    def __init__(self, emit): self.emit=emit; self.stop=threading.Event(); self.results={}; self.lock=threading.Lock(); self.workers=[]
    def discover(self):
        cached=load_cache()
        if cached:
            self.emit(("servers",cached,"Cached servers ready"))
        sources=[("VPNGate HTTPS",GATE[0]),("VPNGate Japan",GATE[1]),("VPNGate HTTP",GATE[2]),("VPNBook",VPNBOOK)]
        for name,url in sources:
            t=threading.Thread(target=self._source,args=(name,url),daemon=True); self.workers.append(t); t.start()
        # Hard deadline: this method NEVER joins network workers.
        threading.Thread(target=self._deadline,daemon=True).start()
    def _source(self,name,url):
        try:
            raw=get(url,5.5)
            servers=parse_gate(raw) if "vpngate" in url or "vpngate.jp" in url else vpnbook_servers(raw)
            if servers:
                with self.lock:
                    for s in servers: self.results[s["id"]]=s
                    merged=sorted(self.results.values(),key=lambda x:x.get("rank",0),reverse=True)[:140]
                save_cache(merged); self.emit(("servers",merged,f"{name}: {len(servers)} servers"))
        except Exception as e: log(f"{name}: {e}")
    def _deadline(self):
        time.sleep(7)
        with self.lock: n=len(self.results)
        self.emit(("done",n,"Discovery deadline reached; slow sources abandoned"))


def decode(server):
    if server.get("config"): return base64.b64decode(server["config"]+"===").decode("utf-8-sig","replace")
    raw=get(server["bundle"],7)
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        names=[n for n in z.namelist() if n.lower().endswith('.ovpn')]
        if not names: raise RuntimeError("VPNBook bundle has no profile")
        preferred=next((n for n in names if "tcp443" in n.lower()),names[0])
        cfg=z.read(preferred).decode("utf-8-sig","replace")
    # VPNBook changes its public password. Fetch it immediately before connection.
    page=get(VPNBOOK,5); html=page.decode("utf-8","replace"); m=re.search(r"(?:Password|Passwort).*?([A-Za-z0-9]{6,20})",html,re.I|re.S)
    if not m: raise RuntimeError("VPNBook password unavailable")
    cfg=re.sub(r"(?im)^auth-user-pass.*$","",cfg)
    cfg += f"\n<auth-user-pass>\nvpnbook\n{m.group(1)}\n</auth-user-pass>\n"
    return cfg


def openvpn_path():
    for p in [shutil.which("openvpn.exe"),r"C:\\Program Files\\OpenVPN\\bin\\openvpn.exe",r"C:\\Program Files\\OpenVPN\\bin\\openvpn.exe"]:
        if p and os.path.isfile(p): return p
    return None


def profile_variants(cfg,ip):
    lines=cfg.splitlines(); rem=[]
    for l in lines:
        p=l.split()
        if len(p)>=3 and p[0].lower()=="remote":
            try: rem.append((p[2],p[3] if len(p)>3 else "udp"))
            except: pass
    modes=[]
    if rem: modes.append(None)
    modes += [("443","tcp-client"),("80","tcp-client"),("53","udp")]
    out=[]
    for mode in modes:
        text=[]
        for l in lines:
            p=l.split()
            if p and p[0].lower()=="auth-user-pass": continue
            if len(p)>=3 and p[0].lower()=="remote":
                if mode: text.append(f"remote {ip} {mode[0]}"); text.append("proto "+mode[1])
                else: text.append(f"remote {ip} {p[2]}")
            elif p and p[0].lower()=="proto" and mode: continue
            else: text.append(l)
        text += ["resolv-retry infinite","connect-retry 1 2","connect-timeout 7","auth-nocache","verb 3"]
        x="\n".join(text)+"\n"
        if x not in out: out.append(x)
    return out


def connect(server):
    ovpn=openvpn_path()
    if not ovpn: raise RuntimeError("OpenVPN is not installed. Install OpenVPN Community first.")
    cfg=decode(server); last=""
    for variant in profile_variants(cfg,server["ip"]):
        td=tempfile.mkdtemp(prefix="findupto-"); cp=os.path.join(td,"client.ovpn"); lp=os.path.join(td,"openvpn.log")
        open(cp,"w",encoding="utf-8").write(variant); p=subprocess.Popen([ovpn,"--config",cp,"--log",lp,"--route-delay","2"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        deadline=time.monotonic()+13
        try:
            while time.monotonic()<deadline:
                if os.path.exists(lp):
                    text=open(lp,encoding="utf-8",errors="replace").read()
                    if "Initialization Sequence Completed" in text: return p,td
                    if "AUTH_FAILED" in text: last="authentication failed"; break
                    if "TLS Error" in text: last="TLS error"
                if p.poll() is not None: break
                time.sleep(.2)
        except Exception as e: last=str(e)
        if p.poll() is None:
            p.terminate()
            try:p.wait(2)
            except: p.kill()
        shutil.rmtree(td,ignore_errors=True)
    raise RuntimeError(last or "all connection methods failed")


class App(tk.Tk):
    def __init__(self):
        super().__init__(); self.title(f"{APP} {VERSION}"); self.geometry("1000x620"); self.minsize(820,500); self.q=queue.Queue(); self.servers=[]; self.proc=None; self.tmp=None; self._ui(); self.after(100,self._pump); self.refresh()
    def _ui(self):
        top=ttk.Frame(self,padding=12); top.pack(fill="x"); ttk.Label(top,text=APP,font=("Segoe UI",20,"bold")).pack(side="left"); ttk.Label(top,text="  Smart Multi-Source",font=("Segoe UI",11)).pack(side="left",pady=7); self.status=tk.StringVar(value="Starting discovery..."); ttk.Label(self,textvariable=self.status,padding=(12,0,12,8)).pack(fill="x")
        cols=("country","city","ping","speed","source"); self.tree=ttk.Treeview(self,columns=cols,show="headings",height=18)
        for c,w in zip(cols,(120,180,100,120,180)): self.tree.heading(c,text=c.title()); self.tree.column(c,width=w)
        self.tree.pack(fill="both",expand=True,padx=12); bar=ttk.Frame(self,padding=12); bar.pack(fill="x"); ttk.Button(bar,text="Refresh",command=self.refresh).pack(side="left"); ttk.Button(bar,text="Connect Best",command=self.best).pack(side="left",padx=8); ttk.Button(bar,text="Connect Selected",command=self.selected).pack(side="left"); ttk.Button(bar,text="Disconnect",command=self.disconnect).pack(side="right")
    def refresh(self):
        self.status.set("Racing independent server sources..."); self.tree.delete(*self.tree.get_children()); self.servers=[]; Engine(self.q.put).discover()
    def _pump(self):
        try:
            while True:
                typ,data,msg=self.q.get_nowait()
                self.status.set(msg)
                if typ=="servers": self.servers=data; self.tree.delete(*self.tree.get_children()); [self.tree.insert("","end",iid=str(i),values=(s.get("country"),s.get("city"),"-" if s.get("ping",9999)>=9999 else f"{s.get('ping'):.0f} ms",f"{s.get('speed',0):.1f} Mbps",s.get("source"))) for i,s in enumerate(self.servers)]
                elif typ=="connect-ok": self.status.set("CONNECTED: "+msg)
                elif typ=="error": messagebox.showerror(APP,msg); self.status.set("Connection failed")
        except queue.Empty: pass
        self.after(100,self._pump)
    def best(self): self._connect(self.servers[0] if self.servers else None)
    def selected(self):
        sel=self.tree.selection(); self._connect(self.servers[int(sel[0])] if sel else None)
    def _connect(self,s):
        if not s: messagebox.showwarning(APP,"No server is currently available. Refresh and try again."); return
        self.status.set(f"Connecting to {s.get('host')}...")
        threading.Thread(target=self._connect_worker,args=(s,),daemon=True).start()
    def _connect_worker(self,s):
        try:
            self.disconnect(); self.proc,self.tmp=connect(s); self.q.put(("connect-ok",None,f"{s.get('country')} / {s.get('host')}"))
        except Exception as e: log(f"connect {s.get('host')}: {e}"); self.q.put(("error",None,str(e)))
    def disconnect(self):
        if self.proc:
            try:self.proc.terminate()
            except: pass
            self.proc=None
        if self.tmp: shutil.rmtree(self.tmp,ignore_errors=True); self.tmp=None
    def destroy(self): self.disconnect(); super().destroy()

if __name__=="__main__": App().mainloop()
