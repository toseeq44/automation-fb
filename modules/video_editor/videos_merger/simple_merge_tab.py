"""
modules/video_editor/videos_merger/simple_merge_tab.py
Simple merge tab UI - Merge multiple videos with settings
"""

from typing import List, Optional
from pathlib import Path
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFileDialog, QScrollArea, QGroupBox, QSpinBox, QDoubleSpinBox,
    QComboBox, QCheckBox, QLineEdit, QMessageBox, QFrame
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
from .video_clip_widget import VideoClipWidget
from .merge_engine import MergeSettings
from .merge_processor import SimpleMergeProcessor
from .utils import get_default_output_folder, generate_output_filename, format_duration
from modules.logging.logger import get_logger

logger = get_logger(__name__)


class SimpleMergeTab(QWidget):
    """Tab for simple video merging"""

    # Signals
    merge_started = pyqtSignal(object)  # Emits processor
    merge_completed = pyqtSignal(bool, dict)  # (success, results)

    def __init__(self):
        super().__init__()

        # Data
        self.video_widgets: List[VideoClipWidget] = []
        self.processor: Optional[SimpleMergeProcessor] = None

        self.init_ui()

    def init_ui(self):
        """Initialize UI"""
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        # Top buttons
        button_layout = QHBoxLayout()

        add_btn = QPushButton("➕ Add Videos")
        add_btn.setFixedHeight(35)
        add_btn.setStyleSheet("""
            QPushButton {
                background-color: #0066cc;
                color: white;
                font-weight: bold;
                font-size: 10pt;
            }
            QPushButton:hover {
                background-color: #0052a3;
            }
        """)
        add_btn.clicked.connect(self.add_videos)
        button_layout.addWidget(add_btn)

        clear_btn = QPushButton("🗑️ Clear All")
        clear_btn.setFixedHeight(35)
        clear_btn.clicked.connect(self.clear_all)
        button_layout.addWidget(clear_btn)

        button_layout.addStretch()
        main_layout.addLayout(button_layout)

        # Video list scroll area
        self.video_list_widget = QWidget()
        self.video_list_layout = QVBoxLayout()
        self.video_list_layout.setSpacing(8)
        self.video_list_widget.setLayout(self.video_list_layout)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.video_list_widget)
        scroll.setMinimumHeight(200)
        main_layout.addWidget(scroll, 1)

        # Empty state label
        self.empty_label = QLabel("No videos added. Click 'Add Videos' to get started.")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet("color: #888; font-size: 11pt; padding: 40px;")
        self.video_list_layout.addWidget(self.empty_label)

        # Settings sections
        settings_layout = QHBoxLayout()

        # Left column - Trim and Transform
        left_column = QVBoxLayout()
        left_column.addWidget(self._create_trim_settings())
        left_column.addWidget(self._create_transform_settings())
        settings_layout.addLayout(left_column, 1)

        # Right column - Transition and Output
        right_column = QVBoxLayout()
        right_column.addWidget(self._create_transition_settings())
        right_column.addWidget(self._create_output_settings())
        settings_layout.addLayout(right_column, 1)

        main_layout.addLayout(settings_layout)

        # Summary row
        summary_layout = QHBoxLayout()
        self.summary_label = QLabel("📊 Total Duration: 00:00  |  Videos: 0")
        self.summary_label.setStyleSheet("font-size: 10pt; font-weight: bold; color: #0066cc;")
        summary_layout.addWidget(self.summary_label)
        summary_layout.addStretch()
        main_layout.addLayout(summary_layout)

        # Start merge button
        self.start_btn = QPushButton("▶️ Start Merging")
        self.start_btn.setFixedHeight(45)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                font-weight: bold;
                font-size: 12pt;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        self.start_btn.clicked.connect(self.start_merge)
        self.start_btn.setEnabled(False)
        main_layout.addWidget(self.start_btn)

        self.setLayout(main_layout)

    def _create_trim_settings(self) -> QGroupBox:
        """Create trim settings group"""
        group = QGroupBox("✂️ Bulk Trim Settings")
        group.setFont(QFont("Arial", 10, QFont.Bold))
        layout = QVBoxLayout()

        # Trim start
        start_layout = QHBoxLayout()
        start_layout.addWidget(QLabel("Trim Start:"))
        self.trim_start_spin = QSpinBox()
        self.trim_start_spin.setRange(0, 300)
        self.trim_start_spin.setValue(0)
        self.trim_start_spin.setSuffix(" sec")
        self.trim_start_spin.setToolTip("Seconds to trim from start of each video")
        self.trim_start_spin.valueChanged.connect(self._update_trimmed_durations)
        start_layout.addWidget(self.trim_start_spin, 1)
        layout.addLayout(start_layout)

        # Trim end
        end_layout = QHBoxLayout()
        end_layout.addWidget(QLabel("Trim End:"))
        self.trim_end_spin = QSpinBox()
        self.trim_end_spin.setRange(0, 300)
        self.trim_end_spin.setValue(0)
        self.trim_end_spin.setSuffix(" sec")
        self.trim_end_spin.setToolTip("Seconds to trim from end of each video")
        self.trim_end_spin.valueChanged.connect(self._update_trimmed_durations)
        end_layout.addWidget(self.trim_end_spin, 1)
        layout.addLayout(end_layout)

        # Apply button
        apply_btn = QPushButton("Apply to All Videos")
        apply_btn.clicked.connect(self._update_trimmed_durations)
        layout.addWidget(apply_btn)

        group.setLayout(layout)
        return group
    def _create_transform_settings(self) -> QGroupBox:
        """Create transform settings (crop, zoom, flip)"""
        group = QGroupBox("🔧 Transform Settings")
        group.setFont(QFont("Arial", 10, QFont.Bold))
        layout = QVBoxLayout()

        # Crop
        crop_layout = QHBoxLayout()
        self.crop_check = QCheckBox("Crop to:")
        self.crop_check.toggled.connect(lambda checked: self.crop_combo.setEnabled(checked))
        crop_layout.addWidget(self.crop_check)

        self.crop_combo = QComboBox()
        self.crop_combo.addItems(['9:16 (TikTok)', '16:9 (YouTube)', '1:1 (Square)',
                                   '4:3 (Classic)', '4:5 (Instagram)', '21:9 (Ultrawide)'])
        self.crop_combo.setEnabled(False)
        crop_layout.addWidget(self.crop_combo, 1)
        layout.addLayout(crop_layout)

        # Zoom
        zoom_layout = QHBoxLayout()
        self.zoom_check = QCheckBox("Zoom:")
        self.zoom_check.toggled.connect(lambda checked: self.zoom_spin.setEnabled(checked))
        zoom_layout.addWidget(self.zoom_check)

        self.zoom_spin = QDoubleSpinBox()
        self.zoom_spin.setRange(0.1, 5.0)
        self.zoom_spin.setSingleStep(0.1)
        self.zoom_spin.setValue(1.1)
        self.zoom_spin.setSuffix("x")
        self.zoom_spin.setToolTip("1.0 = no zoom, 1.1 = 110%")
        self.zoom_spin.setEnabled(False)
        zoom_layout.addWidget(self.zoom_spin, 1)
        layout.addLayout(zoom_layout)

        # Flip horizontal
        self.flip_h_check = QCheckBox("Flip Horizontal (Mirror)")
        self.flip_h_check.setToolTip("Mirror video left-right")
        layout.addWidget(self.flip_h_check)

        # Flip vertical
        self.flip_v_check = QCheckBox("Flip Vertical")
        self.flip_v_check.setToolTip("Flip video upside down")
        layout.addWidget(self.flip_v_check)

        group.setLayout(layout)
        return group

    def _create_transition_settings(self) -> QGroupBox:
        """Create transition settings"""
        group = QGroupBox("🔁 Transition Settings")
        group.setFont(QFont("Arial", 10, QFont.Bold))
        layout = QVBoxLayout()

        # Transition type
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Default Transition:"))

        self.transition_combo = QComboBox()
        self.transition_combo.addItems(['Crossfade', 'Fade', 'Slide Left', 'Slide Right',
                                        'Slide Up', 'Slide Down', 'Zoom In', 'Zoom Out',
                                        'Wipe', 'None'])
        type_layout.addWidget(self.transition_combo, 1)
        layout.addLayout(type_layout)

        # Duration
        duration_layout = QHBoxLayout()
        duration_layout.addWidget(QLabel("Duration:"))

        self.transition_duration_spin = QDoubleSpinBox()
        self.transition_duration_spin.setRange(0.1, 5.0)
        self.transition_duration_spin.setSingleStep(0.1)
        self.transition_duration_spin.setValue(1.0)
        self.transition_duration_spin.setSuffix(" sec")
        duration_layout.addWidget(self.transition_duration_spin, 1)
        layout.addLayout(duration_layout)

        # Apply to all button
        apply_btn = QPushButton("Apply Same Transition to All")
        apply_btn.clicked.connect(self._apply_transition_to_all)
        layout.addWidget(apply_btn)

        group.setLayout(layout)
        return group

    def _create_output_settings(self) -> QGroupBox:
        """Create output settings"""
        group = QGroupBox("💾 Output Settings")
        group.setFont(QFont("Arial", 10, QFont.Bold))
        layout = QVBoxLayout()

        # Output folder
        folder_layout = QHBoxLayout()
        folder_layout.addWidget(QLabel("📂 Output:"))

        self.output_folder_edit = QLineEdit()
        self.output_folder_edit.setText(get_default_output_folder())
        self.output_folder_edit.setReadOnly(True)
        folder_layout.addWidget(self.output_folder_edit, 1)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_output_folder)
        folder_layout.addWidget(browse_btn)
        layout.addLayout(folder_layout)

        # Filename
        filename_layout = QHBoxLayout()
        filename_layout.addWidget(QLabel("📝 Filename:"))

        self.filename_edit = QLineEdit()
        self.filename_edit.setText(generate_output_filename())
        filename_layout.addWidget(self.filename_edit, 1)
        layout.addLayout(filename_layout)

        # Quality and format row
        quality_layout = QHBoxLayout()

        quality_layout.addWidget(QLabel("Quality:"))
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(['Low', 'Medium', 'High', 'Ultra'])
        self.quality_combo.setCurrentIndex(2)  # Default: High
        quality_layout.addWidget(self.quality_combo, 1)

        quality_layout.addWidget(QLabel("Format:"))
        self.format_combo = QComboBox()
        self.format_combo.addItems(['MP4', 'MOV', 'AVI'])
        quality_layout.addWidget(self.format_combo, 1)

        layout.addLayout(quality_layout)

        # Audio settings
        audio_layout = QHBoxLayout()
        self.keep_audio_check = QCheckBox("Keep Audio")
        self.keep_audio_check.setChecked(True)
        audio_layout.addWidget(self.keep_audio_check)

        self.fade_audio_check = QCheckBox("Fade Audio Between Clips")
        audio_layout.addWidget(self.fade_audio_check)
        layout.addLayout(audio_layout)

        # Delete source
        self.delete_source_check = QCheckBox("🗑️ Delete source videos after successful merge")
        self.delete_source_check.setStyleSheet("font-weight: bold; color: #dc3545;")
        layout.addWidget(self.delete_source_check)

        group.setLayout(layout)
        return group
    def add_videos(self):
        """Add videos to merge list"""
        file_dialog = QFileDialog()
        file_paths, _ = file_dialog.getOpenFileNames(
            self,
            "Select Videos to Merge",
            "",
            "Video Files (*.mp4 *.avi *.mov *.mkv *.flv *.wmv *.m4v *.webm);;All Files (*.*)"
        )

        if file_paths:
            # Hide empty label
            self.empty_label.setVisible(False)

            for path in file_paths:
                self._add_video_widget(path)

            self._update_summary()
            self._check_can_merge()
            logger.info(f"Added {len(file_paths)} videos")

    def _add_video_widget(self, video_path: str):
        """Add video widget to list"""
        index = len(self.video_widgets)
        widget = VideoClipWidget(video_path, index, show_transition=True)

        # Connect signals
        widget.remove_clicked.connect(self._remove_video)
        widget.move_up_clicked.connect(self._move_video_up)
        widget.move_down_clicked.connect(self._move_video_down)

        self.video_widgets.append(widget)
        self.video_list_layout.addWidget(widget)

    def _remove_video(self, widget: VideoClipWidget):
        """Remove video from list"""
        if widget in self.video_widgets:
            self.video_widgets.remove(widget)
            self.video_list_layout.removeWidget(widget)
            widget.deleteLater()

            # Update indices
            for i, w in enumerate(self.video_widgets):
                w.set_index(i)

            self._update_summary()
            self._check_can_merge()

            # Show empty label if no videos
            if not self.video_widgets:
                self.empty_label.setVisible(True)

    def _move_video_up(self, widget: VideoClipWidget):
        """Move video up in list"""
        index = self.video_widgets.index(widget)
        if index > 0:
            # Swap in list
            self.video_widgets[index], self.video_widgets[index - 1] = \
                self.video_widgets[index - 1], self.video_widgets[index]

            # Swap in layout
            self.video_list_layout.removeWidget(widget)
            self.video_list_layout.insertWidget(index - 1, widget)

            # Update indices
            self.video_widgets[index].set_index(index)
            self.video_widgets[index - 1].set_index(index - 1)

    def _move_video_down(self, widget: VideoClipWidget):
        """Move video down in list"""
        index = self.video_widgets.index(widget)
        if index < len(self.video_widgets) - 1:
            # Swap in list
            self.video_widgets[index], self.video_widgets[index + 1] = \
                self.video_widgets[index + 1], self.video_widgets[index]

            # Swap in layout
            self.video_list_layout.removeWidget(widget)
            self.video_list_layout.insertWidget(index + 1, widget)

            # Update indices
            self.video_widgets[index].set_index(index)
            self.video_widgets[index + 1].set_index(index + 1)

    def clear_all(self):
        """Clear all videos"""
        if self.video_widgets:
            reply = QMessageBox.question(
                self,
                "Clear All",
                "Are you sure you want to remove all videos?",
                QMessageBox.Yes | QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                for widget in self.video_widgets:
                    self.video_list_layout.removeWidget(widget)
                    widget.deleteLater()

                self.video_widgets.clear()
                self.empty_label.setVisible(True)
                self._update_summary()
                self._check_can_merge()

    def _update_trimmed_durations(self):
        """Update trimmed duration for all videos"""
        trim_start = self.trim_start_spin.value()
        trim_end = self.trim_end_spin.value()

        for widget in self.video_widgets:
            widget.update_trimmed_duration(trim_start, trim_end)

        self._update_summary()

    def _apply_transition_to_all(self):
        """Apply transition settings to all videos"""
        transition_map = {
            'Crossfade': 'crossfade',
            'Fade': 'fade',
            'Slide Left': 'slide_left',
            'Slide Right': 'slide_right',
            'Slide Up': 'slide_up',
            'Slide Down': 'slide_down',
            'Zoom In': 'zoom_in',
            'Zoom Out': 'zoom_out',
            'Wipe': 'wipe',
            'None': 'none'
        }

        transition_type = transition_map.get(self.transition_combo.currentText(), 'crossfade')
        duration = self.transition_duration_spin.value()

        for widget in self.video_widgets:
            widget.set_transition(transition_type)
            widget.set_transition_duration(duration)

    def _browse_output_folder(self):
        """Browse for output folder"""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Output Folder",
            self.output_folder_edit.text()
        )

        if folder:
            self.output_folder_edit.setText(folder)

    def _update_summary(self):
        """Update summary label"""
        total_duration = sum(w.get_trimmed_duration() for w in self.video_widgets)
        video_count = len(self.video_widgets)

        self.summary_label.setText(
            f"📊 Total Duration: {format_duration(total_duration)}  |  Videos: {video_count}"
        )

    def _check_can_merge(self):
        """Check if merge can be started"""
        can_merge = len(self.video_widgets) >= 2
        self.start_btn.setEnabled(can_merge)
    def start_merge(self):
        """Start merging process"""
        if len(self.video_widgets) < 2:
            QMessageBox.warning(self, "Cannot Merge", "Need at least 2 videos to merge.")
            return

        # Get video paths
        video_paths = [w.get_video_path() for w in self.video_widgets]

        # Get output path
        output_folder = self.output_folder_edit.text()
        filename = self.filename_edit.text()
        if not filename.endswith('.mp4'):
            filename += '.mp4'
        output_path = str(Path(output_folder) / filename)

        # Check if output file exists
        if Path(output_path).exists():
            reply = QMessageBox.question(
                self,
                "File Exists",
                f"File already exists:\n{output_path}\n\nOverwrite?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return

        # Build settings
        settings = self._build_settings()

        # Create processor
        self.processor = SimpleMergeProcessor(video_paths, output_path, settings)

        # Connect signals
        self.processor.merge_completed.connect(self._on_merge_completed)

        # Disable UI
        self.start_btn.setEnabled(False)
        self.start_btn.setText("⏳ Merging...")

        # Emit signal
        self.merge_started.emit(self.processor)

        # Start processing
        self.processor.start()

        logger.info(f"Started merge: {len(video_paths)} videos → {output_path}")

    def _build_settings(self) -> MergeSettings:
        """Build merge settings from UI"""
        settings = MergeSettings()

        # Trim
        settings.trim_start = self.trim_start_spin.value()
        settings.trim_end = self.trim_end_spin.value()

        # Crop
        settings.crop_enabled = self.crop_check.isChecked()
        if settings.crop_enabled:
            crop_map = {
                '9:16 (TikTok)': '9:16',
                '16:9 (YouTube)': '16:9',
                '1:1 (Square)': '1:1',
                '4:3 (Classic)': '4:3',
                '4:5 (Instagram)': '4:5',
                '21:9 (Ultrawide)': '21:9'
            }
            settings.crop_preset = crop_map.get(self.crop_combo.currentText(), '16:9')

        # Zoom
        settings.zoom_enabled = self.zoom_check.isChecked()
        if settings.zoom_enabled:
            settings.zoom_factor = self.zoom_spin.value()

        # Flip
        settings.flip_horizontal = self.flip_h_check.isChecked()
        settings.flip_vertical = self.flip_v_check.isChecked()

        # Transition
        transition_map = {
            'Crossfade': 'crossfade',
            'Fade': 'fade',
            'Slide Left': 'slide_left',
            'Slide Right': 'slide_right',
            'Slide Up': 'slide_up',
            'Slide Down': 'slide_down',
            'Zoom In': 'zoom_in',
            'Zoom Out': 'zoom_out',
            'Wipe': 'wipe',
            'None': 'none'
        }
        settings.transition_type = transition_map.get(self.transition_combo.currentText(), 'crossfade')
        settings.transition_duration = self.transition_duration_spin.value()

        # Output
        settings.output_quality = self.quality_combo.currentText().lower()
        settings.output_format = self.format_combo.currentText().lower()
        settings.keep_audio = self.keep_audio_check.isChecked()
        settings.fade_audio = self.fade_audio_check.isChecked()

        # Delete source
        settings.delete_source = self.delete_source_check.isChecked()

        return settings

    def _on_merge_completed(self, success: bool, results: dict):
        """Handle merge completion"""
        # Re-enable UI
        self.start_btn.setEnabled(True)
        self.start_btn.setText("▶️ Start Merging")

        # Emit signal
        self.merge_completed.emit(success, results)

        if success:
            output_path = results.get('output_path', '')
            QMessageBox.information(
                self,
                "Merge Complete",
                f"Videos merged successfully!\n\nOutput: {output_path}"
            )
            logger.info(f"Merge completed: {output_path}")
        else:
            error = results.get('error', 'Unknown error')
            QMessageBox.critical(
                self,
                "Merge Failed",
                f"Failed to merge videos:\n{error}"
            )
            logger.error(f"Merge failed: {error}")

    def get_processor(self) -> Optional[SimpleMergeProcessor]:
        """Get current processor"""
        return self.processor

    def reset(self):
        """Reset tab to initial state"""
        self.clear_all()
        self.trim_start_spin.setValue(0)
        self.trim_end_spin.setValue(0)
        self.crop_check.setChecked(False)
        self.zoom_check.setChecked(False)
        self.flip_h_check.setChecked(False)
        self.flip_v_check.setChecked(False)
        self.transition_combo.setCurrentIndex(0)
        self.transition_duration_spin.setValue(1.0)
        self.quality_combo.setCurrentIndex(2)
        self.keep_audio_check.setChecked(True)
        self.fade_audio_check.setChecked(False)
        self.delete_source_check.setChecked(False)
        self.output_folder_edit.setText(get_default_output_folder())
        self.filename_edit.setText(generate_output_filename())
