"""
License Activation Dialog
UI for activating ContentFlow Pro licenses
"""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QMessageBox, QProgressBar
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont
from modules.license import LicenseManager
from modules.logging import get_logger


class ActivationThread(QThread):
    """Background thread for license activation"""
    finished = pyqtSignal(bool, str)  # success, message

    def __init__(self, license_manager: LicenseManager, license_key: str):
        super().__init__()
        self.license_manager = license_manager
        self.license_key = license_key

    def run(self):
        try:
            success, message = self.license_manager.activate_license(self.license_key)
            self.finished.emit(success, message)
        except Exception as e:
            self.finished.emit(False, f"Activation error: {str(e)}")


class LicenseActivationDialog(QDialog):
    """
    Dialog for license activation
    """

    def __init__(self, license_manager: LicenseManager, parent=None):
        super().__init__(parent)
        self.license_manager = license_manager
        self.logger = get_logger()
        self.activation_thread = None
        self.init_ui()

    def init_ui(self):
        """Initialize UI"""
        self.setWindowTitle("Activate ContentFlow Pro License")
        self.setModal(True)
        self.setFixedSize(550, 450)

        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(30, 30, 30, 30)

        # Title
        title = QLabel("🔐 License Activation")
        title.setFont(QFont("Arial", 20, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #1ABC9C; padding: 10px;")
        layout.addWidget(title)

        # Subtitle
        subtitle = QLabel("Enter your license key to unlock ContentFlow Pro")
        subtitle.setFont(QFont("Arial", 11))
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color: #BDC3C7; padding-bottom: 10px;")
        layout.addWidget(subtitle)

        # License key input
        key_label = QLabel("License Key:")
        key_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        layout.addWidget(key_label)

        self.license_input = QLineEdit()
        self.license_input.setPlaceholderText("CFPRO-XXXX-XXXX-XXXX-XXXX")
        self.license_input.setFont(QFont("Courier", 11))
        self.license_input.setStyleSheet("""
            QLineEdit {
                padding: 10px;
                border: 2px solid #34495E;
                border-radius: 5px;
                background-color: #2C3E50;
                color: #ECF0F1;
            }
            QLineEdit:focus {
                border: 2px solid #1ABC9C;
            }
        """)
        layout.addWidget(self.license_input)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #34495E;
                border-radius: 5px;
                background-color: #2C3E50;
                text-align: center;
                height: 25px;
            }
            QProgressBar::chunk {
                background-color: #1ABC9C;
            }
        """)
        layout.addWidget(self.progress_bar)

        # Status text
        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setMaximumHeight(120)
        self.status_text.setStyleSheet("""
            QTextEdit {
                border: 2px solid #34495E;
                border-radius: 5px;
                background-color: #2C3E50;
                color: #ECF0F1;
                padding: 10px;
                font-size: 11px;
            }
        """)
        self.status_text.setPlainText("💡 Tips:\n"
                                      "• License keys are case-insensitive\n"
                                      "• One license can be used on one device at a time\n"
                                      "• Contact support if you need to transfer to a new device")
        layout.addWidget(self.status_text)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        self.activate_button = QPushButton("Activate License")
        self.activate_button.setFont(QFont("Arial", 11, QFont.Bold))
        self.activate_button.setStyleSheet("""
            QPushButton {
                background-color: #1ABC9C;
                color: white;
                padding: 12px 25px;
                border: none;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #16A085;
            }
            QPushButton:pressed {
                background-color: #138D75;
            }
            QPushButton:disabled {
                background-color: #566573;
                color: #ABB2B9;
            }
        """)
        self.activate_button.clicked.connect(self.activate)
        button_layout.addWidget(self.activate_button)

        self.buy_button = QPushButton("Buy License")
        self.buy_button.setStyleSheet("""
            QPushButton {
                background-color: #3498DB;
                color: white;
                padding: 12px 25px;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #2E86C1;
            }
        """)
        self.buy_button.clicked.connect(self.buy_license)
        button_layout.addWidget(self.buy_button)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #95A5A6;
                color: white;
                padding: 12px 25px;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #7F8C8D;
            }
        """)
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

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

    def activate(self):
        """Handle activation button click"""
        license_key = self.license_input.text().strip()

        if not license_key:
            QMessageBox.warning(self, "Input Required", "Please enter a license key")
            return

        # Validate format (basic check)
        if not license_key.startswith("CFPRO-"):
            QMessageBox.warning(
                self,
                "Invalid Format",
                "License key should start with 'CFPRO-'\n\n"
                "Example: CFPRO-A1B2-C3D4-E5F6-G7H8"
            )
            return

        # Disable inputs during activation
        self.license_input.setEnabled(False)
        self.activate_button.setEnabled(False)
        self.buy_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.status_text.setPlainText("🔄 Activating license...\nPlease wait...")

        # Log attempt
        self.logger.info(f"Attempting to activate license: {license_key[:12]}...", "License")

        # Start activation in background thread
        self.activation_thread = ActivationThread(self.license_manager, license_key)
        self.activation_thread.finished.connect(self.on_activation_finished)
        self.activation_thread.start()

    def on_activation_finished(self, success: bool, message: str):
        """Handle activation completion"""
        # Re-enable inputs
        self.license_input.setEnabled(True)
        self.activate_button.setEnabled(True)
        self.buy_button.setEnabled(True)
        self.progress_bar.setVisible(False)

        if success:
            self.status_text.setPlainText(f"✅ {message}")
            self.logger.info(f"License activated successfully: {message}", "License")

            # Show success dialog
            QMessageBox.information(
                self,
                "Activation Successful",
                f"{message}\n\nContentFlow Pro is now activated!"
            )

            # Close dialog and accept
            self.accept()

        else:
            self.status_text.setPlainText(f"❌ {message}")
            self.logger.error(f"License activation failed: {message}", "License")

            # Show error dialog
            QMessageBox.critical(
                self,
                "Activation Failed",
                f"{message}\n\n"
                "Please check your license key and try again.\n"
                "If the problem persists, contact support."
            )

    def buy_license(self):
        """Handle buy license button click"""
        message = (
            "ContentFlow Pro Subscription Plans:\n\n"
            "📅 Monthly Plan: $20/month\n"
            "   • All features unlocked\n"
            "   • Unlimited usage\n"
            "   • 30 days access\n\n"
            "📆 Yearly Plan: $200/year (Save $40!)\n"
            "   • All features unlocked\n"
            "   • Unlimited usage\n"
            "   • 365 days access\n\n"
            "🎁 7-Day Free Trial Available!\n\n"
            "Contact: 0307-7361139\n"
            "Email: support@contentflowpro.com"
        )

        QMessageBox.information(self, "Buy License", message)


# Test dialog
if __name__ == '__main__':
    import sys
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    # Mock license manager for testing
    license_manager = LicenseManager(server_url="http://localhost:5000")

    dialog = LicenseActivationDialog(license_manager)
    result = dialog.exec_()

    if result == QDialog.Accepted:
        print("License activated!")
    else:
        print("Activation cancelled")

    sys.exit(0)
