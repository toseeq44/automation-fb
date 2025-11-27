"""
License Activation Dialog
UI for activating OneSoul licenses
"""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QMessageBox, QProgressBar, QApplication
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont

from modules.license import LicenseManager, generate_hardware_id
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
    """Dialog for license activation"""

    def __init__(self, license_manager: LicenseManager, parent=None):
        super().__init__(parent)
        self.license_manager = license_manager
        self.logger = get_logger()
        self.activation_thread = None
        self.init_ui()

    def init_ui(self):
        """Initialize UI"""
        self.setWindowTitle("Activate OneSoul License")
        self.setModal(True)
        self.setFixedSize(550, 470)

        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(30, 30, 30, 30)

        # Title
        title = QLabel("OneSoul License Activation")
        title.setFont(QFont("Arial", 20, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #1ABC9C; padding: 10px;")
        layout.addWidget(title)

        # Subtitle
        subtitle = QLabel("Enter your license key to unlock OneSoul")
        subtitle.setFont(QFont("Arial", 11))
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color: #BDC3C7; padding-bottom: 10px;")
        layout.addWidget(subtitle)

        # Hardware ID (for admin to generate license)
        self.hardware_id = generate_hardware_id()
        hw_row = QHBoxLayout()
        hw_label = QLabel(f"Hardware ID: {self.hardware_id}")
        hw_label.setWordWrap(True)
        hw_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        hw_label.setStyleSheet(
            "color: #95A5A6; font-size: 11px; padding: 6px;"
            "border: 1px solid #34495E; border-radius: 4px;"
        )
        copy_btn = QPushButton("Copy")
        copy_btn.setFixedWidth(70)
        copy_btn.setStyleSheet("""
            QPushButton {
                padding: 6px 10px;
                background-color: #1ABC9C;
                border: none;
                color: white;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #16A085;
            }
        """)
        copy_btn.clicked.connect(self.copy_hardware_id)
        hw_row.addWidget(hw_label, 1)
        hw_row.addWidget(copy_btn, 0, Qt.AlignRight)
        layout.addLayout(hw_row)

        # License key input
        key_label = QLabel("License Key:")
        key_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        layout.addWidget(key_label)

        self.license_input = QLineEdit()
        self.license_input.setPlaceholderText("ONESOUL-XXXX-XXXX-XXXX-XXXX")
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
        layout.addWidget(self.status_text)

        # Buttons
        button_layout = QHBoxLayout()

        self.activate_button = QPushButton("Activate")
        self.activate_button.clicked.connect(self.activate_license)
        self.activate_button.setStyleSheet("""
            QPushButton {
                padding: 10px 20px;
                background-color: #1ABC9C;
                border: none;
                color: white;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #16A085;
            }
            QPushButton:disabled {
                background-color: #7F8C8D;
            }
        """)
        button_layout.addWidget(self.activate_button)

        self.buy_button = QPushButton("Plans & Pricing")
        self.buy_button.clicked.connect(self.buy_license)
        self.buy_button.setStyleSheet("""
            QPushButton {
                padding: 10px 20px;
                background-color: #34495E;
                border: none;
                color: white;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2C3E50;
            }
        """)
        button_layout.addWidget(self.buy_button)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        self.cancel_button.setStyleSheet("""
            QPushButton {
                padding: 10px 20px;
                background-color: #7F8C8D;
                border: none;
                color: white;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #95A5A6;
            }
        """)
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)
        self.setLayout(layout)

    def activate_license(self):
        """Start activation process"""
        license_key = self.license_input.text().strip()

        if not license_key:
            QMessageBox.warning(self, "Missing License Key", "Please enter your license key.")
            return

        # Disable inputs during activation
        self.license_input.setEnabled(False)
        self.activate_button.setEnabled(False)
        self.buy_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.status_text.setPlainText("Activating license... Please wait.")

        # Start background activation
        self.activation_thread = ActivationThread(self.license_manager, license_key)
        self.activation_thread.finished.connect(self.handle_activation_result)
        self.activation_thread.start()

    def handle_activation_result(self, success: bool, message: str):
        """Handle result from activation thread"""
        # Re-enable inputs
        self.license_input.setEnabled(True)
        self.activate_button.setEnabled(True)
        self.buy_button.setEnabled(True)
        self.progress_bar.setVisible(False)

        if success:
            self.status_text.setPlainText(f"✓ {message}")
            self.logger.info(f"License activated successfully: {message}", "License")

            QMessageBox.information(
                self,
                "Activation Successful",
                f"{message}\n\nOneSoul is now activated!"
            )
            self.accept()
        else:
            self.status_text.setPlainText(f"✗ {message}")
            self.logger.error(f"License activation failed: {message}", "License")
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
            "OneSoul Subscription Plans:\n\n"
            "• Basic (Monthly): Rs 10,000\n"
            "• Pro (Monthly): Rs 15,000\n"
            "No yearly plan available.\n\n"
            "Email: onesoulforeveryone@gmail.com"
        )
        QMessageBox.information(self, "Buy License", message)

    def copy_hardware_id(self):
        """Copy hardware ID to clipboard"""
        clipboard = QApplication.clipboard()
        clipboard.setText(self.hardware_id)
        QMessageBox.information(
            self,
            "Copied",
            "Hardware ID copied to clipboard.\nShare this ID with admin to get a license."
        )


# Test dialog
if __name__ == '__main__':
    import sys
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
