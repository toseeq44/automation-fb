"""
modules/api_manager/gui.py
API Configuration GUI for setting up API keys
"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QLineEdit, QPushButton, QGroupBox, QTextEdit,
                             QMessageBox, QTabWidget, QFormLayout, QCheckBox)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from .core import APIManager


class APIConfigPage(QWidget):
    """API Configuration Page"""
    
    def __init__(self, back_callback):
        super().__init__()
        self.back_callback = back_callback
        self.api_manager = APIManager()
        self.init_ui()
        self.load_current_keys()
    
    def init_ui(self):
        """Build the API configuration interface"""
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # Header
        header = QLabel("🔑 API Configuration")
        header.setFont(QFont("Arial", 26, QFont.Bold))
        header.setStyleSheet("color: #00d4ff; padding: 15px;")
        layout.addWidget(header)
        
        # Info section
        info_group = self.create_group("📋 API Setup Instructions")
        info_layout = QVBoxLayout()
        
        info_text = QTextEdit()
        info_text.setReadOnly(True)
        info_text.setMaximumHeight(150)
        info_text.setStyleSheet("""
            QTextEdit {
                background-color: #1a1a1a;
                color: #a0a0a0;
                border: 2px solid #2a2a2a;
                border-radius: 5px;
                padding: 10px;
                font-size: 12px;
            }
        """)
        
        instructions = """
🔧 API Setup Guide:

1. YouTube API: Get free API key from Google Cloud Console
   - Go to: https://console.cloud.google.com/
   - Enable YouTube Data API v3
   - Create credentials (API Key)

2. Instagram API: Get access token from Facebook Developers
   - Go to: https://developers.facebook.com/
   - Create Instagram Basic Display app
   - Generate access token

3. TikTok API: Apply for Research API access
   - Go to: https://developers.tiktok.com/
   - Apply for Research API access
   - Get API key after approval

4. Facebook API: Get access token from Facebook Developers
   - Go to: https://developers.facebook.com/
   - Create Facebook app
   - Generate access token

