from __future__ import annotations

import os, subprocess, sys
from pathlib import Path


def runtime_dir() -> Path:
    return Path(sys._MEIPASS) / "runtime" if getattr(sys, "frozen", False) else Path(__file__).resolve().parent / "runtime"


def install_bundled_drivers() -> bool:
    if os.name != "nt":
        return True
    root = runtime_dir()
    infs = list(root.rglob("*.inf")) if root.exists() else []
    if not infs:
        return False
    ok = False
    for inf in infs:
        try:
            cp = subprocess.run(
                ["pnputil.exe", "/add-driver", str(inf), "/install"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=30,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            ok = ok or cp.returncode == 0
        except Exception:
            continue
    return ok


# The desktop client imports standalone_engine first, so this module can apply
# performance policy immediately afterwards without changing the VPN engine API.
try:
    import standalone_engine as _engine

    # Prefer UDP transports. TCP-over-TCP is a common cause of severe throughput
    # collapse on free VPN relays because packet loss creates nested retransmits.
    _engine._VPNBOOK_METHODS = (
        ("udp", "25000", "udp"),
        ("udp", "53", "udp"),
        ("tcp", "443", "tcp-client"),
        ("tcp", "80", "tcp-client"),
    )

    _original_prepare = _engine._prepare

    def _high_throughput_prepare(profile, username, password, work, openvpn_version=(0, 0, 0), route_method="adaptive"):
        path = Path(_original_prepare(profile, username, password, work, openvpn_version, route_method))
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
            optimized = []
            for line in lines:
                if line.strip().lower() == "disable-dco":
                    # OpenVPN 2.6+ DCO moves the data path into the kernel and
                    # avoids the userspace packet-copy bottleneck.
                    if tuple(openvpn_version) >= (2, 6, 0):
                        continue
                optimized.append(line)

            low = {line.strip().lower() for line in optimized}
            if "sndbuf 4194304" not in low:
                optimized.append("sndbuf 4194304")
            if "rcvbuf 4194304" not in low:
                optimized.append("rcvbuf 4194304")
            if "fast-io" not in low and "proto tcp" not in profile.lower():
                optimized.append("fast-io")
            if "explicit-exit-notify 2" not in low and "proto tcp" not in profile.lower():
                optimized.append("explicit-exit-notify 2")

            path.write_text("\n".join(optimized) + "\n", encoding="utf-8")
        except Exception:
            # Never make a working VPN profile fail solely because an optional
            # performance tweak could not be applied.
            pass
        return path

    _engine._prepare = _high_throughput_prepare
except Exception:
    # Performance tuning is opportunistic; normal connection behavior remains
    # available if the optional engine import is unavailable.
    pass
