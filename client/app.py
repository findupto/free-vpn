import ctypes
import csv
import io
import json
import os
import shutil
import ssl
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
APP_VERSION = "1.0.0"
API_URL = os.environ.get("FINDUPTO_API_URL", "https://findupto-free-vpn.onrender.com")
DATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA", tempfile.gettempdir()), "Findupto")
CACHE_FILE = os.path.join(DATA_DIR, "servers.json")
LOG_FILE = os.path.join(DATA_DIR, "findupto.log")
TUNNEL_NAME = "FinduptoVPN"
BASE_DIR = os.path.dirname(sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__))
OPENVPN_URLS = [
    "https://build.openvpn.net/downloads/releases/latest/openvpn-latest-stable-amd64.msi",
    "https://swupdate.openvpn.org/community/releases/OpenVPN-2.7.5-I001-amd64.msi",
    "https://swupdate.openvpn.org/community/releases/OpenVPN-2.7.4-I002-amd64.msi",
    "https://swupdate.openvpn.org/community/releases/OpenVPN-2.6.22-I001-amd64.msi",
]
VPN_GATE_URLS = [
    "https://www.vpngate.net/api/iphone/",
    "https://vpngate.net/api/iphone/",
    "http://www.vpngate.net/api/iphone/",
    "http://vpngate.net/api/iphone/",
]

def log(msg):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8", errors="replace") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except OSError:
        pass

def is_windows():
    return sys.platform.startswith("win")

def is_admin():
    if not is_windows(): return False
    try: return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception: return False

def elevate():
    if is_admin(): return True
    try:
        exe = sys.executable
        args = sys.argv if not getattr(sys, "frozen", False) else sys.argv[1:]
        params = " ".join('"' + str(a).replace('"', '\\"') + '"' for a in args)
        return ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, BASE_DIR, 1) > 32
    except Exception as exc:
        log(f"Elevation failed: {exc}"); return False

def which(name):
    try: return shutil.which(name)
    except Exception: return None

def registry_locations(words):
    result=[]
    for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for parent_name in (r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall", r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"):
            try:
                with winreg.OpenKey(root,parent_name) as parent:
                    for i in range(winreg.QueryInfoKey(parent)[0]):
                        try:
                            with winreg.OpenKey(parent,winreg.EnumKey(parent,i)) as key:
                                name=str(winreg.QueryValueEx(key,"DisplayName")[0])
                                if not any(w.lower() in name.lower() for w in words): continue
                                for vn in ("InstallLocation","InstallDir","Path"):
                                    try:
                                        v=winreg.QueryValueEx(key,vn)[0]
                                        if isinstance(v,str) and v: result.append(v)
                                    except OSError: pass
                        except OSError: pass
            except OSError: pass
    return result

def find_openvpn():
    pf=os.environ.get("ProgramFiles",r"C:\Program Files"); pf32=os.environ.get("ProgramFiles(x86)",r"C:\Program Files (x86)"); pd=os.environ.get("ProgramData",r"C:\ProgramData"); local=os.environ.get("LOCALAPPDATA","")
    roots=[os.path.join(pf,"OpenVPN"),os.path.join(pf32,"OpenVPN"),os.path.join(pd,"OpenVPN"),os.path.join(local,"OpenVPN")]
    for r in registry_locations(("OpenVPN Community","OpenVPN")): roots.append(r)
    candidates=[]
    for r in roots: candidates += [os.path.join(r,"bin","openvpn.exe"),os.path.join(r,"openvpn.exe")]
    candidates += [which("openvpn.exe"),which("openvpn")]
    for p in candidates:
        if p and os.path.isfile(p): return os.path.abspath(p)
    return None

def find_wireguard():
    pf=os.environ.get("ProgramFiles",r"C:\Program Files"); pf32=os.environ.get("ProgramFiles(x86)",r"C:\Program Files (x86)")
    for p in (os.path.join(pf,"WireGuard","wireguard.exe"),os.path.join(pf32,"WireGuard","wireguard.exe"),which("wireguard.exe")):
        if p and os.path.isfile(p): return os.path.abspath(p)
    return None

def _urllib(url,dst):
    req=urllib.request.Request(url,headers={"User-Agent":f"Findupto-Free-VPN/{APP_VERSION}","Accept":"*/*"})
    with urllib.request.urlopen(req,timeout=25,context=ssl.create_default_context()) as r,open(dst,"wb") as f: shutil.copyfileobj(r,f)
    return os.path.getsize(dst)

