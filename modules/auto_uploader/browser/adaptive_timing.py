"""
Adaptive Timing System
======================

Intelligent wait time management based on system performance, network conditions,
and action types. This module ensures optimal timing for various browser automation
actions, adapting to different system speeds and network conditions.

Features:
- System performance measurement
- Network speed detection
- Adaptive wait times for different actions
- Condition-based waiting with timeout
- Smart retry timing with exponential backoff
"""

import logging
import time
import platform
import subprocess
from typing import Callable, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum


class ActionType(Enum):
    """Types of actions that require waiting."""
    PAGE_LOAD = "page_load"
    FORM_SUBMIT = "form_submit"
    DROPDOWN_OPEN = "dropdown_open"
    WINDOW_ACTIVATE = "window_activate"
    LOGIN_VERIFY = "login_verify"
    LOGOUT_VERIFY = "logout_verify"
    FIELD_FILL = "field_fill"
    BUTTON_CLICK = "button_click"
    IMAGE_DETECTION = "image_detection"
    BROWSER_LAUNCH = "browser_launch"


@dataclass
class SystemMetrics:
    """System performance metrics."""
    cpu_score: float  # 0.0 to 1.0 (higher is faster)
    memory_available: float  # GB
    platform: str

    @property
    def is_slow(self) -> bool:
        """Check if system is considered slow."""
        return self.cpu_score < 0.5 or self.memory_available < 2.0

    @property
    def is_fast(self) -> bool:
        """Check if system is considered fast."""
        return self.cpu_score > 0.8 and self.memory_available > 4.0


