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


def main():
    """Launch the OneSoul application"""
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
            QMessageBox.warning(
                None,
                "License Issue",
                f"{message}\n\n"
                "Please check your license or renew your subscription.\n"
                "Some features may be limited."
            )
            # Allow app to run in demo mode
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
