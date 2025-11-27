"""
License Information Dialog
Shows current license details and management options
"""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QGridLayout, QMessageBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from modules.license import LicenseManager
from modules.logging import get_logger
from datetime import datetime


class LicenseInfoDialog(QDialog):
    """
    Dialog showing license information and management options
    """

    def __init__(self, license_manager: LicenseManager, parent=None):
        super().__init__(parent)
        self.license_manager = license_manager
        self.logger = get_logger()
        self.init_ui()

    def init_ui(self):
        """Initialize UI"""
        self.setWindowTitle("License Information")
        self.setModal(True)
        self.setFixedSize(500, 450)

        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(25, 25, 25, 25)

        # Title
        title = QLabel("📋 License Details")
        title.setFont(QFont("Arial", 18, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #1ABC9C; padding: 10px;")
        layout.addWidget(title)

        # Get license info
        license_info = self.license_manager.get_license_info()
        is_valid, status_message, _ = self.license_manager.validate_license()

        if not license_info:
            no_license_label = QLabel("⚠️ No License Found\n\nPlease activate a license to use OneSoul.")
            no_license_label.setAlignment(Qt.AlignCenter)
            no_license_label.setStyleSheet("padding: 30px; font-size: 13px;")
            layout.addWidget(no_license_label)
        else:
            # License info group
            info_group = QGroupBox("License Information")
            info_group.setStyleSheet("""
                QGroupBox {
                    font-weight: bold;
                    border: 2px solid #34495E;
                    border-radius: 8px;
                    margin-top: 10px;
                    padding-top: 10px;
                    background-color: #2C3E50;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px;
                    color: #1ABC9C;
                }
            """)

            info_layout = QGridLayout()
            info_layout.setSpacing(10)
            info_layout.setColumnStretch(1, 1)

            # License details
            details = [
                ("Status:", "✅ Active" if is_valid else "⚠️ Invalid/Expired"),
                ("License Key:", license_info.get('license_key', 'N/A')),
                ("Plan Type:", license_info.get('plan_type', 'N/A').capitalize()),
                ("Device:", license_info.get('device_name', 'N/A')),
                ("Days Remaining:", str(license_info.get('days_remaining', 0))),
                ("Expiry Date:", self._format_date(license_info.get('expiry_date'))),
                ("Last Validation:", self._format_date(license_info.get('last_validation'))),
            ]

            row = 0
            for label_text, value_text in details:
                # Label
                label = QLabel(label_text)
                label.setStyleSheet("font-weight: bold; color: #BDC3C7;")
                info_layout.addWidget(label, row, 0, Qt.AlignRight)

                # Value
                value = QLabel(value_text)
                value.setStyleSheet("color: #ECF0F1;")
                value.setWordWrap(True)
                info_layout.addWidget(value, row, 1)

                row += 1

            info_group.setLayout(info_layout)
            layout.addWidget(info_group)

            # Status message
            status_label = QLabel(status_message)
            status_label.setAlignment(Qt.AlignCenter)
            status_label.setStyleSheet("""
                padding: 10px;
                background-color: #34495E;
                border-radius: 5px;
                font-size: 11px;
            """)
            layout.addWidget(status_label)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        if license_info:
            # Deactivate button
            self.deactivate_button = QPushButton("Deactivate License")
            self.deactivate_button.setStyleSheet("""
                QPushButton {
                    background-color: #E74C3C;
                    color: white;
                    padding: 10px 20px;
                    border: none;
                    border-radius: 5px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #C0392B;
                }
            """)
            self.deactivate_button.clicked.connect(self.deactivate)
            button_layout.addWidget(self.deactivate_button)

        # Close button
        close_button = QPushButton("Close")
        close_button.setStyleSheet("""
            QPushButton {
                background-color: #95A5A6;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #7F8C8D;
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
                background-color: #23272A;
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
            return dt.strftime("%Y-%m-%d %H:%M")
        except:
            return date_str

    def deactivate(self):
        """Handle deactivate button click"""
        # Confirm deactivation
        reply = QMessageBox.question(
            self,
            "Confirm Deactivation",
            "Are you sure you want to deactivate this license?\n\n"
            "You will need to activate it again to use OneSoul.\n"
            "You can then use it on a different device if needed.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.logger.info("User requested license deactivation", "License")

            # Deactivate
            success, message = self.license_manager.deactivate_license()

            if success:
                self.logger.info(f"License deactivated: {message}", "License")
                QMessageBox.information(
                    self,
                    "Deactivation Successful",
                    f"{message}\n\nThe application will now close."
                )
                self.accept()
            else:
                self.logger.error(f"License deactivation failed: {message}", "License")
                QMessageBox.critical(
                    self,
                    "Deactivation Failed",
                    f"{message}\n\nPlease try again or contact support."
                )


# Test dialog
if __name__ == '__main__':
    import sys
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    license_manager = LicenseManager(server_url="http://localhost:5000")

    dialog = LicenseInfoDialog(license_manager)
    dialog.exec_()

    sys.exit(0)
