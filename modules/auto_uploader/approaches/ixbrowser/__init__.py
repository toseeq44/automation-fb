"""
IX Browser Approach
===================
API-based browser automation with IX Browser Cloud API.

Features:
- Cloud API for profile management
- Selenium-based automation (no image recognition)
- Remote browser control
- Team collaboration support
- Faster and more reliable than desktop approach

Components:
- api_client.py: IX Cloud API integration
- auth_manager.py: Credential management
- selenium_connector.py: Connect Selenium to browser
- selenium_login.py: Selenium-based login/logout
- workflow.py: Main workflow implementation

Usage:
    >>> from .workflow import IXBrowserApproach
    >>> from ..base_approach import ApproachConfig
    >>>
    >>> config = ApproachConfig(
    ...     mode='ixbrowser',
    ...     credentials={
    ...         'api_key': 'your-api-key',  # Optional for Cloud API
    ...         'email': 'user@example.com',
    ...         'password': 'xxx',
    ...         'profile_name': 'MyProfile1'
    ...     },
    ...     paths={'creators_root': Path('/path/to/creators')},
    ...     browser_type='ix'
    ... )
    >>> approach = IXBrowserApproach(config)
    >>> result = approach.execute_workflow(work_item)
    >>> print(result.success)
"""

from .workflow import IXBrowserApproach

__all__ = ['IXBrowserApproach']
