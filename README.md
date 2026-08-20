# Findupto VPN

A lightweight desktop VPN client that discovers live public OpenVPN servers, ranks them, retries multiple profiles and servers, and refuses to report success until the tunnel is actually usable.

## v13.1.0

This release focuses on reliability, portability, and faster recovery from broken public VPN endpoints:

- standalone runtime version is now consistent across the application;
- the packaged Windows build bundles the official OpenVPN Community 2.7.6 runtime;
- OpenVPN lookup prefers the bundled runtime, then `FINDUPTO_OPENVPN`, then the system PATH;
- Windows route retries use valid OpenVPN route methods (`adaptive`, `ipapi`, `exe`);
- full-tunnel verification requires both Windows `0.0.0.0/1` and `128.0.0.0/1` routes;
- IPv6 is blocked on Windows for IPv4-only public profiles to prevent common IPv6 bypasses;
- Windows outside-DNS blocking is enabled for the generated profile;
- OpenVPN 2.6+ DCO is disabled for compatibility with public community profiles;
- legacy cipher negotiation is retained for older server configurations;
- discovery remains concurrent and cache-backed so slow or dead public catalogs do not block the UI;
- only validated VPN Gate and VPNBook catalog formats can enter the cache or connection path;
- the client retries more candidates before giving up;
- successful connections are verified with route state and a changed public IP;
- the GUI scales down to smaller desktop displays and supports horizontal scrolling;
- diagnostic log opening works on Windows, macOS, and Linux;
- regression tests cover profile hardening, route validation, legacy ciphers, cache validation, and platform-specific route options.

## Supported platforms

- **Windows 10/11 x64:** packaged standalone executable with bundled OpenVPN runtime and automatic UAC elevation.
- **Linux/macOS:** source execution is supported when OpenVPN and Tkinter are installed; use `FINDUPTO_OPENVPN` when OpenVPN is outside the normal PATH.

Android and iOS are not supported by this desktop Tkinter application. They require native VPN APIs and a separate mobile client architecture.

## Requirements

### Windows packaged build

- Windows 10/11 x64
- Internet access
- Administrator/UAC approval

The repository does not commit third-party binaries. GitHub Actions downloads the official OpenVPN Community 2.7.6 Windows runtime and packages it into `FinduptoVPN.exe`.

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
