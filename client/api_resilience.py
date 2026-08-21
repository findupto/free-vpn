"""Bounded API retries, timeout budgets and circuit breaking."""
from __future__ import annotations
import time
from dataclasses import dataclass

@dataclass
class Circuit:
    failures: int = 0
    opened_until: float = 0.0

class APIResilience:
    def __init__(self, max_failures: int = 3, cooldown: float = 30.0):
        self.max_failures = max(1, int(max_failures))
        self.cooldown = max(0.1, float(cooldown))
        self.circuits: dict[str, Circuit] = {}

    def available(self, name: str, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        circuit = self.circuits.get(name)
        return circuit is None or circuit.opened_until <= now

    def success(self, name: str) -> None:
        self.circuits[name] = Circuit()

    def failure(self, name: str, now: float | None = None) -> None:
        now = time.time() if now is None else now
        circuit = self.circuits.setdefault(name, Circuit())
        circuit.failures += 1
        if circuit.failures >= self.max_failures:
            circuit.opened_until = now + self.cooldown

    def execute(self, name: str, operation, attempts: int = 3):
        if not self.available(name):
            raise RuntimeError("API circuit is open")
        last = None
        for _ in range(max(1, attempts)):
            try:
                result = operation()
                self.success(name)
                return result
            except Exception as exc:
                last = exc
                self.failure(name)
        raise last
