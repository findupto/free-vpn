# Findupto VPN

A Windows OpenVPN client that discovers **live free VPN servers**, ranks them by advertised performance, connects with automatic failover, and verifies that browser traffic is actually using the VPN tunnel.

## What is real and functional

- **VPN Gate live discovery:** server IPs, hostnames, ping, speed, uptime and OpenVPN configs are fetched from the public VPN Gate API instead of shipping a stale IP list.
- **VPNBook live discovery:** the official OpenVPN page is parsed for currently published configuration bundles and the current password is read from the official credentials page at connection time.
- **Fastest-first connection:** VPN Gate relays are ranked using live advertised ping/speed/uptime/score; the best candidates are tried automatically.
- **Browser-ready system tunnel:** successful OpenVPN connections install a full-tunnel route on Windows, so normal Chrome, Edge, Firefox and other applications use the VPN without browser-specific extensions.
- **Real verification:** the client checks the Windows full-tunnel routes and confirms that the public IP changed before showing `CONNECTED`.
- **Automatic protocol fallback:** VPNBook profiles are tried in TCP 443, TCP 80, UDP 53 and UDP 25000 order when those profiles are published.
- **No fake server/IP database:** public server addresses are intentionally not hardcoded because free relays and IPs change frequently.
- **Clear diagnostics:** every OpenVPN attempt gets its own log and errors are classified instead of being hidden behind a generic exit-code message.
- **Clean entry point:** `client/app.py` is the only application launcher; duplicate/dead backend and launcher scripts were removed.

## Windows requirements

Install **OpenVPN Community** separately. The project does not bundle third-party VPN software or claim ownership of public relay infrastructure.

Run the application with administrator privileges if Windows/OpenVPN requires elevation to create the TUN adapter or install routes.

## Free server sources

Current free server sources include:

- urlVPN Gatehttps://www.vpngate.net/ — public volunteer relays with live IP/configuration data.
- urlVPNBook OpenVPNhttps://www.vpnbook.com/freevpn/openvpn — currently published free OpenVPN servers and changing credentials.

Free public VPNs can disappear, become overloaded, change credentials, or be blocked. The client therefore discovers current data and fails over rather than pretending a fixed server/IP is guaranteed to work.

## Build

GitHub Actions compiles the project, runs the unit tests, and builds `FinduptoVPN.exe` from `client/app.py`.
