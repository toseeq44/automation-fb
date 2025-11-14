"""
Upload Configuration for ixBrowser Approach

All configuration settings for Phase 2 - Robustness:
- Network monitoring settings
- State management settings
- Upload retry settings
- Folder queue settings
"""

import os
from pathlib import Path

# Get base paths
_CURRENT_DIR = Path(__file__).parent.parent
_DATA_DIR = _CURRENT_DIR / "data"


# ═══════════════════════════════════════════════════════════
# NETWORK MONITORING CONFIGURATION
# ═══════════════════════════════════════════════════════════

NETWORK_CONFIG = {
    # How often to check network health (seconds)
    "check_interval": 10,

    # Maximum time to wait for network reconnection (seconds)
    # After this timeout, upload will be retried from beginning
    "reconnect_wait": 300,  # 5 minutes

    # Timeout for ping/HTTP requests (seconds)
    "ping_timeout": 5,

    # URLs to check for network health
    "health_check_urls": [
        "https://www.google.com",
        "https://www.facebook.com",
    ],

    # Ping target for basic connectivity check
    "ping_target": "8.8.8.8",  # Google DNS
}


# ═══════════════════════════════════════════════════════════
# STATE MANAGEMENT CONFIGURATION
# ═══════════════════════════════════════════════════════════

STATE_CONFIG = {
    # How often to save upload progress during upload (seconds)
    "save_interval": 30,

    # State file paths
    "state_file": str(_DATA_DIR / "bot_state.json"),
    "folder_file": str(_DATA_DIR / "folder_progress.json"),
    "upload_file": str(_DATA_DIR / "uploaded_videos.json"),

    # Enable automatic backups
    "backup_enabled": True,

    # Number of backup copies to keep
    "backup_count": 3,

    # State file indentation (pretty print)
    "indent": 2,
}


# ═══════════════════════════════════════════════════════════
# UPLOAD & RETRY CONFIGURATION
# ═══════════════════════════════════════════════════════════

UPLOAD_CONFIG = {
    # Maximum retry attempts per video
    "max_retries": 3,

    # Base wait time between retries (seconds)
    "retry_wait_base": 30,  # First retry: 30s

    # Multiplier for subsequent retries
    # Retry 1: 30s, Retry 2: 60s, Retry 3: 120s
    "retry_wait_multiplier": 2,

    # Delete video after max failures
    "delete_on_failure": True,

    # Upload timeout (seconds) - 10 minutes
    "upload_timeout": 600,

    # Progress stuck timeout (seconds)
    # If progress doesn't change for this long, consider it stuck
    "progress_stuck_timeout": 120,  # 2 minutes
}


# ═══════════════════════════════════════════════════════════
# FOLDER QUEUE CONFIGURATION
# ═══════════════════════════════════════════════════════════

FOLDER_CONFIG = {
    # Enable infinite loop through folders
    "loop_enabled": True,

    # Base path to creator_data folder
    # This should be set via command-line argument or environment variable
    "base_path": os.getenv("CREATOR_DATA_PATH", "/path/to/creator_data"),

    # Subfolder name for uploaded videos
    "uploaded_subfolder": "uploaded videos",

    # Video file extensions to look for
    "video_extensions": [
        "*.mp4", "*.mov", "*.avi", "*.mkv", "*.wmv",
        "*.MP4", "*.MOV", "*.AVI", "*.MKV", "*.WMV",
    ],
}


# ═══════════════════════════════════════════════════════════
# USER TYPE & DAILY LIMIT CONFIGURATION
# ═══════════════════════════════════════════════════════════

USER_CONFIG = {
    # User type: "basic" or "pro"
    # Basic: Limited to daily_limit bookmarks per 24 hours
    # Pro: Unlimited uploads
    "user_type": "basic",  # Default: basic user

    # Daily limit for basic users (number of bookmarks/pages per 24 hours)
    "daily_limit_basic": 200,

    # Daily limit for pro users (set to None or very high number)
    "daily_limit_pro": None,  # None = unlimited

    # Enable daily limit tracking
    "track_daily_limit": True,

    # Reset time (hour of day, 0-23)
    # Set to 0 to reset at midnight
    "reset_hour": 0,
}


# ═══════════════════════════════════════════════════════════
# RESUME & RECOVERY CONFIGURATION
# ═══════════════════════════════════════════════════════════

RESUME_CONFIG = {
    # Maximum age of state to consider for resume (minutes)
    # If state is older than this, start fresh instead of resuming
    "max_state_age": 15,

    # Check for interrupted upload on startup
    "check_interrupted": True,

    # Automatically resume interrupted upload
    "auto_resume": True,
}


# ═══════════════════════════════════════════════════════════
# LOGGING CONFIGURATION
# ═══════════════════════════════════════════════════════════

LOGGING_CONFIG = {
    # Log level for state operations
    "state_log_level": "INFO",

    # Log level for network monitoring
    "network_log_level": "INFO",

    # Log level for folder queue
    "queue_log_level": "INFO",

    # Enable verbose debugging
    "debug_mode": False,
}


# ═══════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════

def get_config(section: str = None):
    """
    Get configuration section or all configs.

    Args:
        section: Config section name (network, state, upload, folder, user, resume, logging)
                 If None, returns all configs

    Returns:
        Dict with configuration
    """
    all_configs = {
        "network": NETWORK_CONFIG,
        "state": STATE_CONFIG,
        "upload": UPLOAD_CONFIG,
        "folder": FOLDER_CONFIG,
        "user": USER_CONFIG,
        "resume": RESUME_CONFIG,
        "logging": LOGGING_CONFIG,
    }

    if section:
        return all_configs.get(section.lower(), {})
    return all_configs


def update_config(section: str, key: str, value):
    """
    Update a configuration value.

    Args:
        section: Config section name
        key: Configuration key
        value: New value
    """
    config_map = {
        "network": NETWORK_CONFIG,
        "state": STATE_CONFIG,
        "upload": UPLOAD_CONFIG,
        "folder": FOLDER_CONFIG,
        "user": USER_CONFIG,
        "resume": RESUME_CONFIG,
        "logging": LOGGING_CONFIG,
    }

    if section.lower() in config_map:
        config_map[section.lower()][key] = value
