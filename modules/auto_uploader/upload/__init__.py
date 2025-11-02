"""
Upload Module
=============
Handles video upload operations to Facebook.

Submodules:
-----------
- video_uploader: Core upload logic
- metadata_handler: Title, description, tags handling
- file_selector: Video file selection logic
- progress_monitor: Upload progress tracking
- post_processor: Post-upload actions

Example Usage:
--------------
from modules.auto_uploader.upload.video_uploader import VideoUploader
from modules.auto_uploader.upload.metadata_handler import MetadataHandler

uploader = VideoUploader()
metadata = MetadataHandler().load_metadata(video_path, creator)
uploader.upload_single_video(driver, video_path, metadata)
"""

__version__ = "2.0.0"
__all__ = [
    "VideoUploader",
    "MetadataHandler",
    "FileSelector",
    "ProgressMonitor",
    "PostProcessor",
]
