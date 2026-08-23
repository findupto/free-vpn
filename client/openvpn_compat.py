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
                fields[1] = ip
                line = " ".join(fields)
                replaced = True
        out.append(line)
    if not replaced:
        out.insert(0, f"remote {ip} 443 tcp-client")
    return "\n".join(out) + "\n"


def install(engine) -> None:
    """Install the profile wrapper on the module that actually owns _profiles.

    standalone_engine is a facade over vpn_engine and does not expose every
    private helper from the base engine. Older startup code assumed it did,
    which caused the application to fail before the GUI could start.
    """
    if getattr(engine, "_findupto_openvpn_compat", False):
        return

    target = engine if hasattr(engine, "_profiles") else getattr(engine, "base", None)
    if target is None or not hasattr(target, "_profiles"):
        # Never make the application unstartable merely because the optional
        # compatibility wrapper cannot be installed. The normal engine can
        # still operate with its provider profile unchanged.
        try:
            engine.log("OPENVPN COMPAT SKIPPED: profile provider unavailable")
        except Exception:
            pass
        return

    original_profiles = target._profiles

    def profiles(server: dict):
        result = original_profiles(server)
        if server.get("kind") != "gate":
            return result
        configs, username, password = result
        hardened = [_rewrite_gate_profile(config, server) for config in configs]
        username = str(username or "vpn") or "vpn"
        password = str(password or "vpn") or "vpn"
        engine.log(
            f"VPNGATE PROFILE HARDENED host={server.get('host')} "
            f"ip={server.get('ip')} profiles={len(hardened)} auth_source=provider-default"
        )
        return hardened, username, password

    target._profiles = profiles
    target._findupto_openvpn_compat = True
    engine._findupto_openvpn_compat = True
