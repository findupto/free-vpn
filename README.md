# Findupto VPN

A lightweight desktop VPN client that discovers live public OpenVPN servers, ranks them, uses multiple transport methods and server endpoints, retries intelligently, and refuses to report success until the tunnel is actually usable.

## v14.3.0

This release adds connection lifecycle and IP rotation hardening on top of the existing VPN engine:

- safe, serialized VPN session state management;
- idempotent Disconnect with graceful termination and forced-kill fallback;
- one-click **Change IP** in the desktop command center;
- alternate endpoint selection that avoids the current server;
- verified exit-IP rotation: a new connection is not accepted when it returns the previous public IP;
- automatic retry across multiple alternate verified endpoints;
- protection against overlapping connect/disconnect/change-IP operations;
- regression coverage for connect, disconnect, endpoint selection, retry, and IP rotation.

The previous production-hardening features remain enabled, including durable SQLite persistence, node health/staleness handling, replay-resistant control-plane requests, rolling server health scoring, DNS/public-IP diagnostics, deterministic configuration signatures, reconnect backoff, server quarantine, and privacy-safe diagnostics.

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

## Connection controls

- **Connect:** establishes a tunnel and verifies that the public exit IP changes.
- **Disconnect:** closes the active OpenVPN process safely and resets local session state.
- **Change IP:** closes the current tunnel, tries alternate verified endpoints, and accepts a new tunnel only when the public exit IP differs from the previous one.

If no alternate endpoint produces a different exit IP, the operation fails closed instead of claiming that the address changed.

## Runtime diagnostics

Diagnostics are stored under `%LOCALAPPDATA%\FinduptoVPN` on Windows and the system temporary directory on other platforms:

- `diagnostic.log` — discovery, runtime, route, and connection diagnostics
- `servers.json` — short-lived validated discovery cache
- `openvpn-logs\<server>-last-failure.log` — latest failed connection log

Do not publish raw diagnostic logs because network identifiers and operational details may be sensitive.

## Tunnel success rule

A connection is successful only after the VPN process initializes, Windows has both full-tunnel `/1` routes, and the public IP changes. A successful TLS handshake by itself is never treated as a usable VPN connection.
