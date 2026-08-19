# Findupto VPN

A clean Windows VPN client that discovers legitimate public VPN configurations, ranks them, verifies tunnel establishment, and automatically fails over.

## Current design

- Provider adapters are isolated; one broken provider cannot block another.
- No `ThreadPoolExecutor` or blocking future pool is used for discovery.
- VPN Gate is consumed from its official public API.
- VPNBook is consumed from its current official OpenVPN page and only published configuration links are accepted; the client never invents download URLs.
- A 7-day local cache lets the UI start when public discovery is temporarily unavailable.
- Server candidates are ranked using advertised latency, speed, uptime and score when available.
- OpenVPN connection attempts use the provider profile first, followed by TCP 443, TCP 80, UDP 53 and UDP 25000 variants when the profile permits it.
- `Connect Best` automatically tries up to 12 candidates and stops only after a tunnel is established and the public IP has changed.
- `.ovpn` import is supported for legitimate configurations from other providers.
- Network discovery is asynchronous and cannot freeze the Tkinter UI.

## Windows requirements

Install **OpenVPN Community** separately. The application does not bundle third-party VPN software or credentials.

The GitHub Actions workflow runs Python compilation, unit tests, and then produces `FinduptoVPN.exe`.

## Important limitation

There is no technically honest way to guarantee that public free VPN servers work forever. Providers can change credentials, remove servers, become overloaded, or be blocked by a network. This client is designed so those conditions cause provider/server failover rather than an application crash.

VPNBook currently publishes free OpenVPN and WireGuard service with changing credentials and server configurations, while VPN Gate publishes a live public relay list. The client therefore discovers current data instead of shipping a stale list.
