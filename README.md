# Findupto VPN

A lightweight desktop VPN client that discovers live public OpenVPN servers, ranks them, retries multiple profiles and servers, and refuses to report success until the tunnel is actually usable.

## v13.1.9

This release fixes the Windows connection failures shown by recent diagnostics:

- OpenVPN profile preparation is reload-safe; repeated module imports can no longer recurse through the `_prepare` wrapper;
- Windows full-tunnel validation now requires **both** `0.0.0.0/1` and `128.0.0.0/1` routes before a tunnel is considered initialized;
- generated Windows profiles use OpenVPN `redirect-gateway def1` with route metric and route delay settings instead of relying on a single pushed `/1` route;
- OpenVPN DCO is explicitly disabled for public/community profiles;
- legacy CBC profiles retain explicit `data-ciphers` and `data-ciphers-fallback` compatibility;
- public-IP verification bypasses configured HTTP(S) proxies so the verification request follows the machine's actual routing table;
- the application, standalone engine, and core engine versions are synchronized at 13.1.9;
- the existing strict rule remains: a connection is successful only when the tunnel is initialized, the Windows full-tunnel routes are installed, and the public IP changes.

## Supported platforms

- **Windows 10/11 x64:** packaged standalone executable with bundled OpenVPN runtime and automatic UAC elevation.
- **Linux/macOS:** source execution is supported when OpenVPN and Tkinter are installed; use `FINDUPTO_OPENVPN` when OpenVPN is outside the normal PATH.

Android and iOS are not supported by this desktop Tkinter application. They require native VPN APIs and a separate mobile client architecture.

## Requirements

### Windows packaged build

- Windows 10/11 x64
- Internet access
- Administrator/UAC approval

The repository does not commit third-party binaries. GitHub Actions downloads the official OpenVPN Community Windows runtime and packages it into `FinduptoVPN.exe`.

### Run from source

```powershell
python client/app.py
```

Run tests:

```powershell
python -m unittest discover -s tests -v
```

## Runtime diagnostics

Diagnostics are stored under `%LOCALAPPDATA%\FinduptoVPN` on Windows and the system temporary directory on other platforms:

- `diagnostic.log` — discovery, runtime, route, and connection diagnostics
- `servers.json` — short-lived validated discovery cache
- `openvpn-logs\<server>-last-failure.log` — latest failed connection log

## Tunnel success rule

A connection is successful only after the VPN process initializes, Windows has both full-tunnel `/1` routes, and the public IP changes. A successful TLS handshake by itself is never treated as a usable VPN connection.
