# Findupto Free VPN 4.0

A Windows desktop VPN client and free-server directory focused on **fast discovery, stale-cache availability, smart server ranking, and connection failover**.

## What changed in 4.0

- Fixed the refresh deadlock that could produce `3 (of 3) futures unfinished`.
- Discovery no longer uses a `ThreadPoolExecutor` context manager that waits for timed-out mirrors.
- VPN Gate mirrors race in parallel with a hard discovery deadline.
- Optional `FINDUPTO_API_URL` is queried as another discovery method.
- Gzip/deflate responses are accepted to reduce large CSV transfer time.
- Fresh local cache is returned immediately.
- Stale cache up to 7 days can keep the application usable while upstream sources are down.
- Slow/broken sources are cancelled without blocking the UI.
- Server lists from successful sources are merged and smart-ranked.
- Existing OpenVPN connection engine keeps UDP first and supports TCP fallback variants.
- Windows CI now packages `client/launcher.py`, which installs the resilient discovery layer without replacing the existing UI.
- API serves stale disk cache immediately and refreshes upstream in the background.

## Windows client

The installer includes the Findupto client and installs official OpenVPN Community when required. The client uses public VPN Gate OpenVPN profiles and should treat every public VPN relay as an untrusted exit point.

## Discovery settings

Optional environment variables:

- `FINDUPTO_API_URL` — Findupto API base URL; when set it becomes an additional server source.
- `VPN_LIVE_TIMEOUT` — client live-discovery deadline; default `9` seconds.
- `VPN_STALE_MAX_AGE` — maximum cached-server age; default 7 days.
- `VPN_CACHE_TTL` — API fresh-cache lifetime; default 300 seconds.
- `VPN_FETCH_TIMEOUT` — API upstream timeout; default 9 seconds.

## Build Windows client

```powershell
pip install -r client/requirements.txt
pip install pyinstaller
pyinstaller --noconfirm --clean --onefile --windowed --paths client --name FinduptoVPN client/launcher.py
```

Or run `build_windows.bat` on Windows. GitHub Actions performs the same resilient launcher build and creates the standalone Inno Setup installer.

## Important limitation

No free public VPN directory can guarantee that a relay is online, fast, private, or safe. Findupto can fail over between available relays, but it cannot manufacture a working server when every public relay is unreachable. A real always-on service requires controlled servers under your administration.

## Security

- Never commit private WireGuard keys.
- Use HTTPS for API and configuration endpoints.
- Treat public/community VPN nodes as untrusted exit points.
- Do not log user traffic.
- Keep node registration authenticated in production.

## License

MIT
