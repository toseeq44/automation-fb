"""
Centralized pacing / delay management.

Replaces scattered time.sleep() calls with a stateful manager that tracks
batch progress and applies plan-aware delays.
"""

import random
import time
from typing import Optional


_PRO_PLANS = {"pro", "yearly", "premium"}


def resolve_user_plan(explicit_plan: Optional[str] = None) -> str:
    """Resolve user plan as 'basic' or 'pro'."""
    if explicit_plan:
        plan = str(explicit_plan).strip().lower()
        return "pro" if plan in _PRO_PLANS else "basic"

    try:
        from modules.license import LicenseManager

        info = LicenseManager().get_license_info() or {}
        plan_type = str(info.get("plan_type", "basic")).strip().lower()
        return "pro" if plan_type in _PRO_PLANS else "basic"
    except Exception:
        return "basic"


def get_delay_multiplier(user_plan: Optional[str] = None) -> float:
    """Return delay multiplier by plan.

    basic -> 1.0x
    pro   -> 2.0x
    """
    return 2.0 if resolve_user_plan(user_plan) == "pro" else 1.0


class PacingManager:
    """Stateful delay tracker with batch cooldowns and plan multiplier."""

    def __init__(self, batch_size: int = 10, user_plan: Optional[str] = None):
        self._batch_size = batch_size
        self._op_count = 0
        self._user_plan = resolve_user_plan(user_plan)
        self._delay_multiplier = get_delay_multiplier(self._user_plan)

    def scale_delay(self, base_delay: float) -> float:
        """Scale any base delay using current plan multiplier."""
        return max(0.0, float(base_delay)) * self._delay_multiplier

    def pace_operation(self) -> float:
        """Standard delay between operations (2-4s + batch cooldown every ~N ops)."""
        self._op_count += 1
        delay = random.uniform(2.0, 4.0)

        # Batch cooldown
        if self._op_count % self._batch_size == 0:
            delay += random.uniform(3.0, 7.0)

        delay = self.scale_delay(delay)
        time.sleep(delay)
        return delay

    def pace_after_failure(self) -> float:
        """Longer delay after a failure (3-6s)."""
        delay = self.scale_delay(random.uniform(3.0, 6.0))
        time.sleep(delay)
        return delay

    def pace_short(self) -> float:
        """Short delay for lightweight operations (0.5-1.5s)."""
        delay = self.scale_delay(random.uniform(0.5, 1.5))
        time.sleep(delay)
        return delay

    @property
    def operation_count(self) -> int:
        return self._op_count

    @property
    def user_plan(self) -> str:
        return self._user_plan

    @property
    def delay_multiplier(self) -> float:
        return self._delay_multiplier

    def reset(self):
        """Reset the operation counter."""
        self._op_count = 0
