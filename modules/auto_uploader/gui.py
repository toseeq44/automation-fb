"""
GUI Module - Backward Compatibility Wrapper
============================================
This file provides backward compatibility for code that imports:
    from modules.auto_uploader.gui import AutoUploaderPage

It redirects to the legacy GUI implementation.
"""

# Import from legacy folder for backward compatibility
from ._legacy.gui import AutoUploaderPage

__all__ = ['AutoUploaderPage']
