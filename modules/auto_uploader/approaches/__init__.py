"""
Approaches Module
=================
Contains different automation approach implementations.

Available approaches:
- free_automation: Desktop-based browser automation with image recognition
- ixbrowser: API-based browser automation with IX Browser Cloud API
- gologin: GoLogin browser automation (future)
- vpn: VPN-based automation (future)

Usage:
    >>> from .approach_factory import ApproachFactory
    >>> from .base_approach import ApproachConfig
    >>>
    >>> config = ApproachConfig(
    ...     mode='free_automation',
    ...     credentials={'email': 'user@example.com', 'password': 'xxx'},
    ...     paths={'creators_root': Path('/path/to/creators')},
    ...     browser_type='chrome'
    ... )
    >>>
    >>> approach = ApproachFactory.create(config)
    >>> result = approach.execute_workflow(work_item)
"""

from .base_approach import (
    BaseApproach,
    ApproachConfig,
    CreatorData,
    WorkItem,
    WorkflowResult,
)
from .approach_factory import ApproachFactory

__all__ = [
    'BaseApproach',
    'ApproachConfig',
    'CreatorData',
    'WorkItem',
    'WorkflowResult',
    'ApproachFactory',
]
