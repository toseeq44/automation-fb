"""
main.py
Main application to launch OneSoul Pro.
Version 2.0 - Secure License System with Hardware Binding
"""
import sys

# PyInstaller EXE support - must be before other imports
if getattr(sys, 'frozen', False):
    import multiprocessing
    multiprocessing.freeze_support()

from PyQt5.QtWidgets import QApplication, QMessageBox

# Choose UI version
USE_MODERN_UI = True

if USE_MODERN_UI:
    from gui_modern import VideoToolSuiteGUI
else:
    from gui import VideoToolSuiteGUI

from modules.logging import get_logger
from modules.config import get_config
from modules.license.secure_license import SecureLicense, get_plan_info, get_hardware_id_display
from modules.ui import LicenseActivationDialog

# Import development mode settings
try:
    from dev_config import DEV_MODE, DEV_CONFIG
except ImportError:
    DEV_MODE = False
    DEV_CONFIG = {}


def main():
    """Launch the OneSoul Pro application"""

    # Initialize application
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # Modern look across platforms

    # Initialize logger
    logger = get_logger("ContentFlowPro")
    logger.info("=" * 60, "App")
    logger.info("OneSoul Pro - Video Automation Suite", "App")
    logger.info("Version 2.0.0 - Secure License", "App")
    logger.info("=" * 60, "App")

    # Initialize config
    config = get_config()
    logger.info(f"Config loaded from: {config.config_path}", "App")

    # Ensure directories exist
    config.ensure_directories_exist()

    # Initialize secure license manager (NO SERVER NEEDED!)
    license_manager = SecureLicense()

    # Log hardware ID for debugging
    logger.info(f"Hardware ID: {get_hardware_id_display()}", "License")

    # 🔧 DEVELOPMENT MODE CHECK
    if DEV_MODE:
        logger.warning("⚠️  DEVELOPMENT MODE ENABLED - License checks bypassed!", "App")
        logger.warning("⚠️  Set DEV_MODE = False in dev_config.py for production", "App")
        is_valid = True
        message = "Development Mode - License checks skipped"
        license_info = DEV_CONFIG.get('mock_license_info', {
            'plan': 'pro',
            'plan_name': 'Pro (Dev)',
            'days_remaining': 999,
            'daily_downloads': None,
            'daily_pages': None,
        })
    else:
        # Check license using new secure system (OFFLINE - no server!)
        is_valid, message, license_info = license_manager.load_license()
        logger.info(f"License check: {message}", "License")

    if not is_valid:
        logger.warning(f"License validation failed: {message}", "License")

        # Show activation dialog
        logger.info("No valid license found. Showing activation dialog.", "License")

        activation_dialog = LicenseActivationDialog(license_manager)
        result = activation_dialog.exec_()

        if result != activation_dialog.Accepted:
            # User cancelled activation
            logger.info("User cancelled activation. Exiting.", "License")
            QMessageBox.warning(
                None,
                "License Required",
                "OneSoul Pro requires a valid license to run.\n\n"
                "Please purchase a license to continue.\n\n"
                f"Your Hardware ID: {get_hardware_id_display()}\n"
                "Send this to admin to get your license."
            )
            sys.exit(0)

        # Re-check license after activation
        is_valid, message, license_info = license_manager.load_license()

    if is_valid:
        logger.info(f"License validated successfully: {message}", "License")
        days_remaining = license_info.get('days_remaining', 0) if license_info else 0
        plan_name = license_info.get('plan_name', 'Unknown') if license_info else 'Unknown'

        logger.info(f"Plan: {plan_name}, Days remaining: {days_remaining}", "License")

        # Warn if expiring soon
        if days_remaining <= 7 and days_remaining > 0:
            logger.warning(f"License expiring in {days_remaining} days", "License")
            QMessageBox.warning(
                None,
                "License Expiring Soon",
                f"Your {plan_name} license will expire in {days_remaining} day(s).\n\n"
                "Please renew your subscription to continue using OneSoul Pro.\n\n"
                "Contact: WhatsApp 0307-7361139"
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
