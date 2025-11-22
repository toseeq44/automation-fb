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

    # Enable ping checks (can be disabled if firewall blocks ICMP)
    # If disabled, only HTTP checks will be used
    "enable_ping": False,  # Disabled by default to avoid firewall issues

    # Require ping success (if enabled)
    # If False: ping failure won't mark network as down if HTTP works
    # If True: ping failure will mark network as down regardless of HTTP
    "require_ping": False,  # Prioritize HTTP checks over ping
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
# Connected to Secure License System
# ═══════════════════════════════════════════════════════════

def _get_license_info():
    """Get license info from secure license system."""
    try:
        from modules.license.secure_license import get_plan_info
        return get_plan_info()
    except:
        return {'is_valid': False, 'plan': 'basic', 'daily_pages': 200}


def get_user_type():
    """Get current user type from license."""
    info = _get_license_info()
    if info.get('is_valid'):
        return info.get('plan', 'basic')
    return 'basic'


def get_daily_limit():
    """Get daily limit from license (None = unlimited for Pro)."""
    info = _get_license_info()
    if info.get('is_valid'):
        return info.get('daily_pages')  # None for Pro = unlimited
    return 200  # Basic default


# Static config with defaults (use functions for dynamic values)
USER_CONFIG = {
    # User type: "basic" or "pro"
    # Now dynamically loaded from license system!
    "user_type": "basic",  # Use get_user_type() for live value

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


def get_current_user_config():
    """Get user config with live license data."""
    user_type = get_user_type()
    daily_limit = get_daily_limit()

    return {
        "user_type": user_type,
        "daily_limit_basic": 200,
        "daily_limit_pro": None,
        "daily_limit": daily_limit,
        "track_daily_limit": True,
        "reset_hour": 0,
        "is_pro": user_type == 'pro',
        "is_unlimited": daily_limit is None,
    }


# ═══════════════════════════════════════════════════════════
# NOTIFICATION HANDLING CONFIGURATION
# ═══════════════════════════════════════════════════════════

NOTIFICATION_CONFIG = {
    # Enable browser-level notification blocking (Priority 1)
    "block_browser_notifications": True,

    # Enable active notification dismissal during upload (Priority 2)
    "active_dismissal_enabled": True,

    # Check for notifications every N seconds during upload
    "dismissal_check_interval": 10,

    # Enable Windows focus protection (Priority 3)
    "focus_protection_enabled": False,  # Optional - can cause issues on some systems

    # Wait time after publish button to handle Facebook processing notification
    # Facebook shows "Your bulk upload is processing" notification
    # We navigate to next page to auto-dismiss it
    "post_publish_wait": 3,  # seconds

    # XPath patterns for common Facebook notifications/popups to dismiss
    "dismiss_patterns": [
        # Facebook notification "X" button
        "//div[@role='dialog']//div[@aria-label='Close']",
        "//div[@role='dialog']//div[@aria-label='Dismiss']",

        # "Not Now" buttons for popups
        "//div[@role='dialog']//div[text()='Not Now']",
        "//div[@role='dialog']//button[text()='Not Now']",
        "//button[contains(text(), 'Not Now')]",

        # Generic close buttons
        "//button[@aria-label='Close']",
        "//div[@aria-label='Close notification']",

        # Facebook cookie/consent banners
        "//button[contains(text(), 'Decline')]",
        "//button[contains(text(), 'Only essential')]",
        "//button[contains(text(), 'Only Essential Cookies')]",

        # "Allow notifications" popup
        "//button[contains(text(), 'Block')]",
        "//button[contains(text(), 'Don')]",  # "Don't Allow"

        # Generic overlays
        "//div[@role='dialog']//button[@type='button'][1]",  # First button in dialog
    ],
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
        section: Config section name (network, state, upload, folder, user, notification, resume, logging)
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
        "notification": NOTIFICATION_CONFIG,
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
        "notification": NOTIFICATION_CONFIG,
        "resume": RESUME_CONFIG,
        "logging": LOGGING_CONFIG,
    }

    if section.lower() in config_map:
        config_map[section.lower()][key] = value
