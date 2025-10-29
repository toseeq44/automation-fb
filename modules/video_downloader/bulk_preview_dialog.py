"""
Enhanced bulk mode preview dialog.
Shows creator overview with download options.
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QRadioButton, QButtonGroup, QSpinBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QWidget, QGroupBox, QCheckBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from typing import Dict, List
from pathlib import Path


class BulkPreviewDialog(QDialog):
    """Enhanced preview for bulk mode with detailed creator stats"""

    def __init__(self, parent, creator_data: Dict[str, Dict], history_manager=None):
        """
        Args:
            parent: Parent widget
            creator_data: {creator_name: {'links': [...], 'folder': Path, 'links_file': Path}}
            history_manager: Optional HistoryManager instance
        """
        super().__init__(parent)
        self.creator_data = creator_data
        self.history_manager = history_manager
        self.selected_links = []
        self.selected_creators = {}  # {creator: count}

        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("📂 Bulk Download Preview")
        self.setMinimumWidth(700)
        self.setMinimumHeight(600)

        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Dark theme styling
        self.setStyleSheet("""
            QDialog {
                background-color: #23272A;
                color: #F5F6F5;
            }
            QLabel {
                color: #F5F6F5;
            }
            QTableWidget {
                background-color: #2C2F33;
                color: #F5F6F5;
                border: 2px solid #4B5057;
                border-radius: 8px;
                gridline-color: #4B5057;
            }
            QTableWidget::item {
                padding: 8px;
            }
            QTableWidget::item:selected {
                background-color: #1ABC9C;
                color: #F5F6F5;
            }
            QHeaderView::section {
                background-color: #1ABC9C;
                color: #F5F6F5;
                font-weight: bold;
                padding: 8px;
                border: none;
            }
            QPushButton {
                background-color: #1ABC9C;
                color: #F5F6F5;
                border: none;
                padding: 12px 24px;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #16A085;
            }
            QPushButton:pressed {
                background-color: #128C7E;
            }
            QRadioButton {
                color: #F5F6F5;
                font-size: 14px;
                font-weight: bold;
                spacing: 8px;
            }
            QRadioButton::indicator {
                width: 18px;
                height: 18px;
            }
            QSpinBox {
                background-color: #2C2F33;
                color: #F5F6F5;
                border: 2px solid #4B5057;
                padding: 8px;
                border-radius: 8px;
                font-size: 14px;
            }
            QGroupBox {
                color: #1ABC9C;
                border: 2px solid #4B5057;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 15px;
                background-color: #2C2F33;
                font-weight: bold;
                font-size: 14px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 8px;
            }
            QCheckBox {
                color: #F5F6F5;
                font-size: 13px;
                spacing: 8px;
            }
        """)

        # Title
        title = QLabel("📦 Bulk Download - Creator Overview")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: #1ABC9C; margin-bottom: 10px;")
        layout.addWidget(title)

        # Summary stats
        total_creators = len(self.creator_data)
        total_links = sum(len(data['links']) for data in self.creator_data.values())

        summary = QLabel(
            f"Found {total_creators} creator folder(s) with {total_links} total link(s)"
        )
        summary.setStyleSheet("font-size: 14px; color: #F5F6F5; margin-bottom: 10px;")
        layout.addWidget(summary)

        # Creator table
        self.create_creator_table(layout)

        # Download options group
        options_group = QGroupBox("⚙️ Download Options")
        options_layout = QVBoxLayout()

        # Radio buttons for download mode
        self.button_group = QButtonGroup(self)

        self.radio_all = QRadioButton("📥 Download ALL links from each creator")
        self.radio_all.setChecked(True)
        self.button_group.addButton(self.radio_all)
        options_layout.addWidget(self.radio_all)

        # Custom count option
        custom_layout = QHBoxLayout()
        self.radio_custom = QRadioButton("🔢 Download first")
        self.button_group.addButton(self.radio_custom)
        custom_layout.addWidget(self.radio_custom)

        self.custom_spinbox = QSpinBox()
        self.custom_spinbox.setMinimum(1)
        self.custom_spinbox.setMaximum(10000)
        self.custom_spinbox.setValue(5)
        self.custom_spinbox.setSuffix(" links per creator")
        custom_layout.addWidget(self.custom_spinbox)
        custom_layout.addStretch()
        options_layout.addLayout(custom_layout)

        # 24h skip option
        self.skip_recent_checkbox = QCheckBox("⏸️ Skip creators downloaded in last 24 hours")
        if self.history_manager:
            self.skip_recent_checkbox.setChecked(True)
        else:
            self.skip_recent_checkbox.setEnabled(False)
            self.skip_recent_checkbox.setToolTip("History tracking not available")
        options_layout.addWidget(self.skip_recent_checkbox)

        options_group.setLayout(options_layout)
        layout.addWidget(options_group)

        # Preview of what will be downloaded
        preview_label = QLabel("📋 Download Preview:")
        preview_label.setStyleSheet("font-weight: bold; color: #1ABC9C; margin-top: 10px;")
        layout.addWidget(preview_label)

        self.preview_text = QLabel()
        self.preview_text.setStyleSheet(
            "background-color: #2C2F33; padding: 10px; border-radius: 5px; "
            "color: #F5F6F5; font-size: 12px;"
        )
        self.preview_text.setWordWrap(True)
        layout.addWidget(self.preview_text)

        # Update preview when options change
        self.radio_all.toggled.connect(self.update_preview)
        self.radio_custom.toggled.connect(self.update_preview)
        self.custom_spinbox.valueChanged.connect(self.update_preview)
        self.skip_recent_checkbox.toggled.connect(self.update_preview)

        # Initial preview
        self.update_preview()

        # Action buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        start_btn = QPushButton("✅ Start Download")
        start_btn.clicked.connect(self.accept_and_process)

        cancel_btn = QPushButton("❌ Cancel")
        cancel_btn.clicked.connect(self.reject)

        button_layout.addStretch()
        button_layout.addWidget(start_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def create_creator_table(self, parent_layout):
        """Create table showing creator details"""
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels([
            "Creator", "Total Links", "Last Downloaded", "Status"
        ])

        self.table.setRowCount(len(self.creator_data))
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)

        # Populate table
        for row, (creator, data) in enumerate(sorted(self.creator_data.items())):
            # Creator name
            creator_item = QTableWidgetItem(creator)
            creator_item.setFont(QFont("Arial", 12, QFont.Bold))
            self.table.setItem(row, 0, creator_item)

            # Link count
            link_count = len(data['links'])
            count_item = QTableWidgetItem(str(link_count))
            count_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 1, count_item)

            # History info (if available)
            if self.history_manager:
                creator_info = self.history_manager.get_creator_info(creator)

                # Last download time
                last_download = creator_info.get('last_download', 'Never')
                if last_download and last_download != 'Never':
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(last_download)
                        last_download = dt.strftime('%Y-%m-%d %H:%M')
                    except Exception:
                        pass

                last_item = QTableWidgetItem(last_download)
                last_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, 2, last_item)

                # Status
                total_downloaded = creator_info.get('total_downloaded', 0)
                last_status = creator_info.get('last_status', 'never')

                status_text = f"{last_status}"
                if total_downloaded > 0:
                    status_text = f"✅ {total_downloaded} videos"

                status_item = QTableWidgetItem(status_text)
                status_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, 3, status_item)
            else:
                self.table.setItem(row, 2, QTableWidgetItem("N/A"))
                self.table.setItem(row, 3, QTableWidgetItem("N/A"))

        # Resize columns to content
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)

        parent_layout.addWidget(self.table)

    def update_preview(self):
        """Update preview text based on current selections"""
        skip_recent = self.skip_recent_checkbox.isChecked() and self.history_manager

        creators_to_process = []
        total_links_to_download = 0

        for creator, data in self.creator_data.items():
            # Check if should skip
            if skip_recent and self.history_manager.should_skip_creator(creator):
                continue

            links = data['links']

            if self.radio_all.isChecked():
                count = len(links)
            else:
                count = min(self.custom_spinbox.value(), len(links))

            if count > 0:
                creators_to_process.append((creator, count))
                total_links_to_download += count

        # Format preview
        if not creators_to_process:
            preview = "⚠️ No creators to process (all recently downloaded or no links)"
        else:
            preview = f"Will download {total_links_to_download} video(s) from {len(creators_to_process)} creator(s):\n\n"
            for creator, count in creators_to_process[:10]:  # Show first 10
                preview += f"  • {creator}: {count} link(s)\n"

            if len(creators_to_process) > 10:
                preview += f"  ... and {len(creators_to_process) - 10} more"

        self.preview_text.setText(preview)

    def accept_and_process(self):
        """Process selections and prepare download data"""
        skip_recent = self.skip_recent_checkbox.isChecked() and self.history_manager

        self.selected_links = []
        self.selected_creators = {}

        for creator, data in self.creator_data.items():
            # Skip if recently downloaded
            if skip_recent and self.history_manager.should_skip_creator(creator):
                continue

            links = data['links']

            # Determine how many to download
            if self.radio_all.isChecked():
                count = len(links)
            else:
                count = min(self.custom_spinbox.value(), len(links))

            if count > 0:
                selected = links[:count]
                self.selected_links.extend(selected)
                self.selected_creators[creator] = {
                    'count': count,
                    'links': selected,
                    'folder': data['folder'],
                    'links_file': data['links_file']
                }

        if not self.selected_links:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                "Nothing to Download",
                "No links selected. Check your filters or 24h skip setting."
            )
            return

        self.accept()

    def get_selected_links(self) -> List[str]:
        """Return flat list of selected links"""
        return self.selected_links

    def get_selected_creators(self) -> Dict:
        """Return detailed creator selection data"""
        return self.selected_creators
