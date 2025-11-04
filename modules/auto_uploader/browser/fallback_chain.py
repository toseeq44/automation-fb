"""
Fallback Chain System
====================

Robust action execution with multiple fallback strategies. This module provides
a flexible way to execute actions with automatic fallback to alternative methods
if the primary method fails.

Features:
- Execute actions with multiple fallback strategies
- Automatic retry with different approaches
- Detailed logging of which strategy succeeded
- Strategy prioritization and ordering
- Context-aware fallback selection
"""

import logging
import time
from typing import Callable, List, Optional, Any, Dict, Tuple
from dataclasses import dataclass
from enum import Enum


class StrategyPriority(Enum):
    """Priority levels for fallback strategies."""
    PRIMARY = 1      # Try first (most reliable)
    SECONDARY = 2    # Try if primary fails
    TERTIARY = 3     # Try if secondary fails
    LAST_RESORT = 4  # Final attempt


@dataclass
class Strategy:
    """
    Represents a single execution strategy.

    Attributes:
        name: Human-readable strategy name
        action: Callable to execute
        priority: Strategy priority level
        timeout: Maximum time to attempt this strategy (seconds)
        prerequisites: Optional function to check if strategy can be used
    """
    name: str
    action: Callable[[], Any]
    priority: StrategyPriority = StrategyPriority.SECONDARY
    timeout: float = 10.0
    prerequisites: Optional[Callable[[], bool]] = None

    def can_execute(self) -> bool:
        """Check if this strategy's prerequisites are met."""
        if self.prerequisites is None:
            return True
        try:
            return self.prerequisites()
        except Exception as e:
            logging.debug("Prerequisites check failed for '%s': %s", self.name, e)
            return False


@dataclass
class ExecutionResult:
    """Result of strategy execution."""
    success: bool
    strategy_used: Optional[str]
    attempts: int
    total_time: float
    result_data: Any = None
    error: Optional[str] = None


