# Findupto VPN

A Windows desktop VPN client that discovers live public OpenVPN servers, ranks them, tries the fastest candidates automatically, installs bundled VPN drivers when needed, and refuses to report success until the system is actually using the tunnel.

## v13.0.0

This release removes the old machine-level runtime dependency from the application path and hardens the exact failures shown in the diagnostic logs:

- no curl dependency for discovery or public-IP checks;
- standalone runtime layer with its own OpenVPN executable lookup;
- CI packages the official OpenVPN 2.7.6 Windows runtime into the executable;
- bundled driver INF packages are installed automatically when the elevated application starts a connection;
- full-tunnel verification now requires BOTH Windows routes `0.0.0.0/1` and `128.0.0.0/1`;
- route installation gets a startup delay and retries Windows route methods (`ipapi`, `service`, `adaptive`);
- `show-net-up` is enabled for authoritative OpenVPN network diagnostics;
- IPv6 is blocked while using IPv4-only public VPN profiles to prevent IPv6 bypass;
- DNS outside the tunnel is blocked on Windows;
- OpenVPN 2.6+ DCO is disabled for compatibility with public profiles, with legacy cipher negotiation retained;
- the client tries more live candidates before giving up;
- successful connections are verified with both route state and a changed public IP;
- cached entries remain restricted to validated catalog formats;
- regression tests now cover the two-half-route requirement and generated profile hardening.

## Requirements

- Windows 10/11 x64
- Internet access
- Administrator/UAC approval for the standalone executable

The repository source does not commit third-party binaries. The GitHub Windows build downloads the official OpenVPN Community 2.7.6 runtime and packages it into `FinduptoVPN.exe`, so the released executable does not require a separate OpenVPN installation or curl installation.

## Run from source

```powershell
python client/app.py
```

Run tests:

```powershell
python -m unittest discover -s tests -v
```

A source checkout without the bundled runtime can still use an existing OpenVPN installation through `FINDUPTO_OPENVPN` or the normal OpenVPN Windows path.

## Runtime diagnostics

Diagnostics are stored under `%LOCALAPPDATA%\FinduptoVPN`:

- `diagnostic.log` — discovery, route, runtime and connection diagnostics
- `servers.json` — short-lived validated discovery cache
- `openvpn-logs\<server>-last-failure.log` — latest failed connection log

## Tunnel success rule

A connection is successful only when Windows has both full-tunnel `/1` routes and the public IP changes. An OpenVPN TLS connection by itself is never considered success.
