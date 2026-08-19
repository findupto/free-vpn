from __future__ import annotations
import gzip, os, re, shutil, ssl, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path
import vpn_engine as base
APP_VERSION="13.0.0"
ROOT,LOG,PROFILE_LOGS,CACHE=base.ROOT,base.LOG,base.PROFILE_LOGS,base.CACHE
def log(msg): base.log(msg)
def http_get(url,timeout=10,limit=10_000_000):
    started=time.monotonic(); req=urllib.request.Request(url,headers={"User-Agent":f"FinduptoVPN/{APP_VERSION}","Accept":"*/*","Accept-Encoding":"gzip","Connection":"close"})
    try:
        with urllib.request.urlopen(req,timeout=max(2.0,min(timeout,20)),context=ssl.create_default_context()) as r:
            data=r.read(limit+1)
            if len(data)>limit: raise RuntimeError("response too large")
            if "gzip" in (r.headers.get("Content-Encoding") or "").lower(): data=gzip.decompress(data)
            log(f"HTTP OK method=stdlib url={url} bytes={len(data)} elapsed={time.monotonic()-started:.2f}s"); return data
    except Exception as exc: log(f"HTTP FAIL url={url} error={type(exc).__name__}: {exc}"); raise
def _runtime_dir(): return Path(sys._MEIPASS)/"runtime" if getattr(sys,"frozen",False) else Path(__file__).resolve().parent/"runtime"
def openvpn_exe():
    candidates=[_runtime_dir()/"openvpn.exe"]
    env=os.environ.get("FINDUPTO_OPENVPN")
    if env: candidates.append(Path(env))
    candidates += [Path(r"C:\Program Files\OpenVPN\bin\openvpn.exe"),Path(r"C:\Program Files (x86)\OpenVPN\bin\openvpn.exe")]
    for name in ("openvpn.exe","openvpn"):
        found=shutil.which(name)
        if found: candidates.append(Path(found))
    return next((str(p) for p in candidates if p.is_file() and p.name.lower()=="openvpn.exe"),None)
def route_snapshot():
    if os.name!="nt": return ""
    try:
        cp=subprocess.run(["route","print","-4"],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=5,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0)); hits=[]
        for line in cp.stdout.splitlines():
            m=re.match(r"^\s*(0\.0\.0\.0|128\.0\.0\.0)\s+128\.0\.0\.0\s+([^\s]+)\s+([^\s]+)\s+(\d+)\s*$",line)
            if m: hits.append(" ".join(m.groups()))
        return " | ".join(hits[-4:])
    except Exception as exc: log(f"ROUTE SNAPSHOT FAIL error={type(exc).__name__}: {exc}"); return ""
def full_tunnel_routes(snapshot=None):
    value=route_snapshot() if snapshot is None else snapshot; nets={p.split()[0] for p in value.split(" | ") if p.split()}; return {"0.0.0.0","128.0.0.0"}.issubset(nets)
def _wait_routes(timeout=8):
    end=time.monotonic()+timeout; last=""
    while time.monotonic()<end:
        last=route_snapshot()
        if full_tunnel_routes(last): return last
        time.sleep(.25)
    return last
def _prepare(profile,username,password,work,version=(0,0,0),route_method="ipapi"):
    auth=work/"auth.txt"; auth.write_text(username+"\n"+password+"\n",encoding="utf-8"); lines=[]; cipher=None; compression=False; has_dev=False
    ignored=("auth-user-pass","redirect-gateway","route ","route-ipv6 ","route-nopull","pull-filter","register-dns","block-outside-dns","route-metric","route-delay","route-method","show-net-up","block-ipv6")
    for original in profile.splitlines():
        s=original.strip(); low=s.lower()
        if not s or low.startswith(("#",";")): lines.append(original); continue
        if low.startswith("cipher "): cipher=s.split(None,1)[1].strip()
        if low.startswith("compress ") or low.startswith("comp-lzo"): compression=True; continue
        if low.startswith("fast-io") or low.startswith("persist-key"): continue
        if low.startswith("dev "): has_dev=True
        if low.startswith(ignored): continue
        lines.append(original)
    if not has_dev: lines.append("dev tun")
    lines += ["client","redirect-gateway def1 bypass-dhcp bypass-dns","route 0.0.0.0 128.0.0.0","route 128.0.0.0 128.0.0.0","route-delay 2 30",f"route-method {route_method}","show-net-up","register-dns",f'auth-user-pass "{auth.resolve().as_posix()}"',"auth-nocache","resolv-retry infinite","connect-retry 2 3","connect-timeout 10","persist-tun","verb 4"]
    if os.name=="nt": lines += ["block-ipv6","block-outside-dns"]
    if version >= (2,6,0): lines.append("disable-dco")
    if cipher and cipher.upper() not in "AES-256-GCM:AES-128-GCM:CHACHA20-POLY1305": lines += [f"data-ciphers AES-256-GCM:AES-128-GCM:CHACHA20-POLY1305:{cipher}",f"data-ciphers-fallback {cipher}"]
    if compression and version >= (2,6,0): lines += ["allow-compression asym","comp-lzo"]
    cfg=work/"client.ovpn"; cfg.write_text("\n".join(lines)+"\n",encoding="utf-8"); return cfg