def _curl(url,dst):
    exe=which("curl.exe") or which("curl")
    if not exe: raise RuntimeError("curl unavailable")
    r=subprocess.run([exe,"--fail","--location","--retry","4","--retry-all-errors","--connect-timeout","8","--max-time","90","-A",f"Findupto-Free-VPN/{APP_VERSION}","-o",dst,url],capture_output=True,text=True,timeout=110)
    if r.returncode: raise RuntimeError((r.stderr or r.stdout or "curl failed").strip())
    return os.path.getsize(dst)

def _powershell(url,dst):
    exe=which("powershell.exe") or which("pwsh.exe")
    if not exe: raise RuntimeError("PowerShell unavailable")
    u=url.replace("'","''"); d=dst.replace("'","''")
    scripts=[f"$ProgressPreference='SilentlyContinue';[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12;Invoke-WebRequest -UseBasicParsing -Uri '{u}' -OutFile '{d}'",f"[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12;(New-Object Net.WebClient).DownloadFile('{u}','{d}')"]
    last=""
    for s in scripts:
        try:
            r=subprocess.run([exe,"-NoProfile","-NonInteractive","-ExecutionPolicy","Bypass","-Command",s],capture_output=True,text=True,timeout=100)
            if r.returncode==0 and os.path.isfile(dst) and os.path.getsize(dst)>0: return os.path.getsize(dst)
            last=(r.stderr or r.stdout or "").strip()
        except Exception as e: last=str(e)
    raise RuntimeError(last or "PowerShell failed")

def _bits(url,dst):
    exe=which("powershell.exe") or which("pwsh.exe")
    if not exe: raise RuntimeError("PowerShell unavailable")
    u=url.replace("'","''"); d=dst.replace("'","''")
    s=f"Start-BitsTransfer -Source '{u}' -Destination '{d}' -ErrorAction Stop"
    r=subprocess.run([exe,"-NoProfile","-NonInteractive","-ExecutionPolicy","Bypass","-Command",s],capture_output=True,text=True,timeout=150)
    if r.returncode or not os.path.isfile(dst): raise RuntimeError((r.stderr or r.stdout or "BITS failed").strip())
    return os.path.getsize(dst)

def download_file(url,dst,allow_http=False):
    os.makedirs(os.path.dirname(dst) or ".",exist_ok=True); errors=[]
    for method in (_urllib,_curl,_powershell,_bits):
        try:
            if os.path.exists(dst): os.remove(dst)
            if method(url,dst)>0: log(f"download ok {method.__name__}: {url}"); return dst
        except Exception as e:
            errors.append(f"{method.__name__}: {e}"); log(errors[-1])
    if allow_http and url.lower().startswith("https://"):
        h="http://"+url[8:]
        for method in (_urllib,_curl,_powershell,_bits):
            try:
                if os.path.exists(dst): os.remove(dst)
                if method(h,dst)>0: return dst
            except Exception as e: errors.append(f"{method.__name__} HTTP: {e}")
    raise RuntimeError("All download methods failed: "+" | ".join(errors[-8:]))

def download_bytes(url,allow_http=False):
    fd,p=tempfile.mkstemp(prefix="findupto-"); os.close(fd)
    try:
        download_file(url,p,allow_http); return open(p,"rb").read()
    finally:
        try: os.remove(p)
        except OSError: pass

def ensure_openvpn():
    found=find_openvpn()
    if found: return found
    if not is_admin(): raise PermissionError("Administrator permission is required for automatic OpenVPN repair.")
    local=[os.path.join(BASE_DIR,"openvpn-amd64.msi"),os.path.join(BASE_DIR,"installer","openvpn-amd64.msi"),os.path.join(os.path.dirname(BASE_DIR),"installer","openvpn-amd64.msi")]
    installer=next((p for p in local if os.path.isfile(p) and os.path.getsize(p)>4000000),None)
    td=tempfile.mkdtemp(prefix="findupto-openvpn-")
    try:
        if not installer:
            installer=os.path.join(td,"openvpn.msi"); errors=[]
            for url in OPENVPN_URLS:
                try:
                    download_file(url,installer,False)
                    if os.path.getsize(installer)>4000000: break
                except Exception as e: errors.append(str(e))
            else: raise RuntimeError("OpenVPN download failed through every available method/source: "+" | ".join(errors[-5:]))
        mlog=os.path.join(td,"openvpn-msi.log")
        r=subprocess.run(["msiexec.exe","/i",installer,"/qn","/norestart","/L*v",mlog],capture_output=True,text=True,timeout=300)
        log(f"OpenVPN MSI exit={r.returncode}")
        if r.returncode not in (0,3010): raise RuntimeError(f"OpenVPN installation failed (MSI {r.returncode}).")
        for _ in range(40):
            found=find_openvpn()
            if found: return found
            time.sleep(.5)
        raise RuntimeError("OpenVPN installer finished but openvpn.exe is still unavailable. Check Windows services or reboot once.")
    finally: shutil.rmtree(td,ignore_errors=True)