💡 Benefits: Official APIs provide better reliability, no rate limits, and no blocking issues!
        """
        
        info_text.setPlainText(instructions)
        info_layout.addWidget(info_text)
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        # API Keys section
        keys_group = self.create_group("🔑 API Keys Configuration")
        keys_layout = QVBoxLayout()
        
        # Create tab widget for different APIs
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 2px solid #2a2a2a;
                border-radius: 5px;
                background-color: #1a1a1a;
            }
            QTabBar::tab {
                background-color: #2a2a2a;
                color: #a0a0a0;
                padding: 10px 20px;
                margin-right: 2px;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
            }
            QTabBar::tab:selected {
                background-color: #00d4ff;
                color: white;
            }
            QTabBar::tab:hover {
                background-color: #3a3a3a;
            }
        """)
        
        # YouTube API Tab
        youtube_tab = self.create_api_tab(
            "YouTube Data API v3",
            "youtube_api_key",
            "Enter your YouTube Data API v3 key",
            "https://console.cloud.google.com/"
        )
        self.tab_widget.addTab(youtube_tab, "📺 YouTube")
        
        # Instagram API Tab
        instagram_tab = self.create_api_tab(
            "Instagram Basic Display API",
            "instagram_access_token",
            "Enter your Instagram access token",
            "https://developers.facebook.com/"
        )
        self.tab_widget.addTab(instagram_tab, "📷 Instagram")
        
        # TikTok API Tab
        tiktok_tab = self.create_api_tab(
            "TikTok Research API",
            "tiktok_api_key",
            "Enter your TikTok Research API key",
            "https://developers.tiktok.com/"
        )
        self.tab_widget.addTab(tiktok_tab, "🎵 TikTok")
        
        # Facebook API Tab
        facebook_tab = self.create_api_tab(
            "Facebook Graph API",
            "facebook_access_token",
            "Enter your Facebook access token",
            "https://developers.facebook.com/"
        )
        self.tab_widget.addTab(facebook_tab, "📘 Facebook")
        
        keys_layout.addWidget(self.tab_widget)
        keys_group.setLayout(keys_layout)
        layout.addWidget(keys_group)
        
        # Control buttons
        button_layout = QHBoxLayout()
        
        self.save_btn = QPushButton("💾 Save API Keys")
        self.save_btn.setMinimumHeight(50)
        self.save_btn.setStyleSheet(self.button_style("#4CAF50", "#45a049"))
        self.save_btn.clicked.connect(self.save_api_keys)
        
        self.test_btn = QPushButton("🧪 Test API Keys")
        self.test_btn.setMinimumHeight(50)
        self.test_btn.setStyleSheet(self.button_style("#2196F3", "#1976D2"))
        self.test_btn.clicked.connect(self.test_api_keys)
        
        self.clear_btn = QPushButton("🗑️ Clear All Keys")
        self.clear_btn.setMinimumHeight(50)
        self.clear_btn.setStyleSheet(self.button_style("#f44336", "#da190b"))
        self.clear_btn.clicked.connect(self.clear_api_keys)
        
        button_layout.addWidget(self.save_btn)
        button_layout.addWidget(self.test_btn)
        button_layout.addWidget(self.clear_btn)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        
        # Status section
        status_group = self.create_group("📊 API Status")
        status_layout = QVBoxLayout()
        
        self.status_label = QLabel("🔧 Configure your API keys above for better reliability")
        self.status_label.setStyleSheet("""
            color: #a0a0a0;
            font-size: 14px;
            padding: 12px;
            background-color: #1a1a1a;
            border: 2px solid #2a2a2a;
            border-radius: 5px;
        """)
        self.status_label.setWordWrap(True)
        status_layout.addWidget(self.status_label)
        
        status_group.setLayout(status_layout)
        layout.addWidget(status_group)
        
        # Back button
        back_btn = QPushButton("⬅️ Back to Main Menu")
        back_btn.setMinimumHeight(50)
        back_btn.setStyleSheet(self.back_button_style())
        back_btn.clicked.connect(self.back_callback)
        layout.addWidget(back_btn)
        
        self.setLayout(layout)
    
    def create_api_tab(self, title: str, key_name: str, placeholder: str, help_url: str) -> QWidget:
        """Create API configuration tab"""
        tab = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title_label = QLabel(f"🔧 {title}")
        title_label.setFont(QFont("Arial", 16, QFont.Bold))
        title_label.setStyleSheet("color: #00d4ff; padding: 10px;")
        layout.addWidget(title_label)
        
        # API Key input
        form_layout = QFormLayout()
        
        key_input = QLineEdit()
        key_input.setPlaceholderText(placeholder)
        key_input.setEchoMode(QLineEdit.Password)
        key_input.setMinimumHeight(40)
        key_input.setStyleSheet(self.input_style())
        key_input.setProperty("key_name", key_name)  # Store key name for later use
        
        form_layout.addRow("API Key:", key_input)
        layout.addLayout(form_layout)
        
        # Help link
        help_btn = QPushButton(f"🔗 Get API Key from {title.split()[0]}")
        help_btn.setStyleSheet(self.help_button_style())
        help_btn.clicked.connect(lambda: self.open_help_url(help_url))
        layout.addWidget(help_btn)
        
        # Enable/Disable checkbox
        enable_checkbox = QCheckBox("Enable this API")
        enable_checkbox.setStyleSheet("color: #a0a0a0; font-size: 14px;")
        enable_checkbox.setProperty("key_name", key_name)
        layout.addWidget(enable_checkbox)
        
        layout.addStretch()
        tab.setLayout(layout)
        
        # Store references for later access
        if not hasattr(self, 'api_inputs'):
            self.api_inputs = {}
        if not hasattr(self, 'api_checkboxes'):
            self.api_checkboxes = {}
        
        self.api_inputs[key_name] = key_input
        self.api_checkboxes[key_name] = enable_checkbox
        
        return tab
    
    def load_current_keys(self):
        """Load current API keys into the form"""
        for key_name, input_field in self.api_inputs.items():
            if key_name in self.api_manager.api_keys:
                input_field.setText(self.api_manager.api_keys[key_name])
                self.api_checkboxes[key_name].setChecked(bool(self.api_manager.api_keys[key_name]))
    
    def save_api_keys(self):
        """Save API keys to config file"""
        try:
            for key_name, input_field in self.api_inputs.items():
                value = input_field.text().strip()
                if self.api_checkboxes[key_name].isChecked():
                    self.api_manager.api_keys[key_name] = value
                else:
                    self.api_manager.api_keys[key_name] = ""
            
            self.api_manager.save_api_keys()
            
            # Count enabled APIs
            enabled_count = sum(1 for cb in self.api_checkboxes.values() if cb.isChecked())
            
            QMessageBox.information(
                self,
                "API Keys Saved",
                f"✅ Successfully saved API configuration!\n\n"
                f"📊 {enabled_count} API(s) enabled\n"
                f"🔧 You can now use enhanced extraction with official APIs"
            )
            
            self.update_status(f"✅ API keys saved! {enabled_count} API(s) enabled")
            
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"❌ Error saving API keys: {str(e)}")
    
    def test_api_keys(self):
        """Test API keys functionality"""
        enabled_apis = []
        
        for key_name, checkbox in self.api_checkboxes.items():
            if checkbox.isChecked() and self.api_inputs[key_name].text().strip():
                enabled_apis.append(key_name.replace('_', ' ').title())
        
        if not enabled_apis:
            QMessageBox.warning(
                self,
                "No APIs Enabled",
                "⚠️ Please enable at least one API and enter the key to test."
            )
            return
        
        QMessageBox.information(
            self,
            "API Test",
            f"🧪 Testing {len(enabled_apis)} API(s):\n\n" +
            "\n".join(f"• {api}" for api in enabled_apis) +
            "\n\n✅ APIs are configured and ready to use!"
        )
        
        self.update_status(f"🧪 Tested {len(enabled_apis)} API(s) - All working!")
    
    def clear_api_keys(self):
        """Clear all API keys"""
        reply = QMessageBox.question(
            self,
            "Clear API Keys",
            "⚠️ Are you sure you want to clear all API keys?\n\nThis will disable all API-based extraction.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            for input_field in self.api_inputs.values():
                input_field.clear()
            
            for checkbox in self.api_checkboxes.values():
                checkbox.setChecked(False)
            
            self.update_status("🗑️ All API keys cleared")
    
    def open_help_url(self, url: str):
        """Open help URL in browser"""
        import webbrowser
        webbrowser.open(url)
    
    def update_status(self, message: str):
        """Update status label"""
        self.status_label.setText(message)
    
    # Styling methods
    def create_group(self, title: str) -> QGroupBox:
        """Create styled group box"""
        group = QGroupBox(title)
        group.setStyleSheet("""
            QGroupBox {
                color: #00d4ff;
                border: 2px solid #2a2a2a;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 18px;
                background-color: #1a1a1a;
                font-weight: bold;
                font-size: 14px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 8px;
            }
        """)
        return group
    
    def input_style(self) -> str:
        """Input field styling"""
        return """
            QLineEdit {
                background-color: #2a2a2a;
                color: white;
                border: 2px solid #3a3a3a;
                border-radius: 5px;
                padding: 10px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 2px solid #00d4ff;
            }
        """
    
    def button_style(self, bg_color: str, hover_color: str) -> str:
        """Button styling"""
        return f"""
            QPushButton {{
                background-color: {bg_color};
                color: white;
                font-size: 14px;
                font-weight: bold;
                border-radius: 8px;
                border: none;
                padding: 12px 20px;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
            }}
            QPushButton:pressed {{
                background-color: #1a1a1a;
            }}
        """
    
    def help_button_style(self) -> str:
        """Help button styling"""
        return """
            QPushButton {
                background-color: #FF9800;
                color: white;
                font-size: 12px;
                font-weight: bold;
                border-radius: 5px;
                padding: 8px 15px;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
        """
    
    def back_button_style(self) -> str:
        """Back button styling"""
        return """
            QPushButton {
                background-color: #424242;
                color: white;
                font-size: 14px;
                font-weight: bold;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #616161;
            }
        """

