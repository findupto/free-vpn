from __future__ import annotations

import base64
import csv
import gzip
import io
import json
import os
import re
import shutil
import ssl
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir())) / "FinduptoVPN"
LOG = ROOT / "diagnostic.log"
PROFILE_LOGS = ROOT / "openvpn-logs"
CACHE = ROOT / "servers.json"
UA = "FinduptoVPN/8.0.0"
GATE_URLS = (
    "https://www.vpngate.net/api/iphone/",
    "https://download.vpngate.jp/api/iphone/",
)


def log(message: str) -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")


def http_get(url: str, timeout: float, limit: int) -> bytes:
    start = time.monotonic()
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/plain,text/html,application/zip,*/*",
        "Accept-Encoding": "gzip",
        "Connection": "close",
    })
    log(f"HTTP START {url} timeout={timeout:.1f}s limit={limit}")
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as r:
            status = int(getattr(r, "status", 200))
            enc = (r.headers.get("Content-Encoding") or "").lower()
            if status != 200:
                raise RuntimeError(f"HTTP {status}")
            data = bytearray()
            deadline = time.monotonic() + timeout
            while True:
                if time.monotonic() >= deadline:
                    raise TimeoutError("hard read deadline exceeded")
                chunk = r.read(64 * 1024)
                if not chunk:
                    break
                data.extend(chunk)
                if len(data) > limit:
                    raise RuntimeError("response too large")
            raw = bytes(data)
        if "gzip" in enc:
            raw = gzip.decompress(raw)
        log(f"HTTP OK {url} bytes={len(raw)} elapsed={time.monotonic()-start:.2f}s")
        return raw
    except Exception as exc:
        log(f"HTTP FAIL {url} elapsed={time.monotonic()-start:.2f}s error={type(exc).__name__}: {exc}")
        raise


def parse_gate(raw: bytes) -> list[dict]:
    text = raw.decode("utf-8-sig", "replace").replace("\r", "")
    header = next((x for x in text.split("\n") if x.startswith("#HostName,")), None)
    if not header:
        raise RuntimeError("VPN Gate CSV header missing")
    fields = header[1:].split(",")
    result = []
    for line in text.split("\n"):
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
        host = (d.get("HostName") or "").strip()
        if not ip or not cfg or not host:
            continue
        try:
            ping = float(d.get("Ping") or 9999)
        except Exception:
            ping = 9999
        try:
            speed = float(d.get("Speed") or 0) / 1_000_000
        except Exception:
            speed = 0
        try:
            uptime = float(d.get("Uptime") or 0) / 86400
        except Exception:
            uptime = 0
        try:
            score = float(d.get("Score") or 0)
        except Exception:
            score = 0
        # Prefer low latency, high throughput, uptime and score. Avoid huge session counts.
        rank = speed * 4.0 + score * 0.01 + min(uptime, 90) * 0.15 - min(ping, 2000) * 0.35
        result.append({
            "id": f"gate:{ip}:{host}", "ip": ip, "host": host,
            "country": d.get("CountryLong") or d.get("CountryShort") or "Unknown",
            "city": d.get("City") or "Unknown", "ping": ping,
            "speed": speed, "rank": rank, "config": cfg,
            "source": "VPN Gate", "kind": "gate",
        })
    result.sort(key=lambda x: x["rank"], reverse=True)
    return result[:120]


def _decode_profile(server: dict) -> str:
    encoded = server["config"]
    return base64.b64decode(encoded + "===").decode("utf-8-sig", "replace")


def _vpnbook_bundle(server: dict) -> str:
    sid = server["sid"]
    url = f"https://www.vpnbook.com/free-openvpn-account/vpnbook-openvpn-{sid}.zip"
    raw = http_get(url, 10, 5_000_000)
    if not raw.startswith(b"PK"):
        raise RuntimeError(f"VPNBook returned non-ZIP data for {sid}")
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        profiles = [n for n in z.namelist() if n.lower().endswith(".ovpn")]
        if not profiles:
            raise RuntimeError(f"VPNBook bundle {sid} contains no OpenVPN profiles")
        preferred = next((n for n in profiles if "tcp443" in n.lower()), profiles[0])
        return z.read(preferred).decode("utf-8-sig", "replace")


def vpnbook_servers() -> list[dict]:
    items = {
        "us16": ("United States", "US16"), "us178": ("United States", "US178"),
        "ca149": ("Canada", "CA149"), "ca196": ("Canada", "CA196"),
        "uk205": ("United Kingdom", "UK205"), "uk68": ("United Kingdom", "UK68"),
        "de20": ("Germany", "DE20"), "de220": ("Germany", "DE220"),
        "fr200": ("France", "FR200"), "fr2311": ("France", "FR2311"),
    }
    return [{"id": f"book:{sid}", "sid": sid, "ip": f"{sid}.vpnbook.com", "host": f"{sid}.vpnbook.com",
             "country": c, "city": city, "ping": 9999, "speed": 0, "rank": -1000,
             "source": "VPNBook", "kind": "book"} for sid, (c, city) in items.items()]


def vpnbook_password() -> str:
    # VPNBook changes this password periodically. Only accept a value adjacent to an explicit password label.
    raw = http_get("https://www.vpnbook.com/freevpn/openvpn", 8, 10_000_000).decode("utf-8", "replace")
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", raw, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", "\n", text)
    text = re.sub(r"\s+", " ", text)
    patterns = [
        r"(?:VPN\s+)?Password\s*[:\-]?\s*([A-Za-z0-9]{6,24})",
        r"password\s*[:\-]\s*([A-Za-z0-9]{6,24})",
    ]
    banned = {"password", "vpnbook", "credentials", "updated", "username", "openvpn"}
    for pattern in patterns:
        matches = re.findall(pattern, text, flags=re.I)
        for value in matches:
            value = value.strip()
            if value.lower() not in banned:
                log(f"VPNBOOK AUTH username=vpnbook length={len(value)} fingerprint={value[:2]}***{value[-2:]}")
                return value
    raise RuntimeError("VPNBook current password not found next to a password label")


def config_for(server: dict) -> tuple[str, str, str]:
    if server["kind"] == "gate":
        return _decode_profile(server), "vpn", "vpn"
    return _vpnbook_bundle(server), "vpnbook", vpnbook_password()


def openvpn_exe() -> str | None:
    candidates = [shutil.which("openvpn.exe"), shutil.which("openvpn"),
                  r"C:\Program Files\OpenVPN\bin\openvpn.exe",
                  r"C:\Program Files\OpenVPN Connect\OpenVPNConnect.exe"]
    for p in candidates:
        if p and os.path.isfile(p) and p.lower().endswith("openvpn.exe"):
            return p
    return None


def _rewrite_profile(profile: str, auth_file: Path, host: str, transport: tuple[str, str] | None) -> str:
    lines = profile.splitlines()
    out = []
    for line in lines:
        stripped = line.strip().lower()
        if stripped.startswith("auth-user-pass"):
            continue
        if transport and stripped.startswith("remote "):
            parts = line.split()
            out.append(f"remote {host} {transport[0]}")
        elif transport and stripped.startswith("proto "):
            out.append(f"proto {transport[1]}")
        else:
            out.append(line)
    out.append(f"auth-user-pass {auth_file}")
    out.extend(["auth-nocache", "resolv-retry infinite", "connect-retry 1 2", "verb 3"])
    return "\n".join(out) + "\n"


def _transport_variants(profile: str, host: str) -> list[tuple[str, str] | None]:
    variants: list[tuple[str, str] | None] = [None]
    for port, proto in (("443", "tcp-client"), ("80", "tcp-client"), ("1194", "udp"), ("53", "udp"), ("25000", "udp")):
        if not any(line.strip().lower().startswith("remote ") and f" {port}" in f" {line.strip()}" for line in profile.splitlines()):
            variants.append((port, proto))
    return variants


def _classify(text: str, exit_code: int | None) -> str:
    low = text.lower()
    if "auth_failed" in low:
        return "authentication failed"
    if "tls error" in low:
        return "TLS handshake failed"
    if "connection refused" in low:
        return "connection refused"
    if "network is unreachable" in low:
        return "network unreachable"
    if "options error" in low:
        return "OpenVPN configuration error"
    if exit_code is not None:
        return f"OpenVPN exited with code {exit_code}"
    return "connection timeout"


def connect(server: dict, total_deadline: float = 45.0):
    exe = openvpn_exe()
    if not exe:
        raise RuntimeError("OpenVPN Community is not installed")
    started = time.monotonic()
    log(f"CONNECT START {server['host']} source={server['source']}")
    profile, username, password = config_for(server)
    last = ""
    PROFILE_LOGS.mkdir(parents=True, exist_ok=True)
    for idx, transport in enumerate(_transport_variants(profile, server["ip"]), 1):
        if time.monotonic() - started >= total_deadline:
            break
        td = Path(tempfile.mkdtemp(prefix="findupto-vpn-"))
        auth = td / "auth.txt"
        conf = td / "client.ovpn"
        logfile = PROFILE_LOGS / f"{server['host'].replace(':','_')}-{int(time.time())}-{idx}.log"
        try:
            auth.write_text(username + "\n" + password + "\n", encoding="utf-8")
            os.chmod(auth, 0o600)
            conf.write_text(_rewrite_profile(profile, auth, server["ip"], transport), encoding="utf-8")
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            p = subprocess.Popen([exe, "--config", str(conf), "--log", str(logfile), "--route-delay", "2"],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 creationflags=creationflags)
            log(f"OPENVPN START server={server['host']} variant={idx} transport={transport or 'published'} pid={p.pid} log={logfile}")
            deadline = min(started + total_deadline, time.monotonic() + 14)
            while time.monotonic() < deadline:
                if logfile.exists():
                    text = logfile.read_text(encoding="utf-8", errors="replace")
                    if "Initialization Sequence Completed" in text:
                        log(f"OPENVPN INITIALIZED server={server['host']} variant={idx}")
                        return p, td, logfile
                    if "AUTH_FAILED" in text or "Options error" in text or "TLS Error" in text or "Connection refused" in text:
                        last = _classify(text, p.poll())
                        break
                code = p.poll()
                if code is not None:
                    last = _classify(logfile.read_text(encoding="utf-8", errors="replace") if logfile.exists() else "", code)
                    break
                time.sleep(0.2)
            else:
                last = "connection attempt timed out"
        except Exception as exc:
            last = f"{type(exc).__name__}: {exc}"
        finally:
            if 'p' in locals() and p.poll() is None:
                try:
                    p.terminate(); p.wait(timeout=2)
                except Exception:
                    try: p.kill()
                    except Exception: pass
            if not logfile.exists():
                log(f"OPENVPN LOG MISSING server={server['host']} variant={idx}")
            shutil.rmtree(td, ignore_errors=True)
        log(f"OPENVPN ATTEMPT FAIL server={server['host']} variant={idx} reason={last}")
    log(f"CONNECT FAIL server={server['host']} reason={last or 'deadline exceeded'}")
    raise RuntimeError(last or "connection deadline exceeded")


def verify_tunnel(timeout: float = 5.0) -> str:
    # Only claim success after a public IP request succeeds through the active route.
    for url in ("https://api.ipify.org", "https://ifconfig.me/ip"):
        try:
            ip = http_get(url, timeout, 256).decode("ascii", "ignore").strip()
            if re.fullmatch(r"(?:\d{1,3}\.){3}\d{1,3}", ip) or ":" in ip:
                log(f"TUNNEL VERIFIED public_ip={ip}")
                return ip
        except Exception as exc:
            log(f"TUNNEL VERIFY FAIL url={url} error={type(exc).__name__}: {exc}")
    raise RuntimeError("VPN initialized but public IP verification failed")


def load_cache() -> list[dict]:
    try:
        obj = json.loads(CACHE.read_text(encoding="utf-8"))
        if time.time() - float(obj.get("time", 0)) < 86400:
            return obj.get("servers", [])
    except Exception:
        pass
    return []


def save_cache(servers: list[dict]) -> None:
    try:
        ROOT.mkdir(parents=True, exist_ok=True)
        tmp = CACHE.with_suffix(".tmp")
        tmp.write_text(json.dumps({"time": time.time(), "servers": servers}, separators=(",", ":")), encoding="utf-8")
        tmp.replace(CACHE)
    except Exception as exc:
        log(f"CACHE SAVE FAIL {type(exc).__name__}: {exc}")


def discover(deadline: float = 8.0) -> list[dict]:
    started = time.monotonic()
    merged: dict[str, dict] = {}
    for s in load_cache() + vpnbook_servers():
        merged[s["id"]] = s
    lock = threading.Lock()
    done = threading.Event()

    def worker(url: str) -> None:
        try:
            data = parse_gate(http_get(url, min(6.0, deadline), 8_000_000))
            with lock:
                for s in data:
                    merged[s["id"]] = s
            log(f"DISCOVERY SOURCE OK {url} count={len(data)}")
        except Exception as exc:
            log(f"DISCOVERY SOURCE FAIL {url} error={type(exc).__name__}: {exc}")
        finally:
            done.set()

    threads = [threading.Thread(target=worker, args=(url,), daemon=True) for url in GATE_URLS]
    for t in threads: t.start()
    end = started + deadline
    while time.monotonic() < end and not all(not t.is_alive() for t in threads):
        time.sleep(0.05)
    ranked = sorted(merged.values(), key=lambda s: s.get("rank", -1000), reverse=True)
    log(f"DISCOVERY READY candidates={len(ranked)} elapsed={time.monotonic()-started:.2f}s")
    save_cache(ranked[:150])
    return ranked[:150]
