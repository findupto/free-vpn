# Findupto Free VPN

A clean Windows OpenVPN client focused on fast discovery, aggressive failover and a responsive UI.

## Architecture

- No `ThreadPoolExecutor` is used for network discovery.
- Every provider runs in its own daemon worker.
- Discovery has a hard 7-second UI deadline and never joins slow workers.
- Results are streamed into the UI as soon as a provider succeeds.
- Local cache survives temporary provider outages for up to 7 days.
- Providers currently include VPN Gate HTTPS, VPN Gate Japan, VPN Gate HTTP fallback and VPNBook.
- Servers are ranked using latency, advertised speed, uptime and provider score when available.
- OpenVPN connection attempts use the original profile first and then TCP 443, TCP 80 and UDP 53 variants where possible.
- Connection attempts have short deadlines and automatically fail over instead of hanging indefinitely.

## Windows

Install OpenVPN Community separately, then run the generated executable from the GitHub Actions artifact.

The project intentionally does not bundle or promise ownership of third-party VPN infrastructure. Public free VPN endpoints can disappear or be blocked by networks.
