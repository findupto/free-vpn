import html as _html
import re as _re

import app


def _current_vpnbook_password():
    try:
        raw = app.http_get(app.VPNBOOK_PAGE, 8).decode("utf-8", "replace")
        text = _re.sub(r"<script.*?</script>|<style.*?</style>", " ", raw, flags=_re.I | _re.S)
        text = _re.sub(r"<[^>]+>", " ", text)
        text = _html.unescape(text)
        text = _re.sub(r"\s+", " ", text).strip()
        m = _re.search(r"Password\s+([A-Za-z0-9]{6,20})\s+Copy", text, _re.I)
        if m:
            return m.group(1)
        # Fallback for minor markup changes around the credential block.
        m = _re.search(r"Password\s+([A-Za-z0-9]{6,20})", text, _re.I)
        if m and m.group(1).lower() not in {"updated", "username", "service"}:
            return m.group(1)
    except Exception as exc:
        app.log(f"VPNBook password refresh: {exc}")
    # Official VPNBook currently publishes this password; it is only a temporary
    # fallback until the next successful live page read.
    return "ueedn87"


app.vpnbook_password = _current_vpnbook_password

if __name__ == "__main__":
    app.App().mainloop()
