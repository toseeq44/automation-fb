"""Default configuration values for the modular auto uploader."""

from pathlib import Path

import sys
import os

if getattr(sys, 'frozen', False):
    # If frozen, usage depends on whether we want to read from internal bundle
    # or external folder.
    # For now, let's point to the external folder next to EXE to allow user customization
    _BASE_PATH = Path(sys.executable).parent / "modules" / "auto_uploader"
else:
    _BASE_PATH = Path(__file__).resolve().parents[1]

DEFAULT_CONFIG = {
    "automation": {
        "mode": "free_automation",
        "setup_completed": False,
        "paths": {
            "creators_root": str((_BASE_PATH / "creators").resolve()),
            "shortcuts_root": str((_BASE_PATH / "creator_shortcuts").resolve()),
            "history_file": str((_BASE_PATH / "data" / "history.json").resolve()),
            "ix_data_root": str((_BASE_PATH / "ix_data").resolve()),
        },
        "credentials": {
            "gologin": {},
            "ix": {},
            "vpn": {},
            "free_automation": {},
        },
    },
    "browsers": {
        "gologin": {
            "exe_path": "",
            "desktop_shortcut": "",
            "debug_port": 9222,
            "startup_wait": 15,
            "profile_startup_wait": 10,
            "enabled": True,
        },
        "ix": {
            "exe_path": "",
            "desktop_shortcut": "",
            "debug_port": 9223,
            "startup_wait": 15,
            "profile_startup_wait": 10,
            "enabled": True,
        },
    },
    "upload_settings": {
        "wait_after_upload": 30,
        "wait_between_videos": 120,
        "retry_attempts": 3,
        "retry_delay": 60,
        "delete_after_upload": True,
        "skip_uploaded": True,
        "upload_timeout": 600,
    },
    "facebook": {
        "upload_url": "https://www.facebook.com/",
        "video_upload_url": "https://www.facebook.com/video/upload",
        "wait_for_login": 20,
        "wait_for_video_processing": 30,
    },
}
