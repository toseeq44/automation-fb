"""
Free Automation Approach
========================
Desktop-based browser automation with image recognition.

Features:
- Desktop .lnk shortcut-based browser launch
- Image recognition for UI detection
- Mouse and keyboard automation
- No API required (completely free)

Usage:
    >>> from .workflow import FreeAutomationApproach
    >>> from ..base_approach import ApproachConfig
    >>>
    >>> config = ApproachConfig(
    ...     mode='free_automation',
    ...     credentials={'email': 'user@example.com', 'password': 'xxx'},
    ...     paths={'creators_root': Path('/path/to/creators')},
    ...     browser_type='chrome'
    ... )
    >>> approach = FreeAutomationApproach(config)
    >>> result = approach.execute_workflow(work_item)
"""

from .workflow import FreeAutomationApproach

__all__ = ['FreeAutomationApproach']
