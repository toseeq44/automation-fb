"""
Logger Helper Utilities for ixBrowser Approach

Enhanced logging utilities:
- Consistent logger creation
- Log separators
- Progress logging
- State change logging

Usage:
    logger = get_logger(__name__)
    log_separator(logger, "Upload Started")
"""

import logging


def get_logger(name: str) -> logging.Logger:
    """
    Get logger instance with consistent configuration.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


def log_separator(logger: logging.Logger, title: str = "", level: int = logging.INFO):
    """
    Log a visual separator with optional title.

    Args:
        logger: Logger instance
        title: Optional title text
        level: Log level (default: INFO)
    """
    separator = "═══════════════════════════════════════════"

    if title:
        logger.log(level, "[Upload] %s", separator)
        logger.log(level, "[Upload] %s", title)
        logger.log(level, "[Upload] %s", separator)
    else:
        logger.log(level, "[Upload] %s", separator)


# TODO: Implement additional helper functions
# - log_progress()
# - log_state_change()
# - log_error_with_context()
