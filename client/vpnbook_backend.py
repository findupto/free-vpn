from __future__ import annotations

import io
import re
import zipfile

import app


SERVERS = {
    "us16": ("United States", "US16"), "us178": ("United States", "US178"),
    "ca149": ("Canada", "CA149"), "ca196": ("Canada", "CA196"),
    "uk205": ("United Kingdom", "UK205"), "uk68": ("United Kingdom", "UK68"),
    "de20": ("Germany", "DE20"), "de220": ("Germany", "DE220"),
    "fr200": ("France", "FR200"), "fr2311": ("France", "FR2311"),
}


def _text(raw: bytes) -> str:
    return re.sub(r"\s+", " ", raw.decode("utf-8", "replace")).strip()


def _page() -> str:
    return app.http_get(app.VPNBOOK_PAGE, 12, 3_000_000).decode("utf-8", "replace")


def servers():
    raw = _page()
    found = {}
    # VPNBook changes bundle URLs periodically. Never construct a guessed ZIP URL.
    for href, label in re.findall(r'''href=["']([^"']+)["'][^>]*>(.*?)<''', raw, re.I | re.S):
        if not re.search(r"\.zip(?:[?#]|$)", href, re.I):
            continue
        clean = re.sub(r"<[^>]+>", " ", label)
        blob = (href + " " + clean).lower()
        for sid, (country, city) in SERVERS.items():
            if sid in blob and sid not in found:
                url = href if href.lower().startswith("http") else "https://www.vpnbook.com" + (href if href.startswith("/") else "/" + href)
                found[sid] = {
                    "id": f"book-{sid}", "ip": f"{sid}.vpnbook.com", "host": f"{sid}.vpnbook.com",
                    "country": country, "city": city, "ping": 9999, "speed": 0, "rank": 50,
                    "bundle": url, "source": "VPNBook", "kind": "book",
                }
    if not found:
        raise RuntimeError("VPNBook published no OpenVPN ZIP links")
    result = list(found.values())
    app.log(f"VPNBOOK CATALOG OK servers={len(result)} links=" + ",".join(x["id"] for x in result))
    return result


def password():
    raw = _page()
    # Prefer the credential block. Do not scrape arbitrary words following 'Password'.
    clean = re.sub(r"<script.*?</script>|<style.*?</style>", " ", raw, flags=re.I | re.S)
    clean = re.sub(r"<[^>]+>", " ", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    patterns = [
        r"Password\s+(?:<[^>]+>\s*)*([A-Za-z0-9]{6,20})\s+(?:Copy|Last updated)",
        r"VPN Credentials.{0,500}?Password.{0,100}?\b([A-Za-z0-9]{6,20})\b",
    ]
    for pattern in patterns:
        m = re.search(pattern, raw if "<" in pattern else clean, re.I | re.S)
        if m:
            value = m.group(1)
            if value.lower() not in {"password", "username", "updated", "vpnbook", "credentials"}:
                app.log(f"VPNBOOK AUTH OK length={len(value)} fingerprint={value[:2]}***{value[-2:]}")
                return value
    # Current official page uses the literal credential block. This fallback is deliberately
    # validated against the page rather than being a permanent application credential.
    m = re.search(r"\b([A-Za-z0-9]{6,20})\b\s*(?:<[^>]*>\s*)*Copy", raw, re.I)
    if m and m.group(1).lower() not in {"password", "username", "vpnbook"}:
        value = m.group(1)
        app.log(f"VPNBOOK AUTH FALLBACK length={len(value)} fingerprint={value[:2]}***{value[-2:]}")
        return value
    raise RuntimeError("VPNBook current password could not be identified from official credentials block")


def bundle(server):
    raw = app.http_get(server["bundle"], 15, 8_000_000)
    if not raw.startswith(b"PK"):
        raise RuntimeError(f"VPNBook configuration response is not ZIP ({len(raw)} bytes)")
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        names = [n for n in z.namelist() if n.lower().endswith(".ovpn")]
        if not names:
            raise RuntimeError("VPNBook ZIP contains no OpenVPN profiles")
        sid = server["host"].split(".")[0].lower()
        preferred = [n for n in names if sid in n.lower()]
        names2 = preferred or names
        # Prefer TCP 443 because it is the most broadly reachable VPNBook transport.
        chosen = next((n for n in names2 if "tcp443" in n.lower()), names2[0])
        cfg = z.read(chosen).decode("utf-8-sig", "replace")
        app.log(f"VPNBOOK PROFILE OK server={server['host']} profile={chosen} total_profiles={len(names)}")
        return cfg
