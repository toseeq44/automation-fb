"""
Two-step recovery chain for auth failures.

Step A: Cookie refresh — ensure_fresh_cookies() re-exports from profile DB.
Step B: Browser session recovery — force_browser_cookie_refresh() navigates
        to the platform URL in a live context, causing token rotation.

Module-level shared cooldown prevents rapid re-attempts.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from modules.shared.failure_classifier import FailureType

logger = logging.getLogger(__name__)

# ── Module-level shared cooldown ──────────────────────────────
_recovery_cooldowns: dict[str, float] = {}
_COOLDOWN_SECONDS = 120  # 2 minutes between recovery attempts per platform


@dataclass
class RecoveryResult:
    """Outcome of a recovery attempt."""
    cookie_path: Optional[str] = None
    recovery_type: str = "none"
    attempted_step_a: bool = False
    attempted_step_b: bool = False


class RecoveryChain:
    """Two-step recovery: cookie refresh then browser session recovery."""

    def attempt_recovery(
        self, platform: str, failure_type: FailureType
    ) -> RecoveryResult:
        """Run the two-step recovery chain for a platform.

        Returns RecoveryResult with cookie_path if recovery produced
        a usable cookie file, or None if both steps failed.
        """
        result = RecoveryResult()

        # Cooldown check
        last_attempt = _recovery_cooldowns.get(platform, 0)
        if time.time() - last_attempt < _COOLDOWN_SECONDS:
            logger.info(
                "[RecoveryChain] Skipping %s — cooldown active (last attempt %.0fs ago)",
                platform, time.time() - last_attempt,
            )
            return result

        _recovery_cooldowns[platform] = time.time()

        try:
            from modules.shared.session_authority import get_session_authority
            sa = get_session_authority()
        except Exception as e:
            logger.warning("[RecoveryChain] Cannot get SessionAuthority: %s", e)
            return result

        # ── Step A: Cookie refresh (re-export from profile DB) ────────
        result.attempted_step_a = True
        try:
            cookie_path = sa.ensure_fresh_cookies(platform)
            if cookie_path:
                logger.info(
                    "[RecoveryChain] Step A succeeded for %s: %s",
                    platform, cookie_path,
                )
                result.cookie_path = cookie_path
                result.recovery_type = "cookie_refresh"
                return result
            logger.info("[RecoveryChain] Step A: no fresh cookies for %s", platform)
        except Exception as e:
            logger.warning("[RecoveryChain] Step A failed for %s: %s", platform, e)

        # ── Step B: Browser session recovery (live-context navigation) ─
        result.attempted_step_b = True
        try:
            cookie_path = sa.force_browser_cookie_refresh(platform)
            if cookie_path:
                logger.info(
                    "[RecoveryChain] Step B succeeded for %s: %s",
                    platform, cookie_path,
                )
                result.cookie_path = cookie_path
                result.recovery_type = "browser_refresh"
                return result
            logger.info("[RecoveryChain] Step B: no live cookies for %s", platform)
        except Exception as e:
            logger.warning("[RecoveryChain] Step B failed for %s: %s", platform, e)

        logger.info("[RecoveryChain] Both steps failed for %s", platform)
        return result
