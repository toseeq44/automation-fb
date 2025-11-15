#!/usr/bin/env python3
"""
OneSoul Flow - Demo Application
Run this to see the new modern UI design
"""

import sys
import os

# Add current directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from components.main_window import OneSoulFlowWindow


def main():
    """Run the demo application"""
    # Enable high DPI scaling
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    # Create application
    app = QApplication(sys.argv)

    # Create and configure main window
    window = OneSoulFlowWindow()

    # Set user information (example)
    window.set_user_info(
        name="Toseeq Ur Rehman",
        license_active=True,
        license_text="✓ License Active"
    )

    # Show window
    window.show()

    # Run application
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
