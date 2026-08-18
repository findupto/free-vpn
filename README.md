# Findupto Free VPN

An open-source VPN platform designed to provide **free VPN access through community-operated WireGuard servers**.

> Important: a VPN service cannot magically create free servers in every country. Each VPN exit node needs a real machine/network with bandwidth. This project therefore uses a community model: people can contribute nodes, and the directory exposes healthy nodes to clients.

## Windows desktop app

The project now includes a native Windows desktop client. It runs as a normal `.exe` application and does **not** require a web browser. The installer bundles the official WireGuard for Windows MSI, creates a desktop shortcut, and installs the WireGuard networking component automatically. WireGuard supports Windows 10/11 and exposes a tunnel-service CLI that the client uses to start and stop VPN tunnels.

The GitHub Actions workflow builds `Findupto-Free-VPN-Setup.exe` automatically. Push a `v*` tag to publish a GitHub Release containing the installer.

### Desktop client architecture

```text
FinduptoVPN.exe
     |
     | HTTPS
     v
Findupto API ---- healthy WireGuard nodes
     |
     | short-lived client config URL
     v
WireGuard for Windows
     |
     v
VPN tunnel
```

The client only connects to registered `wireguard` nodes that expose a `config_url`. A node registration must never contain a private WireGuard key. The config URL should issue a short-lived client configuration from trusted node infrastructure.

### API URL

The desktop client reads `FINDUPTO_API_URL` from the environment. If it is not set, it uses the configured default in `client/app.py`. For production, point this value at your HTTPS deployment of this API before distributing the installer.

## Goals

- WireGuard-first VPN networking
- Free/community-operated servers
- Automatic server health checks
- Geographic server discovery
- Short-lived client configurations
- No third-party VPN credentials or paid VPN account scraping
- Easy Docker deployment
- Open API for VPN clients
- Native Windows desktop client
- Standalone Windows installer

## Performance improvements

The API now caches the external VPN Gate directory for a short TTL and performs the blocking upstream fetch outside the FastAPI event loop. This prevents every client request from waiting on the external provider and substantially reduces repeated network latency. Community WireGuard nodes are kept in-memory and sorted deterministically for fast client discovery.

## Architecture

```text
                    +----------------------+
                    |  Findupto API        |
                    |  server directory     |
                    +----------+-----------+
                               |
                 health checks | node metadata
                               v
        +----------------------+----------------------+
        |                      |                      |
   WireGuard Node         WireGuard Node         WireGuard Node
     USA / Dallas          Germany / Frankfurt      Singapore
        |                      |                      |
        +----------------------+----------------------+
                               |
                         FinduptoVPN.exe
                               |
                         WireGuard Windows
```

## Quick start

### API

```bash
docker compose up --build
```

The API will be available on `http://localhost:8080`.

### Windows client development

```powershell
pip install -r client/requirements.txt
pyinstaller --noconfirm --clean --onefile --windowed --name FinduptoVPN client/app.py
```

The generated executable is `dist/FinduptoVPN.exe`.

### Windows installer

The GitHub Actions workflow builds a standalone installer with Inno Setup and bundles the official WireGuard AMD64 MSI. The installer requires administrator privileges because a VPN tunnel driver/service must be installed at the Windows system level.

## Add a community node

Each contributor runs WireGuard on a VPS, home server, Raspberry Pi, or other suitable host and registers only the public endpoint and public key with the directory. Never submit a private WireGuard key. For desktop-client connectivity, provide a `config_url` that returns a short-lived client WireGuard configuration.

The included registry API accepts node metadata and health status. A production deployment should put it behind HTTPS, authentication/rate limiting, and a persistent database.

## Free-server strategy

The project does not claim that every country will always have a free node. Availability depends on volunteers and free-tier infrastructure. The directory can aggregate nodes from many independent operators and automatically remove unhealthy nodes.

Potential infrastructure sources include legitimate free tiers, donated VPS capacity, universities/community networks where permitted, and volunteer hardware. Always follow the provider's acceptable-use policy and bandwidth limits.

## Security

- Never commit private keys.
- Generate WireGuard keys locally on the client/node.
- Use HTTPS for the registry API and config endpoints.
- Do not log user traffic.
- Keep node registration authenticated in production.
- Rotate node/client credentials.
- Prefer short-lived client configurations.
- Treat community nodes as untrusted exit points.

## License

MIT
