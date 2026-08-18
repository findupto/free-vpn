# Findupto Free VPN

A Windows desktop VPN client and free-server directory focused on fast discovery, reliable connection handling, and automatic VPN runtime installation.

## What is fixed

- Server discovery uses API-side caching and client-side cache fallback instead of waiting indefinitely for a remote source.
- External server fetches have strict timeouts and stale cached servers remain usable when the upstream source is temporarily unavailable.
- VPN Gate OpenVPN servers are handled as OpenVPN servers instead of being incorrectly treated as WireGuard nodes.
- The Windows installer now installs both official OpenVPN Community and WireGuard runtimes so the client does not fail because OpenVPN is missing.
- The Windows client verifies the runtime before connecting, runs connection work off the UI thread, records OpenVPN logs, and detects when the OpenVPN process exits.
- The installer workflow validates downloaded runtime installers and verifies that the final installer was actually created.
- `Best Server` selects the top-ranked currently available server.

The official OpenVPN Community project publishes Windows installers for Windows 10 and later. urlOpenVPN Community Downloadshttps://openvpn.net/community/

## Windows client

Run the installer as administrator. It installs:

- Findupto Free VPN
- OpenVPN Community for OpenVPN servers
- WireGuard for Windows for community WireGuard servers

The application can use either protocol based on the server record.

## Performance

The API caches the external VPN Gate directory for 5 minutes by default and performs the blocking upstream request outside the FastAPI event loop. The desktop client also keeps a short-lived local server cache, so opening the application does not require a fresh upstream request every time.

Environment variables:

- `VPN_CACHE_TTL` — API cache lifetime in seconds; default `300`.
- `VPN_FETCH_TIMEOUT` — API upstream timeout; default `8` seconds.
- `FINDUPTO_API_URL` — desktop API endpoint override.

## Development

### API

```bash
docker compose up --build
```

### Windows client

```powershell
pip install -r client/requirements.txt
pip install pyinstaller
pyinstaller --noconfirm --clean --onefile --windowed --name FinduptoVPN client/app.py
```

### Installer

The GitHub Actions workflow builds the EXE, downloads the official OpenVPN Community and WireGuard Windows installers, validates them, and creates `Findupto-Free-VPN-Setup.exe` with Inno Setup.

Push a `v*` tag to publish the installer as a GitHub Release.

## Security

- Never commit private WireGuard keys.
- Use HTTPS for API and configuration endpoints.
- Treat public/community VPN nodes as untrusted exit points.
- Do not log user traffic.
- Keep node registration authenticated in production.
- Prefer short-lived WireGuard client configurations.

## License

MIT
