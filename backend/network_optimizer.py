"""High performance VPN networking helpers.

Adds resilient endpoint validation, timeout protection, adaptive ranking,
and safer warm connection handling for unreliable public VPN servers.
"""

from __future__ import annotations

import socket
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass


@dataclass
class EndpointResult:
    endpoint: str
    latency_ms: float
    success: bool = True
    checked_at: int = 0


class WireGuardFastPath:
    def __init__(self):
        self.enabled = True

    def enable(self):
        self.enabled = True


class UDPOptimizer:
    @staticmethod
    def tune(sock: socket.socket):
        sock.settimeout(5)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4 * 1024 * 1024)
        return sock


class MTUTuner:
    def __init__(self, default=1420):
        self.mtu = default

    def set_mtu(self, value: int):
        self.mtu = max(1280, min(value, 1500))
        return self.mtu


class TCPCongestionTuner:
    @staticmethod
    def preferred_algorithms():
        return ["bbr", "cubic"]


class EndpointRacer:
    """Race many servers and ignore dead/unresponsive endpoints."""

    def race(self, endpoints, probe, timeout=8):
        results = []
        if not endpoints:
            return results

        def safe_probe(endpoint):
            started = time.monotonic()
            try:
                latency = probe(endpoint, timeout=timeout)
                if latency is None:
                    latency = (time.monotonic() - started) * 1000
                return EndpointResult(endpoint, float(latency), True, int(time.time()))
            except Exception:
                return EndpointResult(endpoint, 999999.0, False, int(time.time()))

        workers = min(32, len(endpoints))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(safe_probe, endpoint) for endpoint in endpoints]
            for future in as_completed(futures):
                result = future.result()
                if result.success:
                    results.append(result)

        return sorted(results, key=lambda item: item.latency_ms)


class TunnelPool:
    def __init__(self, size=3):
        self.size = size
        self.pool = []

    def warm(self, connector, endpoints):
        self.pool.clear()
        for endpoint in endpoints[: self.size]:
            try:
                self.pool.append(connector(endpoint))
            except Exception:
                continue
        return len(self.pool)


performance_layer = {
    "fast_path": WireGuardFastPath(),
    "udp": UDPOptimizer(),
    "mtu": MTUTuner(),
    "tcp": TCPCongestionTuner(),
    "endpoint_racing": EndpointRacer(),
    "tunnel_pool": TunnelPool(),
}
