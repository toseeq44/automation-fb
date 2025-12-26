"""
modules/video_editor/apply_preset_dialog.py
Apply Preset Dialog - Single mode video selection and processing
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFileDialog, QGroupBox, QFormLayout, QProgressBar,
    QTextEdit, QMessageBox, QComboBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont

import os
from typing import Optional, Dict, Any

from modules.logging.logger import get_logger
from modules.video_editor.preset_manager import EditingPreset, PresetManager

logger = get_logger(__name__)


class ApplyPresetWorker(QThread):
    """Worker thread for applying preset to video(s)"""

    progress = pyqtSignal(str)  # Progress message
    finished = pyqtSignal(bool, str)  # Success, message

    def __init__(self, preset: EditingPreset, primary_video: str,
                 output_path: str, secondary_video: str = None):
        super().__init__()
        self.preset = preset
        self.primary_video = primary_video
        self.secondary_video = secondary_video
        self.output_path = output_path

    def run(self):
        """Process video with preset"""
        try:
            self.progress.emit(f"Loading preset: {self.preset.name}")

            preset_manager = PresetManager()

            # Check if this is dual video preset
            is_dual_video = any(
                op['operation'] == 'dual_video_merge'
                for op in self.preset.operations
            )

            if is_dual_video and self.secondary_video:
                # Update preset with secondary video path
                for op in self.preset.operations:
                    if op['operation'] == 'dual_video_merge':
                        op['params']['secondary_video_path'] = self.secondary_video
                        break

            # Apply preset
            success = preset_manager.apply_preset_to_video(
                preset=self.preset,
                video_path=self.primary_video,
                output_path=self.output_path,
                quality='high',
                progress_callback=lambda msg: self.progress.emit(msg)
            )

            if success:
                self.finished.emit(True, f"✅ Video processed successfully!\n\nSaved to: {self.output_path}")
            else:
                self.finished.emit(False, "❌ Failed to process video. Check logs for details.")

        except Exception as e:
            logger.error(f"Error processing video: {e}", exc_info=True)
            self.finished.emit(False, f"❌ Error: {str(e)}")


class ApplyPresetDialog(QDialog):
    """
    Dialog for applying preset to single video(s)
    Supports both normal presets (1 video) and Dual Video preset (2 videos)
    """

    def __init__(self, preset_name: str, folder: str, parent=None):
        super().__init__(parent)

        self.preset_name = preset_name
        self.folder = folder
        self.preset = None
        self.worker = None

        # Load preset
        preset_manager = PresetManager()
        self.preset = preset_manager.load_preset_from_folder(preset_name, folder)

        if not self.preset:
            QMessageBox.critical(self, "Error", f"Failed to load preset: {preset_name}")
            self.reject()
            return

        # Check if this is dual video preset
        self.is_dual_video = any(
            op['operation'] == 'dual_video_merge'
            for op in self.preset.operations
        )

        self.setup_ui()

    def setup_ui(self):
        """Setup the user interface"""
        self.setWindowTitle(f"Apply Preset - {self.preset_name}")
        self.setMinimumSize(600, 400)

        main_layout = QVBoxLayout()

        # ========== TITLE ==========
        title_label = QLabel(f"Apply Preset: {self.preset_name}")
        title_label.setFont(QFont("Arial", 14, QFont.Bold))
        main_layout.addWidget(title_label)

        # ========== PRESET INFO ==========
        info_group = QGroupBox("Preset Information")
        info_layout = QFormLayout()

        info_layout.addRow("Name:", QLabel(self.preset.name))
        info_layout.addRow("Description:", QLabel(self.preset.description))
        info_layout.addRow("Category:", QLabel(self.preset.category))
        info_layout.addRow("Operations:", QLabel(str(len(self.preset.operations))))

        info_group.setLayout(info_layout)
        main_layout.addWidget(info_group)

        # ========== VIDEO SELECTION ==========
        video_group = QGroupBox("Video Selection")
        video_layout = QVBoxLayout()

        # Primary video
        primary_layout = QHBoxLayout()
        primary_label = QLabel("Primary Video:" if self.is_dual_video else "Input Video:")
        primary_label.setMinimumWidth(120)
        primary_layout.addWidget(primary_label)

        self.primary_path_edit = QLineEdit()
        self.primary_path_edit.setPlaceholderText("Select video file...")
        self.primary_path_edit.setReadOnly(True)
        primary_layout.addWidget(self.primary_path_edit)

        self.primary_browse_btn = QPushButton("Browse...")
        self.primary_browse_btn.clicked.connect(self.browse_primary_video)
        primary_layout.addWidget(self.primary_browse_btn)

        video_layout.addLayout(primary_layout)

        # Secondary video (only for dual video preset)
        if self.is_dual_video:
            secondary_layout = QHBoxLayout()
            secondary_label = QLabel("Secondary Video:")
            secondary_label.setMinimumWidth(120)
            secondary_layout.addWidget(secondary_label)

            self.secondary_path_edit = QLineEdit()
            self.secondary_path_edit.setPlaceholderText("Select secondary video file...")
            self.secondary_path_edit.setReadOnly(True)
            secondary_layout.addWidget(self.secondary_path_edit)

            self.secondary_browse_btn = QPushButton("Browse...")
            self.secondary_browse_btn.clicked.connect(self.browse_secondary_video)
            secondary_layout.addWidget(self.secondary_browse_btn)

            video_layout.addLayout(secondary_layout)

        # Output path
        output_layout = QHBoxLayout()
        output_label = QLabel("Output Path:")
        output_label.setMinimumWidth(120)
        output_layout.addWidget(output_label)

        self.output_path_edit = QLineEdit()
        self.output_path_edit.setPlaceholderText("Select output location...")
        self.output_path_edit.setReadOnly(True)
        output_layout.addWidget(self.output_path_edit)

        self.output_browse_btn = QPushButton("Browse...")
        self.output_browse_btn.clicked.connect(self.browse_output_path)
        output_layout.addWidget(self.output_browse_btn)

        video_layout.addLayout(output_layout)

        video_group.setLayout(video_layout)
        main_layout.addWidget(video_group)

        # ========== PROGRESS ==========
        progress_group = QGroupBox("Progress")
        progress_layout = QVBoxLayout()

        self.progress_text = QTextEdit()
        self.progress_text.setReadOnly(True)
        self.progress_text.setMaximumHeight(100)
        self.progress_text.setText("Ready to process...")
        progress_layout.addWidget(self.progress_text)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.progress_bar.setVisible(False)
        progress_layout.addWidget(self.progress_bar)

        progress_group.setLayout(progress_layout)
        main_layout.addWidget(progress_group)

        # ========== ACTION BUTTONS ==========
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.apply_btn = QPushButton("✓ Apply Preset")
        self.apply_btn.clicked.connect(self.apply_preset)
        self.apply_btn.setEnabled(False)
        button_layout.addWidget(self.apply_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)

        main_layout.addLayout(button_layout)

        self.setLayout(main_layout)

    def browse_primary_video(self):
        """Browse for primary/input video"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Primary Video" if self.is_dual_video else "Select Video",
            "",
            "Video Files (*.mp4 *.avi *.mov *.mkv *.flv *.wmv);;All Files (*)"
        )

        if file_path:
            self.primary_path_edit.setText(file_path)

            # Auto-suggest output path
            if not self.output_path_edit.text():
                base_name = os.path.splitext(os.path.basename(file_path))[0]
                ext = os.path.splitext(file_path)[1]
                output_dir = os.path.dirname(file_path)
                output_path = os.path.join(output_dir, f"{base_name}_edited{ext}")
                self.output_path_edit.setText(output_path)

            self.check_ready()

    def browse_secondary_video(self):
        """Browse for secondary video (dual video preset only)"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Secondary Video",
            "",
            "Video Files (*.mp4 *.avi *.mov *.mkv *.flv *.wmv);;All Files (*)"
        )

        if file_path:
            self.secondary_path_edit.setText(file_path)
            self.check_ready()

    def browse_output_path(self):
        """Browse for output location"""
        primary_path = self.primary_path_edit.text()

        if primary_path:
            base_name = os.path.splitext(os.path.basename(primary_path))[0]
            ext = os.path.splitext(primary_path)[1]
            default_name = f"{base_name}_edited{ext}"
            output_dir = os.path.dirname(primary_path)
        else:
            default_name = "output.mp4"
            output_dir = ""

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Output Video",
            os.path.join(output_dir, default_name),
            "Video Files (*.mp4 *.avi *.mov *.mkv);;All Files (*)"
        )

        if file_path:
            self.output_path_edit.setText(file_path)
            self.check_ready()

    def check_ready(self):
        """Check if all required fields are filled"""
        primary_ok = bool(self.primary_path_edit.text())
        output_ok = bool(self.output_path_edit.text())

        if self.is_dual_video:
            secondary_ok = bool(self.secondary_path_edit.text())
            ready = primary_ok and secondary_ok and output_ok
        else:
            ready = primary_ok and output_ok

        self.apply_btn.setEnabled(ready)

    def apply_preset(self):
        """Apply preset to selected video(s)"""
        primary_video = self.primary_path_edit.text()
        output_path = self.output_path_edit.text()
        secondary_video = self.secondary_path_edit.text() if self.is_dual_video else None

        # Validate inputs
        if not os.path.exists(primary_video):
            QMessageBox.warning(self, "Error", "Primary video file not found!")
            return

        if self.is_dual_video and secondary_video and not os.path.exists(secondary_video):
            QMessageBox.warning(self, "Error", "Secondary video file not found!")
            return

        # Disable buttons during processing
        self.apply_btn.setEnabled(False)
        self.primary_browse_btn.setEnabled(False)
        if self.is_dual_video:
            self.secondary_browse_btn.setEnabled(False)
        self.output_browse_btn.setEnabled(False)

        # Show progress bar
        self.progress_bar.setVisible(True)
        self.progress_text.clear()
        self.progress_text.append("Starting processing...")

        # Create and start worker thread
        self.worker = ApplyPresetWorker(
            preset=self.preset,
            primary_video=primary_video,
            output_path=output_path,
            secondary_video=secondary_video
        )

        self.worker.progress.connect(self.on_progress)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def on_progress(self, message: str):
        """Update progress display"""
        self.progress_text.append(message)
        # Auto-scroll to bottom
        cursor = self.progress_text.textCursor()
        cursor.movePosition(cursor.End)
        self.progress_text.setTextCursor(cursor)

    def on_finished(self, success: bool, message: str):
        """Handle processing completion"""
        self.progress_bar.setVisible(False)

        if success:
            QMessageBox.information(self, "Success", message)
            self.accept()
        else:
            QMessageBox.critical(self, "Error", message)

            # Re-enable buttons
            self.apply_btn.setEnabled(True)
            self.primary_browse_btn.setEnabled(True)
            if self.is_dual_video:
                self.secondary_browse_btn.setEnabled(True)
            self.output_browse_btn.setEnabled(True)
