"""
Video Upload Workflow Package

Complete bulletproof workflow for uploading videos to Facebook pages.

Phases:
- Phase 2: Extract page names from folder structure
- Phase 1: Open fresh tab and navigate bookmarks using helper images
- Phase 4: Find and click "Add Videos" button
- Phase 5: Set video title and description after upload completes
"""

from .page_name_extractor import PageNameExtractor
from .fresh_tab_manager import FreshTabManager
from .bookmark_navigator import BookmarkNavigator
from .add_videos_finder import AddVideosFinder
from .title_setter import VideoTitleSetter
from .workflow_orchestrator import UploadWorkflowOrchestrator

__all__ = [
    'PageNameExtractor',
    'FreshTabManager',
    'BookmarkNavigator',
    'AddVideosFinder',
    'VideoTitleSetter',
    'UploadWorkflowOrchestrator',
]

__version__ = '1.1.0'
