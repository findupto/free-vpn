# Findupto VPN

A lightweight desktop VPN client that discovers live public OpenVPN servers, ranks them, uses multiple transport methods and server endpoints, retries intelligently, and refuses to report success until the tunnel is actually usable.

## v13.2.0

This release upgrades the Windows connection engine with fast multi-method failover:

- VPNBook automatically tries **TCP/443, TCP/80, UDP/53 and UDP/25000** when available;
- VPN Gate profiles with multiple `remote` endpoints are expanded into independent fallback attempts;
- dead transports fail fast instead of waiting through long OpenVPN retries;
- each candidate server is capped at a short connection budget so one dead server cannot monopolize the queue;
- successful OpenVPN work directories are retained until disconnect, fixing cleanup of the live auth/config/log files;
- failed attempts are terminated and cleaned immediately;
- Windows full-tunnel validation requires both `0.0.0.0/1` and `128.0.0.0/1` routes;
- public-IP verification bypasses configured HTTP(S) proxies and requires an actual IP change;
- DCO is disabled for public/community profiles and legacy CBC cipher compatibility is retained;
- the existing strict success rule remains: initialization + full-tunnel routes + changed public IP.

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
