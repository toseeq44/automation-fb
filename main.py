"""
main.py
Main application to launch OneSoul.
"""
import sys
from PyQt5.QtWidgets import QApplication, QMessageBox

# Choose UI version (set USE_MODERN_UI = True for new OneSoul design)
USE_MODERN_UI = True

if USE_MODERN_UI:
    from gui_modern import VideoToolSuiteGUI
else:
    from gui import VideoToolSuiteGUI

from modules.logging import get_logger
from modules.config import get_config
from modules.license import LicenseManager
from modules.ui import LicenseActivationDialog

# Import development mode settings
try:
    from dev_config import DEV_MODE, DEV_CONFIG
except ImportError:
    DEV_MODE = False
    DEV_CONFIG = {}


import os
import shutil
from pathlib import Path

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
        "folder_mappings.json"
    ]
    
    for filename in files_to_restore:
        source = base_path / filename
        target = exe_dir / filename
        
        # If source exists in bundle but target missing in exe dir, copy it
        if source.exists() and not target.exists():
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

    # Initialize license manager
    server_url = config.get('license.server_url', 'http://localhost:5000')
    license_manager = LicenseManager(server_url=server_url)

    # 🔧 DEVELOPMENT MODE CHECK
    if DEV_MODE:
        logger.warning("⚠️  DEVELOPMENT MODE ENABLED - License checks bypassed!", "App")
        logger.warning("⚠️  Set DEV_MODE = False in dev_config.py for production", "App")
        is_valid = True
        message = "Development Mode - License checks skipped"
        license_info = DEV_CONFIG.get('mock_license_info', {})
    else:
        logger.info(f"License server: {server_url}", "License")
        # Check license on startup
        is_valid, message, license_info = license_manager.validate_license()

    if not is_valid:
        logger.warning(f"License validation failed: {message}", "License")

        # Check if no license exists at all
        if not license_info:
            # Show activation dialog
            logger.info("No license found. Showing activation dialog.", "License")

            activation_dialog = LicenseActivationDialog(license_manager)
            result = activation_dialog.exec_()

            if result != activation_dialog.Accepted:
                # User cancelled activation
                logger.info("User cancelled activation. Exiting.", "License")
                QMessageBox.warning(
                    None,
                    "License Required",
                    "OneSoul requires a valid license to run.\n\n"
                    "Please activate a license or purchase one to continue."
                )
                sys.exit(0)
        else:
            # License exists but invalid (expired or offline too long)
            logger.warning("License invalid or expired", "License")
            QMessageBox.critical(
                None,
                "License Expired",
                f"{message}\n\n"
                "Your license has expired or is invalid.\n"
                "Please renew your subscription to continue using OneSoul.\n\n"
                "The application will now close."
            )
            logger.info("License expired. Application exiting.", "License")
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

    # Launch main window
    logger.info("Launching main window", "App")
    window = VideoToolSuiteGUI(license_manager, config)
    window.show()

    # Run application
    exit_code = app.exec_()

    logger.info("Application shutting down", "App")
    logger.info("=" * 60, "App")

    sys.exit(exit_code)


if __name__ == '__main__':
    main()