def parse_servers(text):
    lines=text.replace("\r\n","\n").replace("\r","\n").splitlines(); i=next((n for n,x in enumerate(lines) if x.startswith("#HostName,")),None)
    if i is None: raise RuntimeError("Invalid VPN Gate server list")
    rows=csv.DictReader(io.StringIO("\n".join([lines[i][1:]]+[x for x in lines[i+1:] if x.strip() and not x.startswith("#") and not x.startswith("*")]))); out=[]
    for row in rows:
        ip=(row.get("IP") or "").strip(); country=(row.get("CountryLong") or row.get("CountryShort") or "").strip()
        if not ip or not country: continue
        try: ping=float(row.get("Ping") or "")
        except Exception: ping=None
        try: speed=float(row.get("Speed") or 0)/1000000
        except Exception: speed=0
        try: score=int(float(row.get("Score") or 0))
        except Exception: score=0
        if ping is not None and ping>700: continue
        out.append({"id":"vpngate-"+ip,"country":country,"city":(row.get("City") or "Unknown").strip() or "Unknown","ip":ip,"protocol":"openvpn","ping_ms":ping,"speed_mbps":speed,"score":score,"source":"VPN Gate","config_url":f"https://www.vpngate.net/common/openvpn_download.aspx?ip={ip}"})
    out.sort(key=lambda x:(x["ping_ms"] if x["ping_ms"] is not None else 99999,-x["speed_mbps"],-x["score"])); return out[:100]

def save_cache(s):
    try:
        os.makedirs(DATA_DIR,exist_ok=True); json.dump({"time":time.time(),"servers":s},open(CACHE_FILE,"w",encoding="utf-8"))
    except OSError: pass

def load_cache():
    try:
        d=json.load(open(CACHE_FILE,encoding="utf-8"))
        return d["servers"] if time.time()-float(d.get("time",0))<1800 else []
    except Exception: return []

def fetch_servers():
    errors=[]
    for url in (API_URL.rstrip("/")+"/api/v1/public/servers?limit=100",API_URL.rstrip("/")+"/api/v1/public/servers"):
        try:
            d=json.loads(download_bytes(url).decode("utf-8"))
            if isinstance(d,list) and d: save_cache(d); return d
        except Exception as e: errors.append(str(e))
    cached=load_cache()
    if cached: return cached
    for url in VPN_GATE_URLS:
        try:
            s=parse_servers(download_bytes(url,True).decode("utf-8-sig",errors="replace"))
            if s: save_cache(s); return s
        except Exception as e: errors.append(str(e)); log("server source failed: "+str(e))
    raise RuntimeError("No server source available: "+" | ".join(errors[-5:]))

def fetch_config(url):
    data=download_bytes(url,True)
    if data[:2]==b"PK":
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            names=[n for n in z.namelist() if n.lower().endswith(".ovpn")]
            if not names: raise RuntimeError("Server returned no OpenVPN profile")
            return z.read(names[0])
    if b"remote " not in data.lower() and b"client" not in data.lower(): raise RuntimeError("Invalid OpenVPN profile received")
    return data