def _version(exe):
    try:
        out=subprocess.run([exe,"--version"],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=5,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0)).stdout; m=re.search(r"OpenVPN\s+(\d+)\.(\d+)(?:\.(\d+))?",out); return tuple(int(m.group(i) or 0) for i in (1,2,3)) if m else (0,0,0)
    except Exception: return (0,0,0)
def _read(path):
    try: return path.read_text(encoding="utf-8",errors="replace") if path.exists() else ""
    except OSError: return ""
def connect(server,total_deadline=45):
    if not base._is_real_server(server): raise RuntimeError("Refusing to connect to an invalid server entry")
    exe=openvpn_exe()
    if not exe: raise RuntimeError("No bundled OpenVPN runtime found; portable package is incomplete")
    ver=_version(exe); log(f"OPENVPN RUNTIME exe={exe} version={'.'.join(map(str,ver))}"); profiles,user,pwd=base._profiles(server); started=time.monotonic(); last=""; methods=("ipapi","service","adaptive") if os.name=="nt" else ("ipapi",)
    for idx,profile in enumerate(profiles,1):
        for method in methods:
            if time.monotonic()-started>=total_deadline: break
            work=Path(tempfile.mkdtemp(prefix="findupto-vpn-")); proc=None
            try:
                cfg=_prepare(profile,user,pwd,work,ver,method); logfile=work/"openvpn.log"; proc=subprocess.Popen([exe,"--config",str(cfg),"--log",str(logfile)],stdout=subprocess.DEVNULL,stderr=subprocess.STDOUT,cwd=str(Path(exe).parent),creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0)); log(f"OPENVPN START server={server['host']} profile={idx}/{len(profiles)} method={method} pid={proc.pid}"); end=min(started+total_deadline,time.monotonic()+15)
                while time.monotonic()<end:
                    text=_read(logfile)
                    if "Initialization Sequence Completed" in text:
                        routes=_wait_routes(8) if os.name=="nt" else ""
                        if os.name=="nt" and not full_tunnel_routes(routes): raise RuntimeError(f"Full-tunnel routes missing: {routes or 'none'}")
                        log(f"OPENVPN INITIALIZED server={server['host']} method={method} routes={routes or 'non-Windows'}"); return proc,work,logfile
                    if proc.poll() is not None: last=base._classify(text,proc.returncode); break
                    time.sleep(.2)
                if proc and proc.poll() is None:
                    proc.terminate()
                    try: proc.wait(3)
                    except Exception: proc.kill()
                text=_read(logfile); last=base._classify(text,proc.returncode if proc else None); base._write_failure_log(server,text or last); log(f"OPENVPN ATTEMPT FAIL server={server['host']} profile={idx} method={method} reason={last}")
            except Exception as exc:
                last=str(exc); text=_read(work/"openvpn.log")
                if text: base._write_failure_log(server,text)
                log(f"OPENVPN ATTEMPT EXCEPTION server={server['host']} profile={idx} method={method} error={exc}")
            finally:
                if proc and proc.poll() is None:
                    try: proc.kill()
                    except Exception: pass
                if not proc or proc.returncode is not None: shutil.rmtree(work,ignore_errors=True)
    raise RuntimeError(last or "all profiles failed")
def public_ip(timeout=8): return base.public_ip(timeout)
def verify_tunnel(previous_ip=None,timeout=8):
    routes=_wait_routes(timeout) if os.name=="nt" else ""
    if os.name=="nt" and not full_tunnel_routes(routes): raise RuntimeError(f"Full-tunnel routes missing: {routes or 'none'}")
    ip=public_ip(timeout)
    if previous_ip and ip==previous_ip: raise RuntimeError(f"VPN initialized but public IP did not change ({ip}); traffic is not using the VPN")
    log(f"TUNNEL VERIFIED public_ip={ip} previous_ip={previous_ip or 'unknown'} routes={routes or 'non-Windows'}"); return ip
base.http_get=http_get
base.openvpn_exe=openvpn_exe
base.route_snapshot=route_snapshot
base._prepare=_prepare
base.connect=connect
base.verify_tunnel=verify_tunnel
for _name in ("APP_VERSION","ROOT","LOG","PROFILE_LOGS","CACHE","parse_gate","vpnbook_servers_from_html","vpnbook_servers","discover","public_ip","full_tunnel_routes","route_snapshot","openvpn_exe","connect","verify_tunnel","log","http_get","_prepare"): globals()[_name]=globals().get(_name,getattr(base,_name))
