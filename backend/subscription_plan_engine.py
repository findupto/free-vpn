"""
Premium Subscription Plan Engine

Provides plan tiers, limits, and access policy foundation.
"""

from dataclasses import dataclass


@dataclass
class Plan:
    name: str
    bandwidth_limit: int
    device_limit: int
    priority: int


class SubscriptionPlanEngine:
    def __init__(self):
        self.plans = {
            "free": Plan("free", 10, 1, 1),
            "pro": Plan("pro", 1000, 5, 5),
            "business": Plan("business", 5000, 20, 10),
        }

    def get_plan(self, name):
        return self.plans.get(name, self.plans["free"])

    def check_access(self, plan, devices, bandwidth):
        selected = self.get_plan(plan)
        return {
            "allowed": devices <= selected.device_limit and bandwidth <= selected.bandwidth_limit,
            "priority": selected.priority,
            "plan": selected.name,
        }
