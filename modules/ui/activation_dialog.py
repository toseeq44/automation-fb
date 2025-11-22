"""
License Activation Dialog
UI for activating OneSoul Pro licenses with Hardware Binding
"""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QMessageBox, QProgressBar, QFrame,
    QApplication
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont

# Import new secure license system
from modules.license.secure_license import (
    SecureLicense, get_hardware_id_display, PLAN_CONFIG
)
from modules.logging import get_logger


class ActivationThread(QThread):
    """Background thread for license activation"""
    finished = pyqtSignal(bool, str, object)  # success, message, info

    def __init__(self, license_manager: SecureLicense, license_key: str):
        super().__init__()
        self.license_manager = license_manager
        self.license_key = license_key

    def run(self):
        try:
            # Validate and save license
            success, message = self.license_manager.save_license(self.license_key)

            if success:
                # Get license info
                _, _, info = self.license_manager.load_license()
                self.finished.emit(True, message, info)
            else:
                self.finished.emit(False, message, None)
        except Exception as e:
            self.finished.emit(False, f"Activation error: {str(e)}", None)


class LicenseActivationDialog(QDialog):
    """
    Dialog for license activation with Hardware ID display
    """

    def __init__(self, license_manager=None, parent=None):
        super().__init__(parent)
        # Use new secure license system
        self.license_manager = SecureLicense()
        self.logger = get_logger()
        self.activation_thread = None
        self.init_ui()

    def init_ui(self):
        """Initialize UI"""
        self.setWindowTitle("Activate OneSoul Pro License")
        self.setModal(True)
        self.setFixedSize(600, 580)

        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(25, 25, 25, 25)

        # Title
        title = QLabel("🔐 License Activation")
        title.setFont(QFont("Arial", 20, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #00d4ff; padding: 10px;")
        layout.addWidget(title)

        # Hardware ID Section
        hw_frame = QFrame()
        hw_frame.setStyleSheet("""
            QFrame {
                background-color: #16213e;
                border: 2px solid #4a4a6a;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        hw_layout = QVBoxLayout(hw_frame)

        hw_title = QLabel("📱 Your Hardware ID (Send this to admin)")
        hw_title.setStyleSheet("font-weight: bold; color: #ff6b6b; font-size: 12px;")
        hw_layout.addWidget(hw_title)

        hw_id_layout = QHBoxLayout()
        self.hw_id_label = QLabel(get_hardware_id_display())
        self.hw_id_label.setFont(QFont("Courier", 14, QFont.Bold))
        self.hw_id_label.setStyleSheet("""
            color: #00ff00;
            background-color: #0f0f23;
            padding: 10px;
            border-radius: 5px;
        """)
        self.hw_id_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        hw_id_layout.addWidget(self.hw_id_label)

        copy_hw_btn = QPushButton("📋 Copy")
        copy_hw_btn.setMaximumWidth(80)
        copy_hw_btn.clicked.connect(self.copy_hardware_id)
        copy_hw_btn.setStyleSheet("""
            QPushButton {
                background-color: #4ecca3;
                color: #000;
                padding: 8px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #6ee6b8;
            }
        """)
        hw_id_layout.addWidget(copy_hw_btn)

        hw_layout.addLayout(hw_id_layout)

        hw_note = QLabel("⚠️ Send this Hardware ID to get your license key")
        hw_note.setStyleSheet("color: #ffa500; font-size: 11px;")
        hw_layout.addWidget(hw_note)

        layout.addWidget(hw_frame)

        # License key input
        key_label = QLabel("🔑 Enter License Key:")
        key_label.setStyleSheet("font-weight: bold; font-size: 13px; margin-top: 10px;")
        layout.addWidget(key_label)

        self.license_input = QTextEdit()
        self.license_input.setPlaceholderText("CF-gAAAAABn... (Paste your license key here)")
        self.license_input.setFont(QFont("Courier", 10))
        self.license_input.setMaximumHeight(80)
        self.license_input.setStyleSheet("""
            QTextEdit {
                padding: 10px;
                border: 2px solid #4a4a6a;
                border-radius: 5px;
                background-color: #0f0f23;
                color: #00ff00;
            }
            QTextEdit:focus {
                border: 2px solid #00d4ff;
            }
        """)
        layout.addWidget(self.license_input)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumHeight(8)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                border-radius: 4px;
                background-color: #2C3E50;
            }
            QProgressBar::chunk {
                background-color: #00d4ff;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.progress_bar)

        # Status text
        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setMaximumHeight(100)
        self.status_text.setStyleSheet("""
            QTextEdit {
                border: 2px solid #4a4a6a;
                border-radius: 5px;
                background-color: #16213e;
                color: #ccc;
                padding: 10px;
                font-size: 11px;
            }
        """)
        self.status_text.setPlainText(
            "📋 HOW TO ACTIVATE:\n"
            "1. Copy your Hardware ID (above)\n"
            "2. Send it to admin with payment\n"
            "3. Receive your license key\n"
            "4. Paste license key and click Activate"
        )
        layout.addWidget(self.status_text)

        # Pricing info
        pricing_frame = QFrame()
        pricing_frame.setStyleSheet("""
            QFrame {
                background-color: #1a1a2e;
                border: 1px solid #4a4a6a;
                border-radius: 5px;
                padding: 5px;
            }
        """)
        pricing_layout = QHBoxLayout(pricing_frame)
        pricing_layout.setSpacing(20)

        basic_label = QLabel("📦 BASIC: Rs 10,000/month\n(200 downloads/day)")
        basic_label.setStyleSheet("color: #3498db; font-size: 11px;")
        pricing_layout.addWidget(basic_label)

        pro_label = QLabel("⭐ PRO: Rs 15,000/month\n(Unlimited)")
        pro_label.setStyleSheet("color: #f39c12; font-size: 11px;")
        pricing_layout.addWidget(pro_label)

        layout.addWidget(pricing_frame)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        self.activate_button = QPushButton("✅ Activate License")
        self.activate_button.setFont(QFont("Arial", 11, QFont.Bold))
        self.activate_button.setStyleSheet("""
            QPushButton {
                background-color: #00d4ff;
                color: #000;
                padding: 12px 25px;
                border: none;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #33e0ff;
            }
            QPushButton:disabled {
                background-color: #566573;
                color: #ABB2B9;
            }
        """)
        self.activate_button.clicked.connect(self.activate)
        button_layout.addWidget(self.activate_button)

        self.contact_button = QPushButton("📞 Contact Admin")
        self.contact_button.setStyleSheet("""
            QPushButton {
                background-color: #4ecca3;
                color: #000;
                padding: 12px 25px;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #6ee6b8;
            }
        """)
        self.contact_button.clicked.connect(self.show_contact)
        button_layout.addWidget(self.contact_button)

        self.cancel_button = QPushButton("❌ Cancel")
        self.cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #e94560;
                color: white;
                padding: 12px 25px;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #ff6b6b;
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
                background-color: #1a1a2e;
                color: #ECF0F1;
            }
            QLabel {
                color: #ECF0F1;
            }
        """)

    def copy_hardware_id(self):
        """Copy hardware ID to clipboard"""
        hw_id = self.hw_id_label.text()
        clipboard = QApplication.clipboard()
        clipboard.setText(hw_id)
        self.status_text.setPlainText(f"✅ Hardware ID copied to clipboard!\n\n{hw_id}\n\nSend this to admin to get your license.")

    def activate(self):
        """Handle activation button click"""
        license_key = self.license_input.toPlainText().strip()

        if not license_key:
            QMessageBox.warning(self, "Input Required", "Please enter a license key")
            return

        # Validate format (basic check)
        if not license_key.startswith("CF-"):
            QMessageBox.warning(
                self,
                "Invalid Format",
                "Invalid license key format.\n\n"
                "License key should start with 'CF-'\n"
                "Please check and try again."
            )
            return

        # Disable inputs during activation
        self.license_input.setEnabled(False)
        self.activate_button.setEnabled(False)
        self.contact_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.status_text.setPlainText("🔄 Validating license...\nPlease wait...")

        # Log attempt
        self.logger.info(f"Attempting to activate license: {license_key[:20]}...", "License")

        # Start activation in background thread
        self.activation_thread = ActivationThread(self.license_manager, license_key)
        self.activation_thread.finished.connect(self.on_activation_finished)
        self.activation_thread.start()

    def on_activation_finished(self, success: bool, message: str, info: dict):
        """Handle activation completion"""
        # Re-enable inputs
        self.license_input.setEnabled(True)
        self.activate_button.setEnabled(True)
        self.contact_button.setEnabled(True)
        self.progress_bar.setVisible(False)

        if success:
            plan_name = info.get('plan_name', 'Unknown') if info else 'Unknown'
            days = info.get('days_remaining', 0) if info else 0

            self.status_text.setPlainText(
                f"✅ LICENSE ACTIVATED!\n\n"
                f"Plan: {plan_name}\n"
                f"Days Remaining: {days}\n"
                f"Status: Active"
            )
            self.logger.info(f"License activated successfully: {message}", "License")

            # Show success dialog
            QMessageBox.information(
                self,
                "Activation Successful",
                f"🎉 License Activated Successfully!\n\n"
                f"Plan: {plan_name}\n"
                f"Valid for: {days} days\n\n"
                f"Enjoy OneSoul Pro!"
            )

            # Close dialog and accept
            self.accept()

        else:
            self.status_text.setPlainText(f"❌ ACTIVATION FAILED\n\n{message}")
            self.logger.error(f"License activation failed: {message}", "License")

            # Show error dialog
            QMessageBox.critical(
                self,
                "Activation Failed",
                f"❌ {message}\n\n"
                "Please check:\n"
                "• License key is correct\n"
                "• Hardware ID matches\n"
                "• License hasn't expired\n\n"
                "Contact admin if problem persists."
            )

    def show_contact(self):
        """Show contact information"""
        message = (
            "📞 CONTACT INFORMATION\n\n"
            "─────────────────────────────\n\n"
            "WhatsApp: 0307-7361139\n\n"
            "─────────────────────────────\n\n"
            "📋 To purchase a license:\n"
            "1. Copy your Hardware ID\n"
            "2. Send it via WhatsApp\n"
            "3. Make payment\n"
            "4. Receive your license key\n\n"
            "─────────────────────────────\n\n"
            f"Your Hardware ID:\n{get_hardware_id_display()}"
        )

        QMessageBox.information(self, "Contact Admin", message)


# Test dialog
if __name__ == '__main__':
    import sys

    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    dialog = LicenseActivationDialog()
    result = dialog.exec_()

    if result == QDialog.Accepted:
        print("License activated!")
    else:
        print("Activation cancelled")

    sys.exit(0)
