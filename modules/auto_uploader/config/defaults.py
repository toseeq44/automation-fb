"""Default configuration values for the modular auto uploader.

NOTE: Uses user's Desktop as default for paths (works with PyInstaller EXE)
Paths must be configured by user through Approaches dialog.
"""

from pathlib import Path


def _get_default_paths():
    """
    Get default paths using user's Desktop.
    These are just defaults - user should configure their own paths.
    """
    # Try to find user's Desktop
    desktop = Path.home() / "Desktop"
    if not desktop.exists():
        # Try OneDrive Desktop
        desktop = Path.home() / "OneDrive" / "Desktop"
    if not desktop.exists():
        desktop = Path.home()

    # Persistent data directory
    data_dir = Path.home() / ".onesoul" / "auto_uploader"

    return {
        # Empty by default - user must configure
        "creators_root": "",
        "shortcuts_root": "",
        "history_file": str(data_dir / "data" / "upload_tracking.json"),
        "ix_data_root": str(data_dir / "ix_data"),
    }


DEFAULT_CONFIG = {
    "automation": {
        "mode": "free_automation",
        "setup_completed": False,
        "paths": _get_default_paths(),
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
