"""
Facebook Auto Uploader Module
Automates video uploads to Facebook pages using anti-detect browsers
"""

from .core import FacebookAutoUploader
from .gui import AutoUploaderPage

__all__ = ['FacebookAutoUploader', 'AutoUploaderPage']
__version__ = '1.0.0'
