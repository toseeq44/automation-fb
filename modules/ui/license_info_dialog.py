"""
License Information Dialog
Shows current license details and management options
Updated for OneSoul Pro Secure License System
"""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QGridLayout, QMessageBox, QFrame, QApplication
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from modules.license.secure_license import SecureLicense, get_hardware_id_display
from modules.logging import get_logger
from datetime import datetime


class LicenseInfoDialog(QDialog):
    """
    Dialog showing license information and management options
    """

    def __init__(self, license_manager, parent=None):
        super().__init__(parent)
        self.license_manager = license_manager
        self.logger = get_logger()
        self.init_ui()

    def init_ui(self):
        """Initialize UI"""
        self.setWindowTitle("License Information - OneSoul Pro")
        self.setModal(True)
        self.setFixedSize(550, 500)

        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(25, 25, 25, 25)

        # Title
        title = QLabel("📋 License Details")
        title.setFont(QFont("Arial", 18, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #00d4ff; padding: 10px;")
        layout.addWidget(title)

        # Get license info
        license_info = self.license_manager.get_license_info()
        is_valid = license_info.get("is_valid", False)
        status_message = license_info.get("status", "Unknown")

        if not is_valid:
            # No License Frame
            no_license_frame = QFrame()
            no_license_frame.setStyleSheet("""
                QFrame {
                    background-color: rgba(233, 69, 96, 0.1);
                    border: 2px solid #e94560;
                    border-radius: 10px;
                    padding: 20px;
                }
            """)
            no_license_layout = QVBoxLayout(no_license_frame)

            no_license_label = QLabel("⚠️ No Valid License Found")
            no_license_label.setAlignment(Qt.AlignCenter)
            no_license_label.setStyleSheet("color: #e94560; font-size: 16px; font-weight: bold;")
            no_license_layout.addWidget(no_license_label)

            msg_label = QLabel("Please activate a license to use OneSoul Pro.\nContact admin via WhatsApp: 0307-7361139")
            msg_label.setAlignment(Qt.AlignCenter)
            msg_label.setStyleSheet("color: #ccc; font-size: 12px; padding: 10px;")
            no_license_layout.addWidget(msg_label)

            layout.addWidget(no_license_frame)
        else:
            # License info group
            info_group = QGroupBox("License Information")
            info_group.setStyleSheet("""
                QGroupBox {
                    font-weight: bold;
                    border: 2px solid #4a4a6a;
                    border-radius: 10px;
                    margin-top: 15px;
                    padding: 15px;
                    background-color: #16213e;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 15px;
                    padding: 0 10px;
                    color: #00d4ff;
                }
            """)

            info_layout = QGridLayout()
            info_layout.setSpacing(12)
            info_layout.setColumnStretch(1, 1)

            # Get data from license_info
            plan_name = license_info.get('plan_name', 'Unknown')
            days_remaining = license_info.get('days_remaining', 0)
            expiry = license_info.get('expiry', '')
            hardware_id = license_info.get('hardware_id', get_hardware_id_display())
            daily_downloads = license_info.get('daily_downloads')
            daily_pages = license_info.get('daily_pages')

            # Determine status color
            if days_remaining <= 3:
                status_color = "#e94560"
                status_icon = "🔴"
            elif days_remaining <= 7:
                status_color = "#f39c12"
                status_icon = "🟡"
            else:
                status_color = "#4ecca3"
                status_icon = "✅"

            # License details
            details = [
                ("Status:", f"{status_icon} Active", status_color),
                ("Plan:", plan_name, "#00d4ff"),
                ("Days Remaining:", str(days_remaining), status_color),
                ("Expiry Date:", self._format_date(expiry), "#ccc"),
                ("Hardware ID:", hardware_id, "#888"),
                ("Daily Downloads:", "Unlimited" if daily_downloads is None else str(daily_downloads), "#4ecca3" if daily_downloads is None else "#ccc"),
                ("Daily Pages:", "Unlimited" if daily_pages is None else str(daily_pages), "#4ecca3" if daily_pages is None else "#ccc"),
            ]

            row = 0
            for label_text, value_text, color in details:
                # Label
                label = QLabel(label_text)
                label.setStyleSheet("font-weight: bold; color: #888; font-size: 12px;")
                info_layout.addWidget(label, row, 0, Qt.AlignRight)

                # Value
                value = QLabel(value_text)
                value.setStyleSheet(f"color: {color}; font-size: 13px; font-weight: bold;")
                value.setWordWrap(True)
                info_layout.addWidget(value, row, 1)

                row += 1

            info_group.setLayout(info_layout)
            layout.addWidget(info_group)

            # Status message
            status_frame = QFrame()
            status_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: rgba(78, 204, 163, 0.1);
                    border: 1px solid {status_color};
                    border-radius: 8px;
                    padding: 10px;
                }}
            """)
            status_layout = QVBoxLayout(status_frame)
            status_label = QLabel(f"📊 {status_message}")
            status_label.setAlignment(Qt.AlignCenter)
            status_label.setStyleSheet(f"color: {status_color}; font-size: 12px;")
            status_layout.addWidget(status_label)
            layout.addWidget(status_frame)

        # Hardware ID Copy Section
        hw_frame = QFrame()
        hw_frame.setStyleSheet("""
            QFrame {
                background-color: #0f0f23;
                border: 1px solid #4a4a6a;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        hw_layout = QHBoxLayout(hw_frame)

        hw_label = QLabel(f"🔑 Hardware ID: {get_hardware_id_display()}")
        hw_label.setStyleSheet("color: #888; font-size: 11px;")
        hw_layout.addWidget(hw_label)

        copy_btn = QPushButton("📋 Copy")
        copy_btn.setMaximumWidth(70)
        copy_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a4a6a;
                color: white;
                padding: 5px 10px;
                border: none;
                border-radius: 4px;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #5a5a7a;
            }
        """)
        copy_btn.clicked.connect(self._copy_hardware_id)
        hw_layout.addWidget(copy_btn)

        layout.addWidget(hw_frame)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        if is_valid:
            # Deactivate button
            self.deactivate_button = QPushButton("🗑️ Deactivate License")
            self.deactivate_button.setStyleSheet("""
                QPushButton {
                    background-color: #e94560;
                    color: white;
                    padding: 12px 20px;
                    border: none;
                    border-radius: 8px;
                    font-weight: bold;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #ff6b6b;
                }
            """)
            self.deactivate_button.clicked.connect(self.deactivate)
            button_layout.addWidget(self.deactivate_button)

        # Close button
        close_button = QPushButton("✓ Close")
        close_button.setStyleSheet("""
            QPushButton {
                background-color: #4ecca3;
                color: #000;
                padding: 12px 20px;
                border: none;
                border-radius: 8px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #6ee6b8;
            }
        """)
        close_button.clicked.connect(self.accept)
        button_layout.addWidget(close_button)

        layout.addLayout(button_layout)

        self.setLayout(layout)
        self.apply_dark_theme()

    def apply_dark_theme(self):
        """Apply dark theme"""
        self.setStyleSheet("""
            QDialog {
                background-color: #1a1a2e;
                color: #ECF0F1;
            }
            QLabel {
                color: #ECF0F1;
            }
        """)

    def _format_date(self, date_str: str) -> str:
        """Format ISO date string to readable format"""
        if not date_str:
            return "N/A"

        try:
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return dt.strftime("%d %b %Y")
        except:
            return date_str

    def _copy_hardware_id(self):
        """Copy hardware ID to clipboard"""
        clipboard = QApplication.clipboard()
        clipboard.setText(get_hardware_id_display())
        QMessageBox.information(self, "Copied", "Hardware ID copied to clipboard!")

    def deactivate(self):
        """Handle deactivate button click"""
        # Confirm deactivation
        reply = QMessageBox.question(
            self,
            "Confirm Deactivation",
            "Are you sure you want to deactivate this license?\n\n"
            "You will need to activate it again to use OneSoul Pro.\n"
            "The license key will be removed from this device.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            success, message = self.license_manager.deactivate_license()

            if success:
                self.logger.info("License deactivated successfully", "License")
                QMessageBox.information(
                    self,
                    "License Deactivated",
                    "Your license has been deactivated.\n\n"
                    "You can activate it again later."
                )
                self.accept()
            else:
                self.logger.error(f"Failed to deactivate license: {message}", "License")
                QMessageBox.critical(
                    self,
                    "Deactivation Failed",
                    f"{message}\n\nPlease try again or contact support."
                )


# Test dialog
if __name__ == '__main__':
    import sys

    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    license_manager = SecureLicense()

    dialog = LicenseInfoDialog(license_manager)
    dialog.exec_()

    sys.exit(0)
