from __future__ import annotations

import base64
import io
import re
import urllib.request
import zipfile

import app
import resilient

# Replace the broken discovery path with the resilient multi-source engine.
app.fetch_servers = resilient.fetch_servers
app.APP_VERSION = "5.0.0"


def _bootstrap_decode_profile(server: dict) -> str:
    """Decode normal profiles, and lazily materialize VPNBook bootstrap profiles."""
    encoded = server.get("config_b64", "")
    if encoded != base64.b64encode(b"bootstrap").decode():
        return app.decode_profile(server)

    url = server.get("config_url")
    if not url:
        raise RuntimeError("VPN profile URL is missing")
    req = urllib.request.Request(url, headers={
        "User-Agent": "Findupto-Free-VPN/5.0",
        "Accept": "application/zip,*/*",
        "Connection": "close",
    })
    with urllib.request.urlopen(req, timeout=7) as response:
        raw = response.read()
    if raw[:2] != b"PK":
        raise RuntimeError("VPNBook returned an invalid OpenVPN bundle")

    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        profiles = [n for n in archive.namelist() if n.lower().endswith(".ovpn")]
        if not profiles:
            raise RuntimeError("VPNBook bundle contains no OpenVPN profile")
        # Prefer TCP 443 for restricted networks, otherwise select a profile
        # matching the server's hostname.
        preferred = next((n for n in profiles if "tcp443" in n.lower()), profiles[0])
        config = archive.read(preferred).decode("utf-8-sig", errors="replace")

    # Fetch the current public VPNBook password. It changes periodically.
    page_req = urllib.request.Request(
        resilient.VPNBOOK_PAGE,
        headers={"User-Agent": "Findupto-Free-VPN/5.0", "Accept": "text/html,*/*"},
    )
    with urllib.request.urlopen(page_req, timeout=6) as response:
        page = response.read().decode("utf-8", errors="replace")
    _, password = resilient._vpnbook_credentials(page.encode())
    if not password:
        raise RuntimeError("Could not obtain the current VPNBook password")

    config = re.sub(r"(?im)^auth-user-pass.*$", "", config)
    config += f"\n<auth-user-pass>\nvpnbook\n{password}\n</auth-user-pass>\n"
    return config


app.decode_profile = _bootstrap_decode_profile

if __name__ == "__main__":
    app.App().mainloop()
