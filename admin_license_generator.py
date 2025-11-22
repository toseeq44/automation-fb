"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                       ONESOUL PRO - LICENSE GENERATOR                         ║
║                           🔐 ADMIN TOOL (CONFIDENTIAL)                        ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║  WARNING: This tool generates valid license keys.                             ║
║  DO NOT share this file with anyone!                                          ║
║  Keep this file secure and separate from the main application.                ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Usage:
    python admin_license_generator.py

Features:
    - Generate Basic and Pro license keys
    - Hardware ID validation
    - Copy license key to clipboard
    - Track generated licenses (optional)
"""

import sys
import json
from datetime import datetime
from pathlib import Path

# Add modules to path
sys.path.insert(0, str(Path(__file__).parent))

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QSpinBox, QTextEdit,
    QGroupBox, QMessageBox, QFrame, QTableWidget, QTableWidgetItem,
    QHeaderView, QTabWidget
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor

from modules.license.secure_license import SecureLicense, PLAN_CONFIG


class LicenseGeneratorGUI(QMainWindow):
    """Admin tool for generating OneSoul Pro licenses."""

    def __init__(self):
        super().__init__()
        self.license_manager = SecureLicense()
        self.generated_licenses = []
        self.history_file = Path(__file__).parent / "admin_license_history.json"

        self._load_history()
        self._setup_ui()

    def _setup_ui(self):
        """Setup the user interface."""
        self.setWindowTitle("🔐 OneSoul Pro - License Generator (ADMIN)")
        self.setMinimumSize(800, 700)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1a1a2e;
            }
            QWidget {
                color: #eee;
                font-size: 13px;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #4a4a6a;
                border-radius: 8px;
                margin-top: 12px;
                padding: 15px;
                background-color: #16213e;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 10px;
                color: #00d4ff;
            }
            QLabel {
                color: #ccc;
            }
            QLineEdit, QSpinBox, QComboBox {
                background-color: #0f0f23;
                border: 1px solid #4a4a6a;
                border-radius: 5px;
                padding: 8px;
                color: #fff;
            }
            QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
                border: 2px solid #00d4ff;
            }
            QPushButton {
                background-color: #e94560;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ff6b6b;
            }
            QPushButton:pressed {
                background-color: #c73e54;
            }
            QPushButton#generateBtn {
                background-color: #00d4ff;
                color: #000;
                font-size: 15px;
                padding: 12px 30px;
            }
            QPushButton#generateBtn:hover {
                background-color: #33e0ff;
            }
            QPushButton#copyBtn {
                background-color: #4ecca3;
            }
            QPushButton#copyBtn:hover {
                background-color: #6ee6b8;
            }
            QTextEdit {
                background-color: #0f0f23;
                border: 1px solid #4a4a6a;
                border-radius: 5px;
                padding: 10px;
                color: #00ff00;
                font-family: Consolas, monospace;
            }
            QTableWidget {
                background-color: #0f0f23;
                border: 1px solid #4a4a6a;
                border-radius: 5px;
                gridline-color: #4a4a6a;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QHeaderView::section {
                background-color: #16213e;
                color: #00d4ff;
                padding: 8px;
                border: 1px solid #4a4a6a;
                font-weight: bold;
            }
            QTabWidget::pane {
                border: 2px solid #4a4a6a;
                border-radius: 5px;
                background-color: #16213e;
            }
            QTabBar::tab {
                background-color: #0f0f23;
                color: #888;
                padding: 10px 20px;
                border: 1px solid #4a4a6a;
                border-bottom: none;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
            }
            QTabBar::tab:selected {
                background-color: #16213e;
                color: #00d4ff;
            }
        """)

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header
        header = QLabel("🔐 LICENSE GENERATOR - ADMIN ONLY")
        header.setStyleSheet("""
            font-size: 24px;
            font-weight: bold;
            color: #e94560;
            padding: 10px;
        """)
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)

        # Warning
        warning = QLabel("⚠️ Do NOT share this tool! Keep it secure!")
        warning.setStyleSheet("""
            font-size: 12px;
            color: #ff6b6b;
            padding: 5px;
            background-color: #2a1a1a;
            border-radius: 5px;
        """)
        warning.setAlignment(Qt.AlignCenter)
        layout.addWidget(warning)

        # Tabs
        tabs = QTabWidget()
        layout.addWidget(tabs)

        # Tab 1: Generate License
        generate_tab = QWidget()
        tabs.addTab(generate_tab, "🔑 Generate License")
        self._setup_generate_tab(generate_tab)

        # Tab 2: History
        history_tab = QWidget()
        tabs.addTab(history_tab, "📜 History")
        self._setup_history_tab(history_tab)

        # Tab 3: Pricing Info
        pricing_tab = QWidget()
        tabs.addTab(pricing_tab, "💰 Pricing")
        self._setup_pricing_tab(pricing_tab)

    def _setup_generate_tab(self, parent):
        """Setup the license generation tab."""
        layout = QVBoxLayout(parent)
        layout.setSpacing(15)

        # Input Group
        input_group = QGroupBox("License Details")
        input_layout = QVBoxLayout(input_group)

        # Hardware ID
        hw_layout = QHBoxLayout()
        hw_label = QLabel("Hardware ID:")
        hw_label.setFixedWidth(120)
        self.hw_input = QLineEdit()
        self.hw_input.setPlaceholderText("XXXX-XXXX-XXXX-XXXX (from user)")
        hw_layout.addWidget(hw_label)
        hw_layout.addWidget(self.hw_input)
        input_layout.addLayout(hw_layout)

        # Plan
        plan_layout = QHBoxLayout()
        plan_label = QLabel("Plan:")
        plan_label.setFixedWidth(120)
        self.plan_combo = QComboBox()
        self.plan_combo.addItem("Basic - Rs 10,000/month", "basic")
        self.plan_combo.addItem("Pro - Rs 15,000/month", "pro")
        plan_layout.addWidget(plan_label)
        plan_layout.addWidget(self.plan_combo)
        input_layout.addLayout(plan_layout)

        # Duration
        duration_layout = QHBoxLayout()
        duration_label = QLabel("Duration (days):")
        duration_label.setFixedWidth(120)
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(1, 365)
        self.duration_spin.setValue(30)
        duration_layout.addWidget(duration_label)
        duration_layout.addWidget(self.duration_spin)
        input_layout.addLayout(duration_layout)

        # Customer Name (optional)
        name_layout = QHBoxLayout()
        name_label = QLabel("Customer Name:")
        name_label.setFixedWidth(120)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("(Optional - for your records)")
        name_layout.addWidget(name_label)
        name_layout.addWidget(self.name_input)
        input_layout.addLayout(name_layout)

        layout.addWidget(input_group)

        # Generate Button
        self.generate_btn = QPushButton("🔐 GENERATE LICENSE KEY")
        self.generate_btn.setObjectName("generateBtn")
        self.generate_btn.clicked.connect(self._generate_license)
        layout.addWidget(self.generate_btn)

        # Output Group
        output_group = QGroupBox("Generated License Key")
        output_layout = QVBoxLayout(output_group)

        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setMaximumHeight(120)
        self.output_text.setPlaceholderText("License key will appear here...")
        output_layout.addWidget(self.output_text)

        # Copy button
        copy_layout = QHBoxLayout()
        self.copy_btn = QPushButton("📋 Copy to Clipboard")
        self.copy_btn.setObjectName("copyBtn")
        self.copy_btn.clicked.connect(self._copy_to_clipboard)
        self.copy_btn.setEnabled(False)
        copy_layout.addStretch()
        copy_layout.addWidget(self.copy_btn)
        output_layout.addLayout(copy_layout)

        layout.addWidget(output_group)

        # Status
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #4ecca3; padding: 10px;")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)

        layout.addStretch()

    def _setup_history_tab(self, parent):
        """Setup the history tab."""
        layout = QVBoxLayout(parent)

        # Table
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(5)
        self.history_table.setHorizontalHeaderLabels([
            "Date", "Customer", "Plan", "Days", "Hardware ID"
        ])
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.history_table.setAlternatingRowColors(True)
        layout.addWidget(self.history_table)

        # Refresh history
        self._refresh_history_table()

        # Clear button
        btn_layout = QHBoxLayout()
        clear_btn = QPushButton("🗑️ Clear History")
        clear_btn.clicked.connect(self._clear_history)
        btn_layout.addStretch()
        btn_layout.addWidget(clear_btn)
        layout.addLayout(btn_layout)

    def _setup_pricing_tab(self, parent):
        """Setup the pricing info tab."""
        layout = QVBoxLayout(parent)

        pricing_text = """
╔═══════════════════════════════════════════════════════════════════╗
║                      ONESOUL PRO - PRICING                        ║
╠═══════════════════════════════════════════════════════════════════╣
║                                                                   ║
║  📦 BASIC PLAN                                                    ║
║  ─────────────────────────────────────────────────────────────   ║
║  💰 Price:         Rs 10,000 / month                              ║
║  📥 Downloads:     200 per day                                    ║
║  📄 Pages/Upload:  200 per day                                    ║
║  💻 Devices:       1 PC per license                               ║
║  ⏱️ Duration:      30 days                                        ║
║                                                                   ║
╠═══════════════════════════════════════════════════════════════════╣
║                                                                   ║
║  ⭐ PRO PLAN                                                       ║
║  ─────────────────────────────────────────────────────────────   ║
║  💰 Price:         Rs 15,000 / month                              ║
║  📥 Downloads:     UNLIMITED                                      ║
║  📄 Pages/Upload:  UNLIMITED                                      ║
║  💻 Devices:       1 PC per license                               ║
║  ⏱️ Duration:      30 days                                        ║
║                                                                   ║
╠═══════════════════════════════════════════════════════════════════╣
║                                                                   ║
║  📋 LICENSE RULES:                                                ║
║  • 1 license = 1 PC (Hardware bound)                              ║
║  • License cannot be transferred to another PC                    ║
║  • For multiple PCs, customer needs multiple licenses             ║
║  • License expires after the specified duration                   ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝
"""

        info_text = QTextEdit()
        info_text.setReadOnly(True)
        info_text.setStyleSheet("""
            font-family: Consolas, monospace;
            font-size: 12px;
            color: #00d4ff;
        """)
        info_text.setText(pricing_text)
        layout.addWidget(info_text)

    def _generate_license(self):
        """Generate a new license key."""
        # Get inputs
        hardware_id = self.hw_input.text().strip().replace("-", "").upper()
        plan = self.plan_combo.currentData()
        days = self.duration_spin.value()
        customer_name = self.name_input.text().strip() or "Unknown"

        # Validate hardware ID
        if len(hardware_id) != 16:
            QMessageBox.warning(
                self, "Invalid Input",
                "Hardware ID must be 16 characters (with or without dashes).\n\n"
                "Example: A1B2-C3D4-E5F6-G7H8 or A1B2C3D4E5F6G7H8"
            )
            return

        # Get admin key
        admin_key = self.license_manager.get_admin_key()

        # Generate license
        success, result = self.license_manager.generate_license_key(
            hardware_id=hardware_id,
            plan=plan,
            days=days,
            admin_key=admin_key
        )

        if success:
            self.output_text.setText(result)
            self.copy_btn.setEnabled(True)
            self.status_label.setText(f"✅ License generated successfully for {customer_name}!")
            self.status_label.setStyleSheet("color: #4ecca3; padding: 10px;")

            # Save to history
            self._add_to_history(customer_name, plan, days, hardware_id)
        else:
            self.output_text.setText("")
            self.copy_btn.setEnabled(False)
            self.status_label.setText(f"❌ Error: {result}")
            self.status_label.setStyleSheet("color: #ff6b6b; padding: 10px;")

    def _copy_to_clipboard(self):
        """Copy license key to clipboard."""
        license_key = self.output_text.toPlainText()
        if license_key:
            clipboard = QApplication.clipboard()
            clipboard.setText(license_key)
            self.status_label.setText("📋 License key copied to clipboard!")

    def _add_to_history(self, customer, plan, days, hw_id):
        """Add generated license to history."""
        entry = {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "customer": customer,
            "plan": plan.upper(),
            "days": days,
            "hardware_id": f"{hw_id[:4]}-****-****-{hw_id[-4:]}"  # Partially hidden
        }
        self.generated_licenses.insert(0, entry)
        self._save_history()
        self._refresh_history_table()

    def _refresh_history_table(self):
        """Refresh the history table."""
        self.history_table.setRowCount(len(self.generated_licenses))

        for row, entry in enumerate(self.generated_licenses):
            self.history_table.setItem(row, 0, QTableWidgetItem(entry.get("date", "")))
            self.history_table.setItem(row, 1, QTableWidgetItem(entry.get("customer", "")))
            self.history_table.setItem(row, 2, QTableWidgetItem(entry.get("plan", "")))
            self.history_table.setItem(row, 3, QTableWidgetItem(str(entry.get("days", ""))))
            self.history_table.setItem(row, 4, QTableWidgetItem(entry.get("hardware_id", "")))

    def _load_history(self):
        """Load history from file."""
        try:
            if self.history_file.exists():
                self.generated_licenses = json.loads(
                    self.history_file.read_text(encoding="utf-8")
                )
        except:
            self.generated_licenses = []

    def _save_history(self):
        """Save history to file."""
        try:
            self.history_file.write_text(
                json.dumps(self.generated_licenses, indent=2),
                encoding="utf-8"
            )
        except:
            pass

    def _clear_history(self):
        """Clear license history."""
        reply = QMessageBox.question(
            self, "Clear History",
            "Are you sure you want to clear all license history?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.generated_licenses = []
            self._save_history()
            self._refresh_history_table()


def main():
    """Main entry point."""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    window = LicenseGeneratorGUI()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
