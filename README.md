# Findupto VPN

A lightweight desktop VPN client that discovers live public OpenVPN servers, ranks them, uses multiple transport methods and server endpoints, retries intelligently, and refuses to report success until the tunnel is actually usable.

## v14.0.0

This release adds a first production-hardening batch around the existing VPN engine:

- durable SQLite persistence for backend server/device metadata;
- node heartbeats, health thresholds, and stale-node handling;
- replay-resistant HMAC envelopes for control-plane requests;
- validated, expiring subscription state;
- rolling server health scoring with stale-metric expiry;
- latency, jitter, packet-loss, and bandwidth-aware server scoring;
- cross-platform DNS resolver configuration verification;
- public-IP and IPv6 connectivity diagnostics;
- stronger VPN endpoint and allowed-network validation;
- deterministic configuration signatures;
- bounded exponential reconnect backoff with cancellation;
- temporary server quarantine after repeated failures;
- privacy-safe startup diagnostic redaction;
- regression coverage for the new hardening behavior;
- project license, security policy, contribution rules, issue/PR templates, dependency update automation, and security CI.

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

Do not publish raw diagnostic logs because network identifiers and operational details may be sensitive.

## Tunnel success rule

A connection is successful only after the VPN process initializes, Windows has both full-tunnel `/1` routes, and the public IP changes. A successful TLS handshake by itself is never treated as a usable VPN connection.
