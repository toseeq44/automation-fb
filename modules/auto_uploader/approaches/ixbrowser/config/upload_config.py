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

    # ═══════════════════════════════════════════════════════════
    # VIDEO HANDLING AFTER SUCCESSFUL UPLOAD
    # ═══════════════════════════════════════════════════════════

    # What to do with video after successful upload?
    # Options: "move" or "delete"
    # - "move": Move video to "uploaded videos" subfolder (keeps backup)
    # - "delete": Permanently delete video (saves disk space)
    "video_after_upload": "move",  # Default: move to uploaded folder

    # Confirm before deleting (safety check)
    # If True and video_after_upload="delete", will log warning before deletion
    "confirm_delete": True,
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
# PUBLISH BUTTON & SUCCESS DETECTION CONFIGURATION
# ═══════════════════════════════════════════════════════════

PUBLISH_CONFIG = {
    # Enable publish button click (production mode)
    "click_publish_button": True,

    # Click method: "selenium" or "pyautogui" or "javascript"
    # - "selenium": Standard Selenium click (most reliable)
    # - "javascript": Execute JavaScript click (bypasses visibility issues)
    # - "pyautogui": Physical mouse click (for stubborn elements)
    "click_method": "pyautogui",  # Default: Physical left mouse click

    # Retry publish click if it fails
    "publish_click_retries": 3,

    # Wait after clicking publish button (seconds)
    # Give Facebook time to process the click
    "post_click_wait": 1,  # 1 second wait for Facebook response

    # ═══════════════════════════════════════════════════════════
    # SUCCESS MESSAGE DETECTION
    # ═══════════════════════════════════════════════════════════

    # Enable success message detection
    "detect_success_message": True,

    # Maximum time to wait for success message (seconds)
    "success_wait_timeout": 30,

    # Poll interval when checking for success (seconds)
    "success_poll_interval": 1,

    # XPath patterns for Facebook success messages/dialogs
    "success_patterns": [
        # Main success messages
        "//div[@role='dialog' and contains(., 'published')]",
        "//div[@role='dialog' and contains(., 'successfully')]",
        "//div[contains(text(), 'Your video has been published')]",
        "//div[contains(text(), 'Post published')]",
        "//div[contains(text(), 'successfully published')]",

        # Processing notifications (also considered success)
        "//div[contains(text(), 'bulk upload is processing')]",
        "//div[contains(text(), 'Your upload is processing')]",
        "//span[contains(text(), 'processing')]",

        # Success icons/indicators
        "//div[@role='dialog']//svg[contains(@aria-label, 'success')]",
        "//div[@role='dialog']//i[contains(@class, 'success')]",

        # Generic dialog after publish
        "//div[@role='alertdialog']",
        "//div[@role='dialog' and @aria-label]",
    ],

    # After detecting success, wait this long before dismissing
    "success_message_display_time": 2,

    # Automatically dismiss success message
    "auto_dismiss_success": True,

    # ═══════════════════════════════════════════════════════════
    # ENHANCED POPUP DETECTION (Windows notifications)
    # ═══════════════════════════════════════════════════════════

    # Detect Windows-level notifications that block button clicks
    "detect_window_popups": True,

    # Patterns for notifications that appear over publish button
    "blocking_popup_patterns": [
        # Windows notification overlay
        "//div[contains(@class, 'notification')]",
        "//div[contains(@class, 'toast')]",
        "//div[contains(@class, 'snackbar')]",

        # Facebook notification bar
        "//div[@role='complementary' and contains(@class, 'notification')]",

        # Popup that blocks interaction
        "//div[@role='presentation']",

        # Generic overlays
        "//div[contains(@style, 'z-index') and contains(@style, 'fixed')]",
    ],

    # Try to click through notifications if they block button
    "click_through_notifications": True,

    # Max attempts to clear blocking popups
    "popup_clear_retries": 3,
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
        section: Config section name (network, state, upload, folder, user, notification, publish, resume, logging)
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
        "publish": PUBLISH_CONFIG,
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
        "publish": PUBLISH_CONFIG,
        "resume": RESUME_CONFIG,
        "logging": LOGGING_CONFIG,
    }

    if section.lower() in config_map:
        config_map[section.lower()][key] = value
