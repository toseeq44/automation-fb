"""
main.py
Main application to launch OneSoul.
"""
import sys
import os
import threading
import json

# --- PyInstaller Playwright Bundling Fix ---
if getattr(sys, 'frozen', False):
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    os.environ['PLAYWRIGHT_BROWSERS_PATH'] = os.path.join(base_path, 'playwright_browsers')
# -------------------------------------------

# --- Initialize Root Logger FIRST ---
try:
    from modules.config.debug_logger import setup_debug_logger
    setup_debug_logger()
except Exception as e:
    print(f"Failed to setup debug logger at startup: {e}")
# ------------------------------------

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication, QMessageBox

# Choose UI version (set USE_MODERN_UI = True for new OneSoul design)
USE_MODERN_UI = True

if USE_MODERN_UI:
    from gui_modern import VideoToolSuiteGUI
else:
    from gui import VideoToolSuiteGUI

from modules.logging import get_logger
from modules.config import get_config
from modules.license import LicenseManager, sync_all_plans
from modules.security import (
    build_user_safe_license_message,
    run_security_preflight,
    verify_runtime_integrity,
)
from modules.ui import LicenseActivationDialog


import os
import shutil
from pathlib import Path


HEARTBEAT_INTERVAL_SECONDS = 45
TRACKING_POLL_INTERVAL_SECONDS = 15
SECURITY_WATCHDOG_INTERVAL_MS = 15000


def _should_block_frozen_helper_invocation() -> bool:
    """Prevent the frozen GUI EXE from relaunching itself as a fake Python helper."""
    if not getattr(sys, "frozen", False):
        return False

    argv = [str(arg or "").strip().lower() for arg in sys.argv[1:]]
    if len(argv) >= 2 and argv[0] == "-m":
        helper = argv[1]
        if helper in {"demucs", "modules.creator_profiles.demucs_runner"}:
            return True
    return False

def restore_bundled_configs():
    """
    Restore configuration files from the bundled PyInstaller temporary directory
    to the executable's directory if they don't exist.
    This allows the EXE to self-extract its default/bundled configs on a new PC.
    """
    # Only run if frozen (bundled as EXE)
    if not getattr(sys, 'frozen', False):
        return

    # PyInstaller unpacks data to a temporary folder at sys._MEIPASS
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    base_path = Path(base_path)
    
    # Directory where the EXE is running
    exe_dir = Path(sys.executable).parent
    
    # List of files/folders to restore
    files_to_restore = [
        "api_config.json",
        "license_endpoints.json",
        "folder_mappings.json"
    ]
    
    for filename in files_to_restore:
        source = base_path / filename
        target = exe_dir / filename

        if not source.exists():
            continue

        should_copy = not target.exists()
        if filename == "license_endpoints.json" and target.exists():
            try:
                target_payload = json.loads(target.read_text(encoding="utf-8"))
                target_primary = str(target_payload.get("primary_url", "") or "").strip().lower()
                if (not target_primary) or ("trycloudflare.com" in target_primary):
                    should_copy = True
            except Exception:
                should_copy = True

        if should_copy:
            try:
                shutil.copy2(source, target)
                print(f"Restored bundled config: {filename}")
            except Exception as e:
                print(f"Failed to restore {filename}: {e}")
    
    # Also ensure cookies directory exists
    cookies_dir = exe_dir / "cookies"
    if not cookies_dir.exists():
        try:
            cookies_dir.mkdir(exist_ok=True)
            print(f"Created cookies directory at: {cookies_dir}")
        except Exception as e:
            print(f"Failed to create cookies directory: {e}")

    # Restore auto_uploader assets
    # We need to copy modules/auto_uploader/creator_shortcuts etc.
    auto_uploader_src = base_path / "modules" / "auto_uploader"
    auto_uploader_dst = exe_dir / "modules" / "auto_uploader"
    
    # List of subfolders to ensure exist/copy
    uploader_folders = ["creator_shortcuts", "creators", "data", "ix_data"]
    
    if auto_uploader_src.exists():
        for folder in uploader_folders:
            src = auto_uploader_src / folder
            dst = auto_uploader_dst / folder
            
            if src.exists() and not dst.exists():
                try:
                    shutil.copytree(src, dst)
                    print(f"Restored auto_uploader asset: {folder}")
                except Exception as e:
                    print(f"Failed to restore {folder}: {e}")

