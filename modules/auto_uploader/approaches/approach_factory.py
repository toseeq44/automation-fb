"""
Approach Factory
================
Factory pattern to create the correct approach implementation based on mode.

This allows the system to dynamically select the right approach (free_automation,
ixbrowser, gologin, etc.) without hard-coding dependencies.
"""
import logging
from typing import Dict, Optional, Type

from .base_approach import BaseApproach, ApproachConfig


class ApproachFactory:
    """
    Factory to create approach instances

    Usage:
        >>> from .free_automation.workflow import FreeAutomationApproach
        >>> ApproachFactory.register_approach('free_automation', FreeAutomationApproach)
        >>>
        >>> config = ApproachConfig(mode='free_automation', ...)
        >>> approach = ApproachFactory.create(config)
        >>> result = approach.execute_workflow(work_item)
    """

    # Registry of available approaches
    _registered_approaches: Dict[str, Type[BaseApproach]] = {}

    @classmethod
    def register_approach(cls, mode: str, approach_class: Type[BaseApproach]) -> None:
        """
        Register an approach implementation

        Args:
            mode: Approach mode identifier (e.g., 'free_automation', 'ixbrowser')
            approach_class: Class that inherits from BaseApproach

        Example:
            >>> ApproachFactory.register_approach('free_automation', FreeAutomationApproach)
        """
        mode_key = mode.lower().strip()

        if mode_key in cls._registered_approaches:
            logging.warning(
                f"Overwriting existing approach registration: {mode_key} "
                f"(was {cls._registered_approaches[mode_key].__name__}, "
                f"now {approach_class.__name__})"
            )

        cls._registered_approaches[mode_key] = approach_class
        logging.info(f"✓ Registered approach: '{mode_key}' → {approach_class.__name__}")

    @classmethod
    def unregister_approach(cls, mode: str) -> bool:
        """
        Unregister an approach

        Args:
            mode: Approach mode to unregister

        Returns:
            True if unregistered, False if not found
        """
        mode_key = mode.lower().strip()

        if mode_key in cls._registered_approaches:
            del cls._registered_approaches[mode_key]
            logging.info(f"Unregistered approach: {mode_key}")
            return True

        return False

    @classmethod
    def get_registered_approaches(cls) -> Dict[str, Type[BaseApproach]]:
        """
        Get all registered approaches

        Returns:
            Dictionary mapping mode → approach class
        """
        return cls._registered_approaches.copy()

    @classmethod
    def is_registered(cls, mode: str) -> bool:
        """
        Check if an approach is registered

        Args:
            mode: Approach mode to check

        Returns:
            True if registered
        """
        mode_key = mode.lower().strip()
        return mode_key in cls._registered_approaches

    @classmethod
    def create(cls, config: ApproachConfig) -> Optional[BaseApproach]:
        """
        Create an approach instance based on config

        Args:
            config: Approach configuration (must include 'mode')

        Returns:
            Approach instance or None if mode not registered

        Example:
            >>> config = ApproachConfig(
            ...     mode='free_automation',
            ...     credentials={'email': 'user@example.com'},
            ...     paths={'creators_root': Path('/path')},
            ...     browser_type='chrome'
            ... )
            >>> approach = ApproachFactory.create(config)
            >>> if approach:
            ...     result = approach.execute_workflow(work_item)
        """
        mode_key = config.mode.lower().strip()

        if mode_key not in cls._registered_approaches:
            logging.error(f"❌ Unknown approach mode: '{mode_key}'")
            logging.info(f"Available modes: {list(cls._registered_approaches.keys())}")
            logging.info("")
            logging.info("HOW TO FIX:")
            logging.info("1. Make sure the approach is registered in __init__.py")
            logging.info("2. Check that the approach module imports correctly")
            logging.info("3. Verify the mode name matches exactly")
            return None

        approach_class = cls._registered_approaches[mode_key]

        logging.info(f"Creating approach: '{mode_key}' ({approach_class.__name__})")

        try:
            instance = approach_class(config)
            logging.info(f"✓ Approach created successfully: {instance}")
            return instance

        except Exception as e:
            logging.error(
                f"❌ Failed to create approach '{mode_key}': {e}",
                exc_info=True
            )
            return None

    @classmethod
    def reset(cls) -> None:
        """
        Reset factory (clear all registrations)

        Useful for testing.
        """
        cls._registered_approaches.clear()
        logging.debug("ApproachFactory reset (all registrations cleared)")


def auto_register_approaches() -> None:
    """
    Auto-register all available approaches

    This function is called when the module is imported.
    It attempts to import and register each approach.
    If an approach is not available, it logs a warning and continues.
    """
    logging.info("Auto-registering approaches...")

    # Register free_automation approach
    try:
        from .free_automation.workflow import FreeAutomationApproach
        ApproachFactory.register_approach('free_automation', FreeAutomationApproach)
    except ImportError as e:
        logging.warning(f"FreeAutomationApproach not available: {e}")

    # Register ixbrowser approach
    try:
        from .ixbrowser.workflow import IXBrowserApproach
        ApproachFactory.register_approach('ix', IXBrowserApproach)
        ApproachFactory.register_approach('ixbrowser', IXBrowserApproach)
    except ImportError as e:
        logging.warning(f"IXBrowserApproach not available: {e}")

    # Register nstbrowser approach
    try:
        from .nstbrowser.workflow import NSTBrowserApproach
        ApproachFactory.register_approach('nst', NSTBrowserApproach)
        ApproachFactory.register_approach('nstbrowser', NSTBrowserApproach)
    except ImportError as e:
        logging.warning(f"NSTBrowserApproach not available: {e}")

    # Future approaches can be added here
    # try:
    #     from .gologin.workflow import GoLoginApproach
    #     ApproachFactory.register_approach('gologin', GoLoginApproach)
    # except ImportError as e:
    #     logging.warning(f"GoLoginApproach not available: {e}")

    registered = ApproachFactory.get_registered_approaches()
    logging.info(f"✓ Auto-registration complete: {len(registered)} approach(es) registered")

    if not registered:
        logging.warning("⚠️  No approaches registered! Check imports.")


# Auto-register on module import
auto_register_approaches()
