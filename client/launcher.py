import app
import vpnbook_backend


def _vpnbook_servers():
    try:
        return vpnbook_backend.servers()
    except Exception as exc:
        app.log(f"VPNBOOK CATALOG FAIL: {type(exc).__name__}: {exc}")
        # Keep the application usable with the built-in catalog when the page itself is temporarily unavailable.
        return app.VPNBOOK_SERVERS and [
            {"id": f"book-{sid}", "ip": f"{sid}.vpnbook.com", "host": f"{sid}.vpnbook.com",
             "country": country, "city": label, "ping": 9999, "speed": 0, "rank": 10,
             "bundle": "", "source": "VPNBook", "kind": "book"}
            for sid, (country, label) in app.VPNBOOK_SERVERS.items()
        ] or []


def _vpnbook_password():
    return vpnbook_backend.password()


def _vpnbook_bundle(server):
    return vpnbook_backend.bundle(server)


# Patch the runtime hooks used by the existing UI/connection engine.
app.vpnbook_servers = _vpnbook_servers
app.vpnbook_password = _vpnbook_password
app.vpnbook_bundle = _vpnbook_bundle
app.VERSION = "7.4.0"
app.UA = f"FinduptoVPN/{app.VERSION}"


if __name__ == "__main__":
    app.App().mainloop()
