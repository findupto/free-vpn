from __future__ import annotations

"""OpenVPN compatibility hardening for public VPN Gate profiles."""


def _rewrite_gate_profile(profile: str, server: dict) -> str:
    ip = str(server.get("ip") or "").strip()
    if not ip:
        return profile
    lines = profile.splitlines()
    out: list[str] = []
    replaced = False
    for line in lines:
        stripped = line.strip()
        if stripped.lower().startswith("remote "):
            fields = stripped.split()
            if len(fields) >= 2:
                # Preserve the provider's port/protocol and only replace the
                # DDNS host, matching VPN Gate's official IP-based profile.
                fields[1] = ip
                line = " ".join(fields)
                replaced = True
        out.append(line)
    if not replaced:
        out.insert(0, f"remote {ip} 443 tcp-client")
    return "\n".join(out) + "\n"


def install(engine) -> None:
    if getattr(engine, "_findupto_openvpn_compat", False):
        return
    original_profiles = engine._profiles

    def profiles(server: dict):
        result = original_profiles(server)
        if server.get("kind") != "gate":
            return result
        configs, username, password = result
        hardened = [_rewrite_gate_profile(config, server) for config in configs]
        # VPN Gate's current public documentation specifies vpn/vpn.
        username = str(username or "vpn") or "vpn"
        password = str(password or "vpn") or "vpn"
        engine.log(
            f"VPNGATE PROFILE HARDENED host={server.get('host')} "
            f"ip={server.get('ip')} profiles={len(hardened)} auth_source=provider-default"
        )
        return hardened, username, password

    engine._profiles = profiles
    engine._findupto_openvpn_compat = True