class AdaptiveTiming:
    """
    Intelligent timing system that adapts to system performance and network conditions.

    This class provides smart wait times that automatically adjust based on:
    - System CPU performance
    - Available memory
    - Network speed
    - Action type
    - Historical performance

    Example:
        >>> timing = AdaptiveTiming()
        >>> # Smart wait for page load
        >>> timing.smart_wait(ActionType.PAGE_LOAD)
        >>>
        >>> # Wait for condition with timeout
        >>> success = timing.wait_for_condition(
        ...     lambda: check_login_status() == "logged_in",
        ...     timeout=30,
        ...     check_interval=0.5
        ... )
    """

    # Base wait times for different actions (in seconds)
    BASE_WAIT_TIMES: Dict[ActionType, float] = {
        ActionType.PAGE_LOAD: 3.0,
        ActionType.FORM_SUBMIT: 2.0,
        ActionType.DROPDOWN_OPEN: 1.0,
        ActionType.WINDOW_ACTIVATE: 0.5,
        ActionType.LOGIN_VERIFY: 2.0,
        ActionType.LOGOUT_VERIFY: 2.0,
        ActionType.FIELD_FILL: 0.3,
        ActionType.BUTTON_CLICK: 0.5,
        ActionType.IMAGE_DETECTION: 0.2,
        ActionType.BROWSER_LAUNCH: 5.0,
    }

    def __init__(self, enable_network_check: bool = False):
        """
        Initialize adaptive timing system.

        Args:
            enable_network_check: Enable network speed measurement (adds startup delay)
        """
        self.system_metrics = self._measure_system_performance()
        self.network_speed = 1.0  # Default to normal speed
        self.enable_network_check = enable_network_check

        # Performance multipliers
        self.system_multiplier = self._calculate_system_multiplier()
        self.network_multiplier = 1.0

        # Timing history for adaptive learning
        self.timing_history: Dict[ActionType, list] = {}

        logging.debug(
            "AdaptiveTiming initialized - System: %s (multiplier: %.2f)",
            "FAST" if self.system_metrics.is_fast else "SLOW" if self.system_metrics.is_slow else "NORMAL",
            self.system_multiplier
        )

    def smart_wait(self, action_type: ActionType, custom_multiplier: float = 1.0) -> float:
        """
        Perform an intelligent wait based on action type and system performance.

        Args:
            action_type: Type of action being performed
            custom_multiplier: Additional custom multiplier (default: 1.0)

        Returns:
            Actual wait time used (in seconds)

        Example:
            >>> timing = AdaptiveTiming()
            >>> actual_wait = timing.smart_wait(ActionType.PAGE_LOAD)
            >>> print(f"Waited {actual_wait:.2f} seconds")
        """
        base_wait = self.BASE_WAIT_TIMES.get(action_type, 1.0)

        # Calculate adaptive wait time
        wait_time = base_wait * self.system_multiplier * self.network_multiplier * custom_multiplier

        # Apply bounds (minimum 0.1s, maximum 30s)
        wait_time = max(0.1, min(wait_time, 30.0))

        logging.debug(
            "Smart wait: %s - base=%.2fs, multipliers=(sys:%.2f, net:%.2f, custom:%.2f) -> %.2fs",
            action_type.value,
            base_wait,
            self.system_multiplier,
            self.network_multiplier,
            custom_multiplier,
            wait_time
        )

        time.sleep(wait_time)

        # Record timing for learning
        if action_type not in self.timing_history:
            self.timing_history[action_type] = []
        self.timing_history[action_type].append(wait_time)

        return wait_time

    def wait_for_condition(
        self,
        condition_func: Callable[[], bool],
        timeout: float = 30.0,
        check_interval: float = 0.5,
        action_name: str = "condition"
    ) -> bool:
        """
        Wait until a condition is true or timeout is reached.

        This is a robust alternative to fixed time.sleep() calls, allowing code
        to proceed as soon as a condition is met instead of waiting unnecessarily.

        Args:
            condition_func: Function that returns True when condition is met
            timeout: Maximum time to wait in seconds
            check_interval: How often to check the condition (seconds)
            action_name: Name of action for logging

        Returns:
            True if condition was met, False if timeout reached

        Example:
            >>> # Wait for login window to appear
            >>> success = timing.wait_for_condition(
            ...     lambda: detector.detect_login_window()['found'],
            ...     timeout=10,
            ...     action_name="login_window_detection"
            ... )
            >>> if success:
            ...     print("Login window appeared!")
        """
        logging.debug(
            "Waiting for condition '%s' (timeout: %.1fs, interval: %.2fs)",
            action_name,
            timeout,
            check_interval
        )

        start_time = time.time()
        checks = 0

        while time.time() - start_time < timeout:
            checks += 1

            try:
                if condition_func():
                    elapsed = time.time() - start_time
                    logging.debug(
                        "✓ Condition '%s' met after %.2fs (%d checks)",
                        action_name,
                        elapsed,
                        checks
                    )
                    return True
            except Exception as e:
                logging.debug(
                    "Condition check error for '%s': %s",
                    action_name,
                    e
                )

            time.sleep(check_interval)

        elapsed = time.time() - start_time
        logging.warning(
            "✗ Condition '%s' not met after %.2fs timeout (%d checks)",
            action_name,
            elapsed,
            checks
        )
        return False

    def exponential_backoff(
        self,
        attempt: int,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        jitter: bool = True
    ) -> float:
        """
        Calculate exponential backoff delay for retry attempts.

        Args:
            attempt: Current attempt number (0-indexed)
            base_delay: Base delay in seconds
            max_delay: Maximum delay cap
            jitter: Add random jitter to prevent thundering herd

        Returns:
            Delay time in seconds

        Example:
            >>> for attempt in range(5):
            ...     delay = timing.exponential_backoff(attempt)
            ...     print(f"Attempt {attempt}: wait {delay:.2f}s")
            ...     time.sleep(delay)
        """
        import random

        # Calculate exponential delay: base * 2^attempt
        delay = min(base_delay * (2 ** attempt), max_delay)

        # Add jitter (±25% randomness)
        if jitter:
            jitter_amount = delay * 0.25
            delay += random.uniform(-jitter_amount, jitter_amount)

        # Apply system multiplier
        delay *= self.system_multiplier

        # Ensure minimum delay
        delay = max(0.1, delay)

        logging.debug(
            "Exponential backoff: attempt=%d, base=%.2fs -> %.2fs",
            attempt,
            base_delay,
            delay
        )

        return delay

    def retry_with_backoff(
        self,
        action_func: Callable[[], bool],
        max_retries: int = 3,
        base_delay: float = 1.0,
        action_name: str = "action"
    ) -> bool:
        """
        Retry an action with exponential backoff.

        Args:
            action_func: Function to execute (should return True on success)
            max_retries: Maximum number of retry attempts
            base_delay: Base delay between retries
            action_name: Action name for logging

        Returns:
            True if action succeeded, False if all retries failed

        Example:
            >>> def try_login():
            ...     return perform_login()
            >>>
            >>> success = timing.retry_with_backoff(
            ...     try_login,
            ...     max_retries=3,
            ...     action_name="login_attempt"
            ... )
        """
        for attempt in range(max_retries):
            try:
                logging.debug(
                    "Attempt %d/%d for '%s'",
                    attempt + 1,
                    max_retries,
                    action_name
                )

                if action_func():
                    if attempt > 0:
                        logging.info(
                            "✓ Action '%s' succeeded on attempt %d/%d",
                            action_name,
                            attempt + 1,
                            max_retries
                        )
                    return True

            except Exception as e:
                logging.warning(
                    "Action '%s' attempt %d failed: %s",
                    action_name,
                    attempt + 1,
                    e
                )

            # Wait before retry (except on last attempt)
            if attempt < max_retries - 1:
                delay = self.exponential_backoff(attempt, base_delay)
                logging.debug("Waiting %.2fs before retry...", delay)
                time.sleep(delay)

        logging.error(
            "✗ Action '%s' failed after %d attempts",
            action_name,
            max_retries
        )
        return False

    def _measure_system_performance(self) -> SystemMetrics:
        """
        Measure system performance metrics.

        Returns:
            SystemMetrics with CPU score and memory info
        """
        cpu_score = 0.7  # Default to normal
        memory_gb = 4.0  # Default

        try:
            # Try to get CPU info
            platform_sys = platform.system()

            # Simple CPU estimation based on processor count
            try:
                import os
                cpu_count = os.cpu_count() or 2
                # More CPUs generally means faster (rough heuristic)
                cpu_score = min(1.0, 0.3 + (cpu_count / 8.0) * 0.7)
            except Exception:
                pass

            # Try to get memory info
            try:
                import psutil
                mem = psutil.virtual_memory()
                memory_gb = mem.available / (1024 ** 3)  # Convert to GB

                # If we have psutil, get better CPU estimate
                cpu_percent = psutil.cpu_percent(interval=0.1)
                # Lower CPU usage = more available = faster
                cpu_score = min(1.0, 1.0 - (cpu_percent / 100.0) * 0.3)

            except ImportError:
                logging.debug("psutil not available, using default metrics")
            except Exception as e:
                logging.debug("Error measuring system: %s", e)

        except Exception as e:
            logging.debug("System measurement error: %s", e)

        metrics = SystemMetrics(
            cpu_score=cpu_score,
            memory_available=memory_gb,
            platform=platform.system()
        )

        logging.debug(
            "System metrics: CPU=%.2f, Memory=%.1fGB, Platform=%s",
            metrics.cpu_score,
            metrics.memory_available,
            metrics.platform
        )

        return metrics

    def _calculate_system_multiplier(self) -> float:
        """
        Calculate timing multiplier based on system performance.

        Returns:
            Multiplier value (0.7 for fast systems, 1.5 for slow systems)
        """
        if self.system_metrics.is_fast:
            # Fast system: reduce wait times
            return 0.7
        elif self.system_metrics.is_slow:
            # Slow system: increase wait times
            return 1.5
        else:
            # Normal system: standard wait times
            return 1.0

    def get_stats(self) -> Dict[str, Any]:
        """
        Get timing statistics and performance info.

        Returns:
            Dictionary with timing statistics
        """
        stats = {
            'system_multiplier': self.system_multiplier,
            'network_multiplier': self.network_multiplier,
            'system_metrics': {
                'cpu_score': self.system_metrics.cpu_score,
                'memory_gb': self.system_metrics.memory_available,
                'platform': self.system_metrics.platform,
                'is_fast': self.system_metrics.is_fast,
                'is_slow': self.system_metrics.is_slow,
            },
            'timing_history': {
                action.value: {
                    'count': len(times),
                    'avg': sum(times) / len(times) if times else 0,
                    'min': min(times) if times else 0,
                    'max': max(times) if times else 0,
                }
                for action, times in self.timing_history.items()
            }
        }
        return stats
