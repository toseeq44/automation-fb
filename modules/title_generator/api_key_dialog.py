"""
API Key Setup Dialog for Title Generator
User-friendly dialog to get and validate Groq API key
"""

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QLineEdit, QPushButton, QTextEdit, QMessageBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont
from modules.logging.logger import get_logger
from .api_manager import APIKeyManager

logger = get_logger(__name__)


class ValidationThread(QThread):
    """Background thread for API key validation"""

    validation_complete = pyqtSignal(bool, str)  # (success, message)

    def __init__(self, api_manager, api_key):
        super().__init__()
        self.api_manager = api_manager
        self.api_key = api_key

    def run(self):
        """Run validation in background"""
        success, message = self.api_manager.validate_api_key(self.api_key)
        self.validation_complete.emit(success, message)


class APIKeyDialog(QDialog):
    """Dialog for Groq API key setup"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.api_manager = APIKeyManager()
        self.validation_thread = None
        self.setup_ui()

    def setup_ui(self):
        """Setup UI components"""
        self.setWindowTitle("🔑 Groq API Key Setup")
        self.setMinimumWidth(500)
        self.setModal(True)

        layout = QVBoxLayout()
        layout.setSpacing(15)

        # Title
        title = QLabel("Title Generator - API Key Required")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        # Instructions
        instructions = QTextEdit()
        instructions.setReadOnly(True)
        instructions.setMaximumHeight(150)
        instructions.setHtml("""
        <p>To use the Title Generator, you need a <b>FREE</b> Groq API key.</p>

        <p><b>How to get your API key:</b></p>
        <ol>
            <li>Go to <a href="https://console.groq.com">console.groq.com</a></li>
            <li>Sign up for a free account</li>
            <li>Navigate to API Keys section</li>
            <li>Create a new API key</li>
            <li>Copy and paste it below</li>
        </ol>

        <p><i>Your key is stored securely and only used for title generation.</i></p>
        """)
        layout.addWidget(instructions)

        # API Key input
        key_label = QLabel("API Key:")
        layout.addWidget(key_label)

        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("gsk_...")
        self.key_input.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.key_input)

        # Show/Hide key button
        show_key_btn = QPushButton("👁 Show Key")
        show_key_btn.setMaximumWidth(120)
        show_key_btn.setCheckable(True)
        show_key_btn.toggled.connect(self.toggle_key_visibility)
        layout.addWidget(show_key_btn)

        # Test connection button
        test_layout = QHBoxLayout()
        self.test_btn = QPushButton("🔌 Test Connection")
        self.test_btn.clicked.connect(self.test_connection)
        test_layout.addWidget(self.test_btn)

        self.status_label = QLabel("")
        test_layout.addWidget(self.status_label)
        test_layout.addStretch()

        layout.addLayout(test_layout)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        self.save_btn = QPushButton("💾 Save & Continue")
        self.save_btn.clicked.connect(self.save_and_continue)
        self.save_btn.setEnabled(False)  # Disabled until validation
        button_layout.addWidget(self.save_btn)

        layout.addLayout(button_layout)

        self.setLayout(layout)

    def toggle_key_visibility(self, checked):
        """Toggle API key visibility"""
        if checked:
            self.key_input.setEchoMode(QLineEdit.Normal)
        else:
            self.key_input.setEchoMode(QLineEdit.Password)

    def test_connection(self):
        """Test API key with Groq API"""
        api_key = self.key_input.text().strip()

        if not api_key:
            self.status_label.setText("❌ Please enter API key")
            self.status_label.setStyleSheet("color: red;")
            return

        # Disable inputs during validation
        self.test_btn.setEnabled(False)
        self.key_input.setEnabled(False)
        self.status_label.setText("⏳ Testing connection...")
        self.status_label.setStyleSheet("color: orange;")

        # Start validation in background thread
        self.validation_thread = ValidationThread(self.api_manager, api_key)
        self.validation_thread.validation_complete.connect(self.on_validation_complete)
        self.validation_thread.start()

    def on_validation_complete(self, success, message):
        """Handle validation result"""
        # Re-enable inputs
        self.test_btn.setEnabled(True)
        self.key_input.setEnabled(True)

        # Update status
        self.status_label.setText(message)

        if success:
            self.status_label.setStyleSheet("color: green;")
            self.save_btn.setEnabled(True)
        else:
            self.status_label.setStyleSheet("color: red;")
            self.save_btn.setEnabled(False)

    def save_and_continue(self):
        """Save API key and close dialog"""
        api_key = self.key_input.text().strip()

        if not api_key:
            QMessageBox.warning(self, "Error", "Please enter API key")
            return

        # Save API key
        if self.api_manager.set_api_key(api_key):
            logger.info("API key saved successfully")
            self.accept()
        else:
            QMessageBox.critical(self, "Error", "Failed to save API key")
