# Findupto Free VPN 3.0

A Windows desktop VPN client and free-server directory focused on fast discovery, smart server ranking, cache-first startup, and automatic OpenVPN failover.

## What changed

- **Parallel server-source racing:** the client queries all VPN Gate mirrors concurrently and immediately uses the first valid result.
- **Longer streaming timeout:** large ~1 MB directory responses are no longer killed by a 7-second download limit.
- **Persistent cache fallback:** a recent server list remains usable when VPN Gate is slow or temporarily unavailable.
- **Smart ranking:** speed, latency, uptime and source score are combined to select better free relays.
- **Fast Connect:** probes multiple top-ranked relays concurrently before attempting OpenVPN.
- **Protocol fallback:** OpenVPN profiles can be retried using the original transport and TCP variants such as TCP/443 when supported.
- **Automatic OpenVPN runtime:** the Windows client detects an existing OpenVPN installation and can install the official runtime when required.
- **Non-blocking UI:** discovery, probing and connection work stay off the Tkinter UI thread.
- **Better diagnostics:** connection failures and runtime state are written to the local Findupto log.
- **API resilience:** the FastAPI service races upstream mirrors, caches successful results to disk, and serves the last good cache when upstream sources fail.

## Important limitation

Free public VPN relays are inherently unreliable and can be slow, overloaded or offline. Findupto improves selection and failover but cannot guarantee that a third-party relay will accept a connection or provide a specific speed.

## Windows client

Run the installer as Administrator. The application uses official OpenVPN Community software for VPN Gate OpenVPN relays.

## Performance defaults

The desktop client uses a 20-second per-source directory timeout and races three mirrors instead of trying curl, PowerShell and urllib sequentially for every mirror. A cached directory is shown immediately at startup while the live list refreshes in the background.

The API uses a 10-minute cache by default and a 30-second upstream read timeout.

Environment variables:

- `VPN_CACHE_TTL` — API cache lifetime in seconds; default `600`.
- `VPN_FETCH_TIMEOUT` — API upstream read timeout; default `30` seconds.
- `VPN_CACHE_FILE` — persistent API cache path.
- `FINDUPTO_API_KEY` — required for community-node registration and heartbeat endpoints.

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

The GitHub Actions workflow builds the EXE, downloads an official OpenVPN Community MSI with source failover, validates it, and creates `Findupto-Free-VPN-Setup.exe` with Inno Setup.

Push a `v*` tag to publish the installer as a GitHub Release.

## Security

- Treat public VPN nodes as untrusted exit points.
- Never commit private VPN keys or credentials.
- Use HTTPS for API and configuration endpoints where available.
- Do not log user traffic.
- Keep node registration authenticated in production.

## License

MIT
