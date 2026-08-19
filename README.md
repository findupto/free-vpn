# Findupto VPN

A lightweight Windows desktop VPN client that discovers public OpenVPN profiles from live public catalogs, ranks candidates, connects through OpenVPN Community, and verifies that the system public IP actually changed.

## v12.0.0

This release focuses on the OpenVPN 2.7.x failures reported in the diagnostic logs:

- fixes generated OpenVPN Windows paths by writing forward-slash paths in `.ovpn` files;
- removes obsolete `fast-io` and `persist-key` directives from generated profiles;
- keeps OpenVPN 2.6+ DCO disabled for compatibility with public profiles;
- preserves legacy cipher compatibility through `data-ciphers` / `data-ciphers-fallback`;
- keeps compression only when the downloaded public profile explicitly requires it;
- stops creating four permanent log files for every failed server;
- retains only the latest failed OpenVPN log for troubleshooting;
- removes stale/invalid cached server entries before reuse;
- accepts VPNBook configuration bundles only when linked by the live official page;
- keeps curl optional and falls back to Python `urllib` when the installed curl lacks features;
- verifies full-tunnel Windows routes and public IP before reporting a connection as successful;
- adds regression coverage for the Windows backslash configuration failure;
- hardens Windows CI and executable packaging.

## Requirements

- Windows 10/11
- OpenVPN Community installed and available at the normal OpenVPN path
- Administrator permission may be required by Windows/OpenVPN to create the tunnel adapter and routes
- Internet access for live server discovery

The application does not bundle third-party VPN credentials or hard-code a VPNBook password. Public VPN catalogs are volatile and can disappear or reject connections at any time.

## Run from source

```powershell
python client/app.py
```

Run the tests with:

```powershell
python -m unittest discover -s tests -v
```

## Runtime files

The application stores diagnostics under `%LOCALAPPDATA%\FinduptoVPN`:

- `diagnostic.log` — application/network diagnostics
- `servers.json` — short-lived validated discovery cache
- `openvpn-logs\<server>-last-failure.log` — latest failed OpenVPN attempt only

Successful connection profiles remain temporary and are deleted when disconnected.

## Safety

Only live-discovered public server entries are accepted. The client verifies the tunnel before declaring success and refuses to trust arbitrary cached entries.