def main():
    """Launch the OneSoul application"""
    if _should_block_frozen_helper_invocation():
        print("OneSoul helper invocation blocked: bundled EXE cannot run Python modules.")
        sys.exit(2)

    # Attempt to restore configs first
    restore_bundled_configs()

    # Initialize application
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # Modern look across platforms

    # Initialize logger
    logger = get_logger("OneSoul")
    logger.info("=" * 60, "App")
    logger.info("OneSoul - All Solution One Place", "App")
    logger.info("Version 1.0.0", "App")
    logger.info("=" * 60, "App")

    # Initialize config
    config = get_config()
    logger.info(f"Config loaded from: {config.config_path}", "App")

    # Ensure directories exist
    config.ensure_directories_exist()

    security_ok, security_message, security_detail = run_security_preflight(config)
    if not security_ok:
        logger.error(f"Security preflight blocked startup: {security_detail}", "Security")
        QMessageBox.critical(None, "Security Check Failed", security_message)
        sys.exit(0)

    integrity_ok, integrity_message, integrity_detail = verify_runtime_integrity(config)
    if not integrity_ok:
        logger.error(f"Runtime integrity check failed: {integrity_detail}", "Security")
        QMessageBox.critical(None, "Integrity Check Failed", integrity_message)
        sys.exit(0)

    # Initialize license manager
    server_url = config.get('license.server_url', 'http://localhost:5000')
    app_version = config.get('app.version', '1.0.0')
    server_fallback_urls = config.get('license.server_fallback_urls', [])
    bootstrap_urls = config.get('license.bootstrap_urls', [])
    remember_last_good_url = config.get('license.remember_last_good_url', True)
    heartbeat_interval_seconds = int(config.get('license.heartbeat_interval_seconds', HEARTBEAT_INTERVAL_SECONDS) or HEARTBEAT_INTERVAL_SECONDS)
    tracking_poll_interval_seconds = int(config.get('license.task_poll_interval_seconds', TRACKING_POLL_INTERVAL_SECONDS) or TRACKING_POLL_INTERVAL_SECONDS)
    heartbeat_interval_seconds = max(15, heartbeat_interval_seconds)
    tracking_poll_interval_seconds = max(5, tracking_poll_interval_seconds)
    license_manager = LicenseManager(
        server_url=server_url,
        app_version=app_version,
        fallback_urls=server_fallback_urls,
        bootstrap_urls=bootstrap_urls,
        remember_last_good_url=remember_last_good_url,
    )

    license_provider = str(config.get('license.provider', 'firebase') or 'firebase').strip().lower()
    logger.info(f"License provider: {license_provider}", "License")
    logger.info(f"License server preference: {server_url or '(auto)'}", "License")
    logger.info(
        f"License endpoint candidates: {', '.join(license_manager.get_server_url_candidates()) or '(none configured)'}",
        "License",
    )
    logger.info(f"Resolved license endpoint: {license_manager.get_active_server_url() or '(none yet)'}", "License")
    # Production enforcement: always validate license on startup.
    is_valid, message, license_info = license_manager.validate_license()

    if not is_valid:
        logger.warning(f"License validation failed: {message}", "License")

        if license_manager.should_force_shutdown():
            logger.error(f"License startup lock triggered: {license_manager.last_status_code}", "License")
            title = "License Service Unavailable"
            if str(license_manager.last_status_code).strip().lower() == "firebase_config_missing":
                title = "Firebase Configuration Missing"
            safe_message = build_user_safe_license_message(license_manager.last_status_code, message)
            QMessageBox.critical(None, title, f"{safe_message}\n\nOneSoul will now close.")
            sys.exit(0)

        # Show activation dialog for both no license and expired license
        if not license_info:
            logger.info("No license found. Showing activation dialog.", "License")
            dialog_message = "No active license found. Please activate a license to continue."
        else:
            # License exists but invalid (expired or offline too long)
            logger.warning("License invalid or expired", "License")
            dialog_message = f"License Issue: {message}"
            QMessageBox.warning(
                None,
                "License Expired",
                f"{build_user_safe_license_message(license_manager.last_status_code, message)}\n\n"
                "Your license has expired or is invalid.\n"
                "Please activate a valid license to continue."
            )

        # Show activation dialog
        activation_dialog = LicenseActivationDialog(license_manager)
        result = activation_dialog.exec_()

        if result != activation_dialog.Accepted:
            # User cancelled activation
            logger.info("User cancelled license activation. Exiting.", "License")
            QMessageBox.warning(
                None,
                "License Required",
                "OneSoul requires a valid license to run.\n\n"
                "The application will now close."
            )
            sys.exit(0)
        else:
            # License activated successfully, validate again
            is_valid, message, license_info = license_manager.validate_license()
            if not is_valid:
                if license_manager.should_force_shutdown():
                    logger.error(f"Post-activation startup lock triggered: {license_manager.last_status_code}", "License")
                    title = "License Service Unavailable"
                    if str(license_manager.last_status_code).strip().lower() == "firebase_config_missing":
                        title = "Firebase Configuration Missing"
                    safe_message = build_user_safe_license_message(license_manager.last_status_code, message)
                    QMessageBox.critical(None, title, f"{safe_message}\n\nOneSoul will now close.")
                    sys.exit(0)
                logger.error("License activation succeeded but validation failed.", "License")
                QMessageBox.critical(
                    None,
                    "Activation Error",
                    "License activation completed but validation failed.\n"
                    "Please restart the application."
                )
                sys.exit(0)
    else:
        logger.info(f"License validated successfully: {message}", "License")
        days_remaining = license_info.get('days_remaining', 0) if license_info else 0

        # Warn if expiring soon
        if days_remaining <= 7 and days_remaining > 0:
            logger.warning(f"License expiring in {days_remaining} days", "License")
            QMessageBox.warning(
                None,
                "License Expiring Soon",
                f"Your license will expire in {days_remaining} day(s).\n\n"
                "Please renew your subscription to continue using OneSoul."
            )

    
    # Sync user plan across all modules
    logger.info("Syncing user plan across modules...", "App")
    sync_all_plans(license_manager)

    # Best-effort startup heartbeat and background presence tracking.
    hb_ok, hb_msg = license_manager.send_heartbeat("startup")
    if hb_ok:
        logger.info(f"Startup heartbeat accepted: {hb_msg}", "License")
    else:
        logger.debug(f"Startup heartbeat unavailable: {hb_msg}", "License")

    heartbeat_stop = threading.Event()

    def heartbeat_loop():
        while not heartbeat_stop.wait(heartbeat_interval_seconds):
            ok, msg = license_manager.send_heartbeat("running")
            if ok:
                logger.debug(f"Running heartbeat accepted: {msg}", "License")
            else:
                logger.warning(f"Running heartbeat unavailable: {msg}", "License")

    heartbeat_thread = threading.Thread(target=heartbeat_loop, daemon=True, name="LicenseHeartbeat")
    heartbeat_thread.start()

    def tracking_loop():
        while not heartbeat_stop.wait(tracking_poll_interval_seconds):
            ok, msg = license_manager.poll_admin_tasks()
            if ok:
                logger.debug(f"Tracking poll: {msg}", "License")
            else:
                logger.warning(f"Tracking poll idle/unavailable: {msg}", "License")

    tracking_thread = threading.Thread(target=tracking_loop, daemon=True, name="LicenseTrackingPoll")
    tracking_thread.start()

    # Browser Singleton Teardown Hook
    def cleanup_browsers():
        heartbeat_stop.set()
        try:
            hb_ok, hb_msg = license_manager.send_heartbeat("shutdown")
            if hb_ok:
                logger.info(f"Shutdown heartbeat accepted: {hb_msg}", "License")
            else:
                logger.debug(f"Shutdown heartbeat unavailable: {hb_msg}", "License")
        except Exception:
            pass
        logger.info("Application shutting down: cleaning up managed browsers", "App")
        try:
            from modules.shared.managed_chrome_session import get_managed_chrome_session
            get_managed_chrome_session().graceful_close()
        except Exception:
            pass
        try:
            from modules.creator_profiles.ix_link_grabber import get_ix_session
            get_ix_session().close_session()
        except Exception:
            pass
    app.aboutToQuit.connect(cleanup_browsers)

    # Launch main window
    logger.info("Launching main window", "App")
    window = VideoToolSuiteGUI(license_manager, config)
    window.show()

    shutdown_notice_shown = {"value": False}

    def security_watchdog():
        if not license_manager.should_force_shutdown() or shutdown_notice_shown["value"]:
            return
        shutdown_notice_shown["value"] = True
        logger.error(f"Runtime license security lock triggered: {license_manager.last_status_code}", "License")
        QMessageBox.critical(
            window,
            "License Security Lock",
            "OneSoul could not refresh its secure license lease within the allowed window.\n\n"
            "The application will now close."
        )
        app.quit()

    security_timer = QTimer()
    security_timer.setInterval(SECURITY_WATCHDOG_INTERVAL_MS)
    security_timer.timeout.connect(security_watchdog)
    security_timer.start()

    # Run application
    exit_code = app.exec_()

    logger.info("Application shutting down", "App")
    logger.info("=" * 60, "App")

    sys.exit(exit_code)


if __name__ == '__main__':
    main()