class App(tk.Tk):
    def __init__(self):
        super().__init__(); self.title(f"{APP_NAME} {APP_VERSION}"); self.geometry("1080x650"); self.minsize(850,520); self.servers=[]; self.process=None; self.config_path=None; self.build_ui(); threading.Thread(target=self.startup,daemon=True).start()
    def build_ui(self):
        ttk.Label(self,text=APP_NAME,font=("Segoe UI",20,"bold")).pack(anchor="w"); ttk.Label(self,text="Automatic multi-method networking • background repair • fast fallback").pack(anchor="w",pady=(2,14))
        frame=ttk.Frame(self); frame.pack(fill="both",expand=True); cols=("country","city","ip","protocol","ping","speed","source"); self.tree=ttk.Treeview(frame,columns=cols,show="headings")
        for c,t,w in [("country","Country",150),("city","City",140),("ip","IP",130),("protocol","Protocol",90),("ping","Ping",80),("speed","Speed",95),("source","Source",120)]: self.tree.heading(c,text=t); self.tree.column(c,width=w)
        self.tree.pack(side="left",fill="both",expand=True); sb=ttk.Scrollbar(frame,orient="vertical",command=self.tree.yview); sb.pack(side="right",fill="y"); self.tree.configure(yscrollcommand=sb.set)
        b=ttk.Frame(self); b.pack(fill="x",pady=(14,8)); ttk.Button(b,text="Refresh",command=self.refresh).pack(side="left"); ttk.Button(b,text="Best Server",command=self.best).pack(side="left",padx=8); ttk.Button(b,text="Connect",command=self.connect).pack(side="left"); ttk.Button(b,text="Disconnect",command=self.disconnect).pack(side="left",padx=8); ttk.Button(b,text="Diagnostics",command=self.diagnostics).pack(side="right")
        self.status=tk.StringVar(value="Starting automatic network checks…"); ttk.Label(self,textvariable=self.status).pack(anchor="w")
    def startup(self):
        try:
            s=fetch_servers(); self.after(0,lambda:self.show_servers(s))
        except Exception as e: log("startup: "+str(e)); self.after(0,lambda:self.status.set("Network unavailable; automatic fallback exhausted"))
    def refresh(self): self.status.set("Trying network methods automatically…"); threading.Thread(target=self.startup,daemon=True).start()
    def show_servers(self,s):
        self.servers=s
        for x in self.tree.get_children(): self.tree.delete(x)
        for i,v in enumerate(s): self.tree.insert("","end",iid=str(i),values=(v.get("country",""),v.get("city","Unknown"),v.get("ip",""),"OPENVPN",("-" if v.get("ping_ms") is None else f"{v['ping_ms']:.0f} ms"),("-" if not v.get("speed_mbps") else f"{v['speed_mbps']:.1f} Mbps"),v.get("source","")))
        if s:self.tree.selection_set("0")
        self.status.set(f"{len(s)} servers ready")
    def selected(self):
        q=self.tree.selection()
        if not q: messagebox.showinfo(APP_NAME,"Select a server first."); return None
        return self.servers[int(q[0])]
    def best(self):
        if not self.servers: return messagebox.showinfo(APP_NAME,"Servers are still loading.")
        self.tree.selection_set("0"); self.connect()
    def connect(self):
        s=self.selected()
        if not s:return
        if not is_admin():
            if elevate(): self.destroy()
            else: messagebox.showerror(APP_NAME,"Administrator permission is required for the VPN tunnel.")
            return
        self.status.set("Preparing VPN automatically…"); threading.Thread(target=self.connect_worker,args=(s,),daemon=True).start()
    def connect_worker(self,s):
        path=None
        try:
            ovpn=ensure_openvpn(); config=fetch_config(s["config_url"]); fd,path=tempfile.mkstemp(prefix="findupto-",suffix=".ovpn"); os.close(fd); open(path,"wb").write(config); self.stop_process(); logpath=path+".log"; self.process=subprocess.Popen([ovpn,"--config",path,"--auth-nocache","--log",logpath],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0)); self.config_path=path; self.after(0,lambda:self.status.set(f"Connecting to {s.get('city',s.get('country','server'))}…")); threading.Thread(target=self.watch,args=(self.process,),daemon=True).start()
        except Exception as e:
            if path:
                try: os.remove(path)
                except OSError: pass
            log("connection failed: "+str(e)); self.after(0,lambda:messagebox.showerror(APP_NAME,f"Automatic connection failed.\n\n{e}\n\nLog: {LOG_FILE}")); self.after(0,lambda:self.status.set("Connection failed"))
    def watch(self,p):
        code=p.wait(); self.after(0,lambda:self.status.set(f"VPN stopped (exit code {code})"))
    def stop_process(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:self.process.kill()
        self.process=None
    def disconnect(self):
        if not is_admin():
            if elevate(): self.destroy()
            return
        self.stop_process()
        if self.config_path:
            try:os.remove(self.config_path)
            except OSError:pass
            self.config_path=None
        self.status.set("Disconnected")
    def diagnostics(self):
        messagebox.showinfo("Diagnostics",f"OpenVPN: {find_openvpn() or 'NOT FOUND'}\nWireGuard: {find_wireguard() or 'NOT FOUND'}\ncurl: {which('curl.exe') or which('curl') or 'NOT FOUND'}\nPowerShell: {which('powershell.exe') or which('pwsh.exe') or 'NOT FOUND'}\nAdmin: {is_admin()}\nLog: {LOG_FILE}")

if __name__=="__main__": App().mainloop()
