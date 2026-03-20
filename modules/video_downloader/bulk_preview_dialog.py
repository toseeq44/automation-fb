"""
Enhanced bulk mode preview dialog.
Shows creator overview with download options.
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QRadioButton, QButtonGroup, QSpinBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QWidget, QGroupBox, QCheckBox, QScrollArea
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
        self.setMinimumWidth(800)
        self.setMinimumHeight(700)
        # Make window resizable
        self.resize(900, 750)

        # Main layout for dialog
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Scrollable area for content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.NoFrame)

        # Content widget inside scroll area
        content_widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        content_widget.setLayout(layout)

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
            QScrollArea {
                border: none;
                background-color: #23272A;
            }
            QScrollBar:vertical {
                background-color: #2C2F33;
                width: 12px;
                border-radius: 6px;
                margin: 2px;
            }
            QScrollBar::handle:vertical {
                background-color: #4B5057;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #1ABC9C;
            }
            QScrollBar::handle:vertical:pressed {
                background-color: #16A085;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
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
        skip_count = sum(1 for data in self.creator_data.values() if data.get('will_skip_24h', False))

        summary_text = f"Found {total_creators} creator folder(s) with {total_links} total link(s)"
        if skip_count > 0:
            summary_text += f"\n🔴 {skip_count} creator(s) marked for skip (downloaded in last 24h)"

        summary = QLabel(summary_text)
        summary.setStyleSheet("font-size: 14px; color: #F5F6F5; margin-bottom: 10px;")
        layout.addWidget(summary)

        # Legend
        legend = QLabel("🔴 Red = Will skip (24h window) | ⏸️ = Recently downloaded")
        legend.setStyleSheet("font-size: 12px; color: #95A5A6; margin-bottom: 5px; font-style: italic;")
        layout.addWidget(legend)

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
        self.skip_recent_checkbox = QCheckBox("⏸️ Skip creators downloaded in last 24 hours (RECOMMENDED)")
        if self.history_manager:
            self.skip_recent_checkbox.setChecked(True)  # Checked by default!
            skip_count = sum(1 for data in self.creator_data.values() if data.get('will_skip_24h', False))
            if skip_count > 0:
                tooltip = f"Currently {skip_count} creator(s) will be skipped. Uncheck to re-download them."
            else:
                tooltip = "No recently downloaded creators found. All will be processed."
            self.skip_recent_checkbox.setToolTip(tooltip)
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

        # Set scroll area content and add to main layout
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)

        self.setLayout(main_layout)

    def create_creator_table(self, parent_layout):
        """Create table showing creator details with skip indicators"""
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels([
            "Creator", "Total Links", "Last Downloaded", "Status"
        ])

        self.table.setRowCount(len(self.creator_data))
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)

        # Make table scrollable with max height
        self.table.setMinimumHeight(200)
        self.table.setMaximumHeight(350)

        # Populate table
        for row, (creator, data) in enumerate(sorted(self.creator_data.items())):
            will_skip = data.get('will_skip_24h', False)

            # Creator name with skip indicator
            creator_text = creator
            if will_skip:
                creator_text = f"⏸️ {creator} [WILL SKIP]"

            creator_item = QTableWidgetItem(creator_text)
            creator_font = QFont("Arial", 12, QFont.Bold)
            creator_item.setFont(creator_font)

            # Color code skipped creators
            if will_skip:
                from PyQt5.QtGui import QColor
                creator_item.setForeground(QColor("#E74C3C"))  # Red for skipped

            self.table.setItem(row, 0, creator_item)

            # Link count
            link_count = len(data['links'])
            count_item = QTableWidgetItem(str(link_count))
            count_item.setTextAlignment(Qt.AlignCenter)
            if will_skip:
                from PyQt5.QtGui import QColor
                count_item.setForeground(QColor("#E74C3C"))
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
                if will_skip:
                    from PyQt5.QtGui import QColor
                    last_item.setForeground(QColor("#E74C3C"))
                self.table.setItem(row, 2, last_item)

                # Status
                total_downloaded = creator_info.get('total_downloaded', 0)
                last_status = creator_info.get('last_status', 'never')

                if will_skip:
                    status_text = "⏸️ SKIP (24h)"
                else:
                    status_text = f"{last_status}"
                    if total_downloaded > 0:
                        status_text = f"✅ {total_downloaded} videos"

                status_item = QTableWidgetItem(status_text)
                status_item.setTextAlignment(Qt.AlignCenter)
                if will_skip:
                    from PyQt5.QtGui import QColor
                    status_item.setForeground(QColor("#E74C3C"))
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
        skipped_count = 0
        total_links_to_download = 0

        for creator, data in self.creator_data.items():
            # Check if should skip (use pre-computed flag or checkbox)
            should_skip = False
            if skip_recent:
                # Use the will_skip_24h flag that was computed at scan time
                should_skip = data.get('will_skip_24h', False)

            if should_skip:
                skipped_count += 1
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
            preview = "⚠️ No creators to process\n\n"
            if skipped_count > 0:
                preview += f"All {skipped_count} creator(s) were downloaded in last 24 hours.\n"
                preview += "Uncheck '24h skip' option to re-download them."
            else:
                preview += "No links available."
        else:
            preview = f"📥 Will download {total_links_to_download} video(s) from {len(creators_to_process)} creator(s)\n\n"

            if skipped_count > 0:
                preview += f"⏸️ Skipping {skipped_count} recently downloaded creator(s)\n\n"

            preview += "Details:\n"
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
            # Skip if recently downloaded (use pre-computed flag)
            if skip_recent and data.get('will_skip_24h', False):
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