class FallbackChain:
    """
    Execute actions with automatic fallback to alternative strategies.

    This class manages multiple approaches to accomplish a task, automatically
    trying fallback strategies if the primary approach fails. It's essential
    for building robust automation that handles edge cases and varying conditions.

    Example:
        >>> chain = FallbackChain("Click Login Button")
        >>>
        >>> # Add strategies in order of preference
        >>> chain.add_strategy(
        ...     name="Image Detection",
        ...     action=lambda: click_by_image(),
        ...     priority=StrategyPriority.PRIMARY
        ... )
        >>> chain.add_strategy(
        ...     name="OCR Text Detection",
        ...     action=lambda: click_by_ocr(),
        ...     priority=StrategyPriority.SECONDARY
        ... )
        >>> chain.add_strategy(
        ...     name="Keyboard Enter",
        ...     action=lambda: press_enter(),
        ...     priority=StrategyPriority.LAST_RESORT
        ... )
        >>>
        >>> # Execute with fallbacks
        >>> result = chain.execute()
        >>> if result.success:
        ...     print(f"Success using: {result.strategy_used}")
    """

    def __init__(self, action_name: str, enable_logging: bool = True):
        """
        Initialize fallback chain.

        Args:
            action_name: Name of the action being performed
            enable_logging: Enable detailed execution logging
        """
        self.action_name = action_name
        self.strategies: List[Strategy] = []
        self.enable_logging = enable_logging
        self.execution_history: List[ExecutionResult] = []

        logging.debug("FallbackChain initialized for action: %s", action_name)

    def add_strategy(
        self,
        name: str,
        action: Callable[[], Any],
        priority: StrategyPriority = StrategyPriority.SECONDARY,
        timeout: float = 10.0,
        prerequisites: Optional[Callable[[], bool]] = None
    ) -> 'FallbackChain':
        """
        Add a strategy to the fallback chain.

        Args:
            name: Strategy name for logging
            action: Function to execute (should return truthy value on success)
            priority: Strategy priority (lower number = higher priority)
            timeout: Maximum execution time for this strategy
            prerequisites: Optional function to check if strategy is viable

        Returns:
            Self for method chaining

        Example:
            >>> chain.add_strategy(
            ...     "Primary Method",
            ...     action=lambda: do_primary(),
            ...     priority=StrategyPriority.PRIMARY
            ... ).add_strategy(
            ...     "Backup Method",
            ...     action=lambda: do_backup(),
            ...     priority=StrategyPriority.SECONDARY
            ... )
        """
        strategy = Strategy(
            name=name,
            action=action,
            priority=priority,
            timeout=timeout,
            prerequisites=prerequisites
        )
        self.strategies.append(strategy)

        logging.debug(
            "Strategy added to '%s': %s (priority: %s)",
            self.action_name,
            name,
            priority.name
        )

        return self  # Enable method chaining

    def execute(
        self,
        raise_on_failure: bool = False,
        delay_between_attempts: float = 0.5
    ) -> ExecutionResult:
        """
        Execute the action using strategies in priority order.

        Tries each strategy in order of priority until one succeeds or all fail.
        Automatically skips strategies whose prerequisites are not met.

        Args:
            raise_on_failure: Raise exception if all strategies fail
            delay_between_attempts: Delay between strategy attempts (seconds)

        Returns:
            ExecutionResult with details of execution

        Raises:
            RuntimeError: If raise_on_failure=True and all strategies fail

        Example:
            >>> result = chain.execute()
            >>> if result.success:
            ...     print(f"Succeeded with {result.strategy_used}")
            ... else:
            ...     print(f"All strategies failed after {result.attempts} attempts")
        """
        if not self.strategies:
            error_msg = f"No strategies defined for action '{self.action_name}'"
            logging.error(error_msg)
            if raise_on_failure:
                raise RuntimeError(error_msg)
            return ExecutionResult(
                success=False,
                strategy_used=None,
                attempts=0,
                total_time=0.0,
                error=error_msg
            )

        # Sort strategies by priority
        sorted_strategies = sorted(self.strategies, key=lambda s: s.priority.value)

        if self.enable_logging:
            logging.info("")
            logging.info("┌" + "─" * 58 + "┐")
            logging.info("│ FALLBACK CHAIN: %-42s │", self.action_name[:42])
            logging.info("└" + "─" * 58 + "┘")
            logging.info("Available strategies: %d", len(sorted_strategies))
            for idx, strategy in enumerate(sorted_strategies, 1):
                logging.info(
                    "  %d. %s [%s]",
                    idx,
                    strategy.name,
                    strategy.priority.name
                )

        start_time = time.time()
        attempts = 0

        for strategy in sorted_strategies:
            attempts += 1

            # Check prerequisites
            if not strategy.can_execute():
                logging.debug(
                    "⊘ Strategy '%s' prerequisites not met, skipping",
                    strategy.name
                )
                continue

            if self.enable_logging:
                logging.info("")
                logging.info(
                    "→ Attempting strategy %d/%d: %s",
                    attempts,
                    len(sorted_strategies),
                    strategy.name
                )

            try:
                # Execute strategy with timeout
                strategy_start = time.time()
                result = self._execute_with_timeout(strategy)
                strategy_time = time.time() - strategy_start

                # Check if successful (truthy result)
                if result:
                    total_time = time.time() - start_time

                    if self.enable_logging:
                        logging.info(
                            "✓ SUCCESS: Strategy '%s' succeeded in %.2fs",
                            strategy.name,
                            strategy_time
                        )
                        logging.info("Total execution time: %.2fs", total_time)
                        logging.info("")

                    exec_result = ExecutionResult(
                        success=True,
                        strategy_used=strategy.name,
                        attempts=attempts,
                        total_time=total_time,
                        result_data=result
                    )
                    self.execution_history.append(exec_result)
                    return exec_result

                else:
                    logging.debug(
                        "✗ Strategy '%s' returned falsy result (%.2fs)",
                        strategy.name,
                        strategy_time
                    )

            except TimeoutError:
                logging.warning(
                    "⏱ Strategy '%s' timed out after %.1fs",
                    strategy.name,
                    strategy.timeout
                )
            except Exception as e:
                logging.warning(
                    "✗ Strategy '%s' failed with error: %s",
                    strategy.name,
                    str(e),
                    exc_info=False
                )

            # Delay before next attempt
            if attempts < len(sorted_strategies):
                time.sleep(delay_between_attempts)

        # All strategies failed
        total_time = time.time() - start_time
        error_msg = f"All {attempts} strategies failed for '{self.action_name}'"

        if self.enable_logging:
            logging.error("")
            logging.error("✗ FAILURE: %s", error_msg)
            logging.error("Total time: %.2fs", total_time)
            logging.error("")

        exec_result = ExecutionResult(
            success=False,
            strategy_used=None,
            attempts=attempts,
            total_time=total_time,
            error=error_msg
        )
        self.execution_history.append(exec_result)

        if raise_on_failure:
            raise RuntimeError(error_msg)

        return exec_result

    def execute_first_success(self, strategies: List[Callable[[], Any]]) -> Tuple[bool, Any]:
        """
        Quick execution of multiple strategies without full setup.

        Convenience method for simple fallback scenarios where you just want
        to try a list of functions in order.

        Args:
            strategies: List of callable functions to try

        Returns:
            Tuple of (success: bool, result: Any)

        Example:
            >>> success, result = chain.execute_first_success([
            ...     lambda: method1(),
            ...     lambda: method2(),
            ...     lambda: method3(),
            ... ])
        """
        for idx, strategy_func in enumerate(strategies, 1):
            try:
                result = strategy_func()
                if result:
                    logging.debug(
                        "Quick strategy %d/%d succeeded",
                        idx,
                        len(strategies)
                    )
                    return True, result
            except Exception as e:
                logging.debug(
                    "Quick strategy %d/%d failed: %s",
                    idx,
                    len(strategies),
                    e
                )
                continue

        return False, None

    def _execute_with_timeout(self, strategy: Strategy) -> Any:
        """
        Execute a strategy with timeout protection.

        Args:
            strategy: Strategy to execute

        Returns:
            Strategy result

        Raises:
            TimeoutError: If strategy exceeds timeout
        """
        import signal

        def timeout_handler(signum, frame):
            raise TimeoutError(f"Strategy '{strategy.name}' exceeded {strategy.timeout}s timeout")

        # Set timeout (Unix-like systems only)
        try:
            if hasattr(signal, 'SIGALRM'):
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(int(strategy.timeout))

            result = strategy.action()

            # Cancel timeout
            if hasattr(signal, 'SIGALRM'):
                signal.alarm(0)

            return result

        except Exception:
            # Cancel timeout on error
            if hasattr(signal, 'SIGALRM'):
                signal.alarm(0)
            raise

    def clear_strategies(self) -> None:
        """Clear all registered strategies."""
        self.strategies.clear()
        logging.debug("All strategies cleared for '%s'", self.action_name)

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get execution statistics.

        Returns:
            Dictionary with execution history and success rates
        """
        if not self.execution_history:
            return {
                'total_executions': 0,
                'success_rate': 0.0,
                'avg_attempts': 0.0,
                'avg_time': 0.0
            }

        successful = [e for e in self.execution_history if e.success]

        return {
            'total_executions': len(self.execution_history),
            'successful': len(successful),
            'failed': len(self.execution_history) - len(successful),
            'success_rate': len(successful) / len(self.execution_history) * 100,
            'avg_attempts': sum(e.attempts for e in self.execution_history) / len(self.execution_history),
            'avg_time': sum(e.total_time for e in self.execution_history) / len(self.execution_history),
            'most_used_strategy': max(
                (e.strategy_used for e in successful if e.strategy_used),
                key=lambda s: sum(1 for e in successful if e.strategy_used == s),
                default=None
            ) if successful else None
        }


# Convenience functions for common use cases

def try_multiple(
    action_name: str,
    strategies: List[Tuple[str, Callable]],
    **kwargs
) -> ExecutionResult:
    """
    Convenience function to quickly try multiple strategies.

    Args:
        action_name: Name of action being performed
        strategies: List of (name, callable) tuples
        **kwargs: Additional arguments for FallbackChain.execute()

    Returns:
        ExecutionResult

    Example:
        >>> result = try_multiple(
        ...     "Find Login Button",
        ...     [
        ...         ("Image Match", lambda: find_by_image()),
        ...         ("OCR Search", lambda: find_by_ocr()),
        ...         ("Fixed Position", lambda: find_by_position()),
        ...     ]
        ... )
    """
    chain = FallbackChain(action_name)

    for idx, (name, action) in enumerate(strategies):
        # Assign priority based on order
        if idx == 0:
            priority = StrategyPriority.PRIMARY
        elif idx == len(strategies) - 1:
            priority = StrategyPriority.LAST_RESORT
        else:
            priority = StrategyPriority.SECONDARY

        chain.add_strategy(name, action, priority=priority)

    return chain.execute(**kwargs)
