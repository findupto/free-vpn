# Findupto Free VPN

An open-source VPN platform designed to provide **free VPN access through community-operated WireGuard servers**.

> Important: a VPN service cannot magically create free servers in every country. Each VPN exit node needs a real machine/network with bandwidth. This project therefore uses a community model: people can contribute nodes, and the directory exposes healthy nodes to clients.

## Goals

- WireGuard-first VPN networking
- Free/community-operated servers
- Automatic server health checks
- Geographic server discovery
- Short-lived client configurations
- No third-party VPN credentials or paid VPN account scraping
- Easy Docker deployment
- Open API for VPN clients

## Recommended free VPN references

Current 2026 testing consistently identifies Proton VPN Free, Windscribe Free and PrivadoVPN Free among the stronger free VPN choices. Proton VPN Free offers unlimited data and free servers in a limited set of countries; Windscribe Free offers 10 GB/month with servers in 10 countries. These are useful benchmarks, but their servers and credentials are **not** redistributed by this project.

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
                         Findupto Client
```

## Quick start

### API

```bash
docker compose up --build
```

The API will be available on `http://localhost:8080`.

### Add a community node

Each contributor runs WireGuard on a VPS, home server, Raspberry Pi, or other suitable host and registers only the public endpoint and public key with the directory. **Never submit a private WireGuard key.**

The included registry API accepts node metadata and health status. A production deployment should put it behind HTTPS, authentication/rate limiting, and a persistent database.

## Free-server strategy

The project does not claim that every country will always have a free node. Availability depends on volunteers and free-tier infrastructure. The directory can aggregate nodes from many independent operators and automatically remove unhealthy nodes.

Potential infrastructure sources include legitimate free tiers, donated VPS capacity, universities/community networks where permitted, and volunteer hardware. Always follow the provider's acceptable-use policy and bandwidth limits.

## Security

- Never commit private keys.
- Generate WireGuard keys locally on the client/node.
- Use HTTPS for the registry API.
- Do not log user traffic.
- Keep node registration authenticated in production.
- Rotate node/client credentials.
- Treat community nodes as untrusted exit points.

## License

MIT
