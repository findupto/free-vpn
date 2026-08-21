"""Safe MTU/MSS policy calculations; does not mutate host networking."""
from __future__ import annotations

MIN_MTU = 576
MAX_MTU = 9000


def validate_mtu(mtu: int) -> int:
    mtu = int(mtu)
    if not MIN_MTU <= mtu <= MAX_MTU:
        raise ValueError(f"MTU must be between {MIN_MTU} and {MAX_MTU}")
    return mtu


def tunnel_mtu(path_mtu: int, overhead: int = 60) -> int:
    path_mtu = validate_mtu(path_mtu)
    if overhead < 0 or overhead >= path_mtu:
        raise ValueError("invalid tunnel overhead")
    return path_mtu - overhead


def mss_for_mtu(mtu: int, ip_header: int = 20, tcp_header: int = 20) -> int:
    mtu = validate_mtu(mtu)
    if ip_header < 0 or tcp_header < 0 or ip_header + tcp_header >= mtu:
        raise ValueError("invalid header sizes")
    return mtu - ip_header - tcp_header
