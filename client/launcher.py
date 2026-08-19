from __future__ import annotations
import os, shutil, subprocess, tempfile, time, urllib.request
from pathlib import Path
import app
import vpnbook_backend


def _vpnbook_servers():
    try: return vpnbook_backend.servers()
    except Exception as exc:
        app.log(f"VPNBOOK CATALOG FAIL: {type(exc).__name__}: {exc}")
        return [{"id":f"book-{sid}","ip":f"{sid}.vpnbook.com","host":f"{sid}.vpnbook.com","country":country,"city":label,"ping":9999,"speed":0,"rank":10,"bundle":"","source":"VPNBook","kind":"book"} for sid,(country,label) in app.VPNBOOK_SERVERS.items()]

def _vpnbook_password(): return vpnbook_backend.password()
def _vpnbook_bundle(server): return vpnbook_backend.bundle(server)

def _connect_one(server):
    exe=app.openvpn_exe()
    if not exe: raise RuntimeError("OpenVPN Community is not installed")
    app.log(f"CONNECT START server={server['host']} source={server['source']} version={app.VERSION}")
    cfg=app.config_for(server)
    root=app.ROOT/"openvpn-logs"; root.mkdir(parents=True,exist_ok=True)
    last=""
    for n,variant in enumerate(app.variants(cfg,server["ip"]),1):
        stamp=time.strftime("%Y%m%d-%H%M%S")+f"-{time.time_ns()%1000000:06d}"
        td=Path(tempfile.mkdtemp(prefix="findupto-")); conf=td/"client.ovpn"; auth=td/"auth.txt"; logf=root/f"{stamp}-{server['host']}-v{n}.log"
        # Use a real auth file instead of relying on inline <auth-user-pass> parsing.
        import re
        m=re.search(r"<auth-user-pass>\s*([^\r\n]+)\s*\r?\n([^\r\n]+)\s*</auth-user-pass>",variant,re.I)
        if m:
            user,pwd=m.group(1).strip(),m.group(2).strip()
            auth.write_text(user+"\n"+pwd+"\n",encoding="utf-8")
            variant=re.sub(r"\s*<auth-user-pass>.*?</auth-user-pass>\s*",f'\nauth-user-pass "{auth.as_posix()}"\n',variant,flags=re.I|re.S)
        conf.write_text(variant,encoding="utf-8")
        p=subprocess.Popen([exe,"--config",str(conf),"--log",str(logf),"--route-delay","2","--connect-retry","1 2","--connect-timeout","8"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        app.log(f"OPENVPN START server={server['host']} variant={n} pid={p.pid} log={logf}")
        deadline=time.monotonic()+22
        try:
            while time.monotonic()<deadline:
                text=logf.read_text(encoding="utf-8",errors="replace") if logf.exists() else ""
                if "Initialization Sequence Completed" in text:
                    app.log(f"OPENVPN CONNECTED server={server['host']} variant={n}")
                    return p,str(td)
                low=text.lower()
                if "auth_failed" in low or "auth: failed" in low: last="authentication failed"; app.log(f"OPENVPN AUTH_FAILED server={server['host']} variant={n}"); break
                if "tls error" in low: last="TLS error"; app.log(f"OPENVPN TLS_ERROR server={server['host']} variant={n}"); break
                if "connection refused" in low: last="connection refused"; break
                if p.poll() is not None: last=f"OpenVPN exited with code {p.returncode}"; break
                time.sleep(.25)
        finally:
            if p.poll() is None:
                try: p.terminate(); p.wait(2)
                except Exception:
                    try: p.kill()
                    except Exception: pass
        if not last: last=f"OpenVPN timeout; see {logf}"
        app.log(f"OPENVPN DETAIL server={server['host']} variant={n} reason={last} log={logf}")
        shutil.rmtree(td,ignore_errors=True)
    app.log(f"CONNECT FAIL server={server['host']} reason={last or 'all variants failed'}")
    raise RuntimeError(last or "all OpenVPN transport variants failed")

app.vpnbook_servers=_vpnbook_servers
app.vpnbook_password=_vpnbook_password
app.vpnbook_bundle=_vpnbook_bundle
app.connect_one=_connect_one
app.VERSION="7.5.0"
app.UA=f"FinduptoVPN/{app.VERSION}"

if __name__=="__main__": app.App().mainloop()
