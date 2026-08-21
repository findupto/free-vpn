"""Minimal subscription state with explicit expiration and plan validation."""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass(frozen=True)
class Subscription:
    plan: str
    expires_at: int | None = None


class BillingSystem:
    VALID_PLANS = {"free", "plus", "pro"}

    def __init__(self):
        self.subscriptions: dict[str, Subscription] = {}

    def activate(self, user_id: str, plan: str, expires_at: int | None = None) -> bool:
        if not user_id or plan not in self.VALID_PLANS:
            return False
        if expires_at is not None and expires_at <= int(time.time()):
            return False
        self.subscriptions[user_id] = Subscription(plan, expires_at)
        return True

    def get_plan(self, user_id: str) -> str | None:
        subscription = self.subscriptions.get(user_id)
        if subscription is None:
            return None
        if subscription.expires_at is not None and subscription.expires_at <= int(time.time()):
            return "free"
        return subscription.plan

    def is_active(self, user_id: str) -> bool:
        return self.get_plan(user_id) is not None
