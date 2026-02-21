"""
modules/video_editor/videos_merger/smart_clip_tab.py
Smart Clip Merge tab UI.
"""

from collections import defaultdict
import json
from pathlib import Path
from typing import Dict, List, Optional

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)

from modules.logging.logger import get_logger
from .smart_clip_processor import SmartClipMergeProcessor
from .utils import (
    format_duration,
    get_default_smart_clip_output_folder,
    get_videos_from_folder,
)

logger = get_logger(__name__)

try:
    from moviepy import VideoFileClip
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False


class SmartClipMergeTab(QWidget):
    """Tab for extracting smart clips and merging them."""

    PRESET_FILE = Path.home() / ".video_merger_smart_clip_presets.json"
    DEFAULT_PRESETS: Dict[str, Dict] = {
        "Balanced": {
            "extract_mode": "Exact Center",
            "global_seconds": 8,
            "format": "MP4",
            "quality": "Match Source",
            "transition": "Crossfade",
            "transition_duration": 1,
            "crop_enabled": False,
            "crop_preset": "9:16",
            "zoom_enabled": False,
            "zoom_percent": 110,
            "mirror_h": False,
            "mirror_v": False,
            "color_enhance": False,
            "brightness": 100,
            "contrast": 100,
            "saturation": 100,
            "blur_sides": False,
            "blur_strength": 6,
            "blur_width_percent": 18,
            "blur_feather_percent": 60,
        },
        "Cinematic": {
            "extract_mode": "Exact Center",
            "global_seconds": 9,
            "format": "MP4",
            "quality": "High",
            "transition": "Fade",
            "transition_duration": 1,
            "crop_enabled": True,
            "crop_preset": "21:9",
            "zoom_enabled": True,
            "zoom_percent": 108,
            "mirror_h": False,
            "mirror_v": False,
            "color_enhance": True,
            "brightness": 98,
            "contrast": 112,
            "saturation": 108,
            "blur_sides": False,
            "blur_strength": 6,
            "blur_width_percent": 18,
            "blur_feather_percent": 60,
        },
        "Vivid": {
            "extract_mode": "Random",
            "global_seconds": 8,
            "format": "MP4",
            "quality": "High",
            "transition": "Zoom In",
            "transition_duration": 1,
            "crop_enabled": False,
            "crop_preset": "9:16",
            "zoom_enabled": False,
            "zoom_percent": 110,
            "mirror_h": False,
            "mirror_v": False,
            "color_enhance": True,
            "brightness": 104,
            "contrast": 114,
            "saturation": 125,
            "blur_sides": False,
            "blur_strength": 6,
            "blur_width_percent": 18,
            "blur_feather_percent": 60,
        },
        "Mirror+Blur": {
            "extract_mode": "Random",
            "global_seconds": 7,
            "format": "MP4",
            "quality": "Medium",
            "transition": "Blur",
            "transition_duration": 1,
            "crop_enabled": False,
            "crop_preset": "9:16",
            "zoom_enabled": False,
            "zoom_percent": 110,
            "mirror_h": True,
            "mirror_v": False,
            "color_enhance": False,
            "brightness": 100,
            "contrast": 100,
            "saturation": 100,
            "blur_sides": True,
            "blur_strength": 8,
            "blur_width_percent": 20,
            "blur_feather_percent": 75,
        },
    }

    merge_started = pyqtSignal(object)
    merge_completed = pyqtSignal(bool, dict)

    def __init__(self):
        super().__init__()
        self.entries: List[Dict] = []
        self.bulk_folder_map: Dict[str, List[Dict]] = {}
        self.processor: Optional[SmartClipMergeProcessor] = None
        self._building_table = False
        self._preset_applying = False
        self.presets: Dict[str, Dict] = {}
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        top_group = QGroupBox("Smart Clip Controls")
        top_layout = QHBoxLayout()

        top_layout.addWidget(QLabel("Mode:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Simple Videos", "Bulk Folders"])
        top_layout.addWidget(self.mode_combo)

        self.select_btn = QPushButton("Select Videos")
        self.select_btn.clicked.connect(self.select_input)
        top_layout.addWidget(self.select_btn)

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(self.clear_all)
        top_layout.addWidget(self.clear_btn)

        top_layout.addSpacing(15)
        top_layout.addWidget(QLabel("Clip Seconds (Global):"))
        self.global_seconds_spin = QSpinBox()
        self.global_seconds_spin.setRange(1, 600)
        self.global_seconds_spin.setValue(8)
        self.global_seconds_spin.setFixedWidth(90)
        top_layout.addWidget(self.global_seconds_spin)

        self.apply_global_btn = QPushButton("Apply to Checked")
        self.apply_global_btn.clicked.connect(self.apply_global_seconds_to_checked)
        top_layout.addWidget(self.apply_global_btn)

        top_layout.addSpacing(10)
        top_layout.addWidget(QLabel("Extract Mode:"))
        self.extract_mode_combo = QComboBox()
        self.extract_mode_combo.addItems(["Exact Center", "Random"])
        top_layout.addWidget(self.extract_mode_combo)

        top_layout.addSpacing(12)
        top_layout.addWidget(QLabel("Preset:"))
        self.preset_combo = QComboBox()
        self.preset_combo.setMinimumWidth(180)
        self.preset_combo.currentTextChanged.connect(self.apply_selected_preset)
        top_layout.addWidget(self.preset_combo)

        self.preset_name_edit = QLineEdit()
        self.preset_name_edit.setPlaceholderText("Custom preset name")
        self.preset_name_edit.setMaximumWidth(180)
        top_layout.addWidget(self.preset_name_edit)

        self.save_preset_btn = QPushButton("Save Preset")
        self.save_preset_btn.clicked.connect(self.save_current_preset)
        top_layout.addWidget(self.save_preset_btn)

        self.export_preset_btn = QPushButton("Export")
        self.export_preset_btn.clicked.connect(self.export_presets)
        top_layout.addWidget(self.export_preset_btn)

        self.import_preset_btn = QPushButton("Import")
        self.import_preset_btn.clicked.connect(self.import_presets)
        top_layout.addWidget(self.import_preset_btn)

        self.delete_preset_btn = QPushButton("Delete Preset")
        self.delete_preset_btn.clicked.connect(self.delete_selected_preset)
        top_layout.addWidget(self.delete_preset_btn)

        top_layout.addStretch()
        top_group.setLayout(top_layout)
        main_layout.addWidget(top_group)

        self.summary_label = QLabel("No input selected.")
        self.summary_label.setStyleSheet("color: #00bcd4; font-weight: bold;")
        main_layout.addWidget(self.summary_label)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Select", "Folder Detail", "Video Length", "Clip Seconds", "Status"])
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.itemChanged.connect(self._on_item_changed)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.setMinimumHeight(260)
        main_layout.addWidget(self.table, 1)

        output_group = QGroupBox("Output")
        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("Save To:"))
        self.output_edit = QLineEdit(get_default_smart_clip_output_folder())
        self.output_edit.setReadOnly(True)
        output_layout.addWidget(self.output_edit, 1)
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self.browse_output)
        output_layout.addWidget(browse_btn)

        output_layout.addSpacing(10)
        output_layout.addWidget(QLabel("Format:"))
        self.format_combo = QComboBox()
        self.format_combo.addItems(["MP4", "MOV", "AVI"])
        output_layout.addWidget(self.format_combo)

        output_layout.addWidget(QLabel("Quality:"))
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["Match Source", "Low", "Medium", "High", "Ultra"])
        self.quality_combo.setCurrentIndex(0)
        output_layout.addWidget(self.quality_combo)

        output_layout.addWidget(QLabel("Transition:"))
        self.transition_combo = QComboBox()
        self.transition_combo.addItems([
            "None", "Crossfade", "Fade",
            "Slide Left", "Slide Right", "Slide Up", "Slide Down",
            "Wipe Left", "Wipe Right", "Wipe Up", "Wipe Down",
            "Zoom In", "Zoom Out",
            "Dissolve (Random)", "Dissolve (Grid)", "Dissolve (Radial)",
            "Rotate", "Blur",
        ])
        output_layout.addWidget(self.transition_combo)

        output_layout.addWidget(QLabel("Duration:"))
        self.transition_duration_spin = QSpinBox()
        self.transition_duration_spin.setRange(1, 5)
        self.transition_duration_spin.setValue(1)
        self.transition_duration_spin.setSuffix("s")
        output_layout.addWidget(self.transition_duration_spin)

        self.delete_source_check = QCheckBox("Delete source after successful merge")
        output_layout.addWidget(self.delete_source_check)
        output_layout.addStretch()
        output_group.setLayout(output_layout)
        main_layout.addWidget(output_group)

        enhance_group = QGroupBox("Extra Editing")
        enhance_layout = QHBoxLayout()

        self.crop_check = QCheckBox("Crop")
        enhance_layout.addWidget(self.crop_check)
        self.crop_combo = QComboBox()
        self.crop_combo.addItems(["9:16", "16:9", "1:1", "4:3", "4:5", "21:9"])
        self.crop_combo.setEnabled(False)
        self.crop_check.toggled.connect(self.crop_combo.setEnabled)
        enhance_layout.addWidget(self.crop_combo)

        self.zoom_check = QCheckBox("Zoom")
        enhance_layout.addWidget(self.zoom_check)
        self.zoom_spin = QSpinBox()
        self.zoom_spin.setRange(100, 300)
        self.zoom_spin.setValue(110)
        self.zoom_spin.setSuffix("%")
        self.zoom_spin.setEnabled(False)
        self.zoom_check.toggled.connect(self.zoom_spin.setEnabled)
        enhance_layout.addWidget(self.zoom_spin)

        self.mirror_h_check = QCheckBox("Mirror H")
        enhance_layout.addWidget(self.mirror_h_check)
        self.mirror_v_check = QCheckBox("Mirror V")
        enhance_layout.addWidget(self.mirror_v_check)

        self.color_enhance_check = QCheckBox("Color Enhance")
        enhance_layout.addWidget(self.color_enhance_check)

        enhance_layout.addWidget(QLabel("B:"))
        self.brightness_spin = QSpinBox()
        self.brightness_spin.setRange(50, 200)
        self.brightness_spin.setValue(100)
        self.brightness_spin.setSuffix("%")
        self.brightness_spin.setEnabled(False)
        enhance_layout.addWidget(self.brightness_spin)

        enhance_layout.addWidget(QLabel("C:"))
        self.contrast_spin = QSpinBox()
        self.contrast_spin.setRange(50, 200)
        self.contrast_spin.setValue(100)
        self.contrast_spin.setSuffix("%")
        self.contrast_spin.setEnabled(False)
        enhance_layout.addWidget(self.contrast_spin)

        enhance_layout.addWidget(QLabel("S:"))
        self.saturation_spin = QSpinBox()
        self.saturation_spin.setRange(50, 200)
        self.saturation_spin.setValue(100)
        self.saturation_spin.setSuffix("%")
        self.saturation_spin.setEnabled(False)
        enhance_layout.addWidget(self.saturation_spin)

        self.color_enhance_check.toggled.connect(self.brightness_spin.setEnabled)
        self.color_enhance_check.toggled.connect(self.contrast_spin.setEnabled)
        self.color_enhance_check.toggled.connect(self.saturation_spin.setEnabled)

        self.blur_sides_check = QCheckBox("Blur Sides")
        enhance_layout.addWidget(self.blur_sides_check)
        enhance_layout.addWidget(QLabel("Strength:"))
        self.blur_strength_spin = QSpinBox()
        self.blur_strength_spin.setRange(1, 20)
        self.blur_strength_spin.setValue(6)
        self.blur_strength_spin.setEnabled(False)
        enhance_layout.addWidget(self.blur_strength_spin)

        enhance_layout.addWidget(QLabel("Width:"))
        self.blur_width_spin = QSpinBox()
        self.blur_width_spin.setRange(5, 40)
        self.blur_width_spin.setValue(18)
        self.blur_width_spin.setSuffix("%")
        self.blur_width_spin.setEnabled(False)
        enhance_layout.addWidget(self.blur_width_spin)

        enhance_layout.addWidget(QLabel("Blend:"))
        self.blur_feather_spin = QSpinBox()
        self.blur_feather_spin.setRange(0, 100)
        self.blur_feather_spin.setValue(60)
        self.blur_feather_spin.setSuffix("%")
        self.blur_feather_spin.setEnabled(False)
        enhance_layout.addWidget(self.blur_feather_spin)

        self.blur_sides_check.toggled.connect(self.blur_strength_spin.setEnabled)
        self.blur_sides_check.toggled.connect(self.blur_width_spin.setEnabled)
        self.blur_sides_check.toggled.connect(self.blur_feather_spin.setEnabled)

        enhance_layout.addStretch()
        enhance_group.setLayout(enhance_layout)
        main_layout.addWidget(enhance_group)

        action_layout = QHBoxLayout()
        action_layout.addStretch()
        self.start_btn = QPushButton("Start Smart Clip Merge")
        self.start_btn.setEnabled(False)
        self.start_btn.clicked.connect(self.start_merge)
        action_layout.addWidget(self.start_btn)
        main_layout.addLayout(action_layout)

        self.setLayout(main_layout)

        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        self._on_mode_changed()
        self._load_presets()

        self.setStyleSheet("""
            QWidget { background-color: #1a1a1a; color: #e0e0e0; }
            QGroupBox {
                background-color: #252525;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
                font-weight: bold;
                color: #00bcd4;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 4px 10px;
            }
            QPushButton {
                background-color: #2a2a2a;
                color: #e0e0e0;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                padding: 6px 10px;
                font-weight: 500;
            }
            QPushButton:hover { border-color: #00bcd4; background-color: #333333; }
            QPushButton:disabled { color: #707070; background-color: #232323; }
            QTableWidget {
                background-color: #1f1f1f;
                border: 1px solid #3a3a3a;
                gridline-color: #303030;
                alternate-background-color: #242424;
            }
            QHeaderView::section {
                background-color: #2a2a2a;
                color: #00e5ff;
                border: 1px solid #303030;
                padding: 6px;
                font-weight: bold;
            }
            QLineEdit, QComboBox, QSpinBox {
                background-color: #1e1e1e;
                color: #e0e0e0;
                border: 1px solid #3a3a3a;
                border-radius: 4px;
                padding: 4px;
                min-height: 22px;
            }
            QComboBox::drop-down { border: none; width: 20px; }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #e0e0e0;
                margin-right: 6px;
            }
            QTableWidget QComboBox, QTableWidget QSpinBox {
                min-height: 18px;
                padding: 1px;
            }
        """)

    def _on_mode_changed(self):
        is_simple = self.mode_combo.currentIndex() == 0
        self.select_btn.setText("Select Videos" if is_simple else "Select Folders")
        self.clear_all()

    def select_input(self):
        if not MOVIEPY_AVAILABLE:
            QMessageBox.critical(self, "Missing Dependency", "MoviePy not installed. Please install moviepy first.")
            return

        if self.mode_combo.currentIndex() == 0:
            file_paths, _ = QFileDialog.getOpenFileNames(
                self,
                "Select Videos",
                "",
                "Video Files (*.mp4 *.avi *.mov *.mkv *.flv *.wmv *.m4v *.webm);;All Files (*.*)",
            )
            if not file_paths:
                return
            self._scan_simple(file_paths)
        else:
            self._scan_bulk()

    def _scan_simple(self, file_paths: List[str]):
        self.entries = []
        self.bulk_folder_map = {}
        for path in file_paths:
            duration = self._read_duration(path)
            if duration <= 0:
                continue
            self.entries.append(
                {
                    "path": path,
                    "folder": str(Path(path).parent),
                    "folder_name": Path(path).parent.name,
                    "duration": duration,
                    "checked": True,
                    "clip_seconds": 0,
                    "status": "Ready",
                }
            )
        self._refresh_table()
        self._update_summary()

    def _scan_bulk(self):
        self.entries = []
        self.bulk_folder_map = {}
        selected_folders: List[str] = []

        while True:
            folder = QFileDialog.getExistingDirectory(
                self,
                "Select Folder with Videos (Cancel to finish)",
            )
            if not folder:
                break
            if folder not in selected_folders:
                selected_folders.append(folder)

            retry = QMessageBox.question(
                self,
                "Add More Folders",
                "Do you want to add another folder?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if retry == QMessageBox.No:
                break

        if not selected_folders:
            return

        for folder in selected_folders:
            video_paths = get_videos_from_folder(folder)
            folder_entries: List[Dict] = []
            for path in video_paths:
                duration = self._read_duration(path)
                if duration <= 0:
                    continue
                entry = {
                    "path": path,
                    "folder": folder,
                    "folder_name": Path(folder).name,
                    "duration": duration,
                    "checked": True,
                    "clip_seconds": 0,
                    "status": "Ready",
                }
                self.entries.append(entry)
                folder_entries.append(entry)
            self.bulk_folder_map[folder] = folder_entries

        self._refresh_table()
        self._update_summary()

    def _read_duration(self, path: str) -> float:
        clip = None
        try:
            clip = VideoFileClip(path)
            return float(clip.duration or 0.0)
        except Exception as e:
            logger.warning(f"Failed to read duration for {path}: {e}")
            return 0.0
        finally:
            if clip:
                try:
                    clip.close()
                except Exception:
                    pass

    def _refresh_table(self):
        self._building_table = True
        self.table.setRowCount(len(self.entries))

        for row, entry in enumerate(self.entries):
            check_item = QTableWidgetItem()
            check_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            check_item.setCheckState(Qt.Checked if entry["checked"] else Qt.Unchecked)
            self.table.setItem(row, 0, check_item)

            detail_text = (
                f"Folder: {entry['folder_name']} | "
                f"File: {Path(entry['path']).name} | "
                f"Root: {entry['folder']}"
            )
            detail_item = QTableWidgetItem(detail_text)
            detail_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(row, 1, detail_item)

            duration_item = QTableWidgetItem(format_duration(entry["duration"]))
            duration_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(row, 2, duration_item)

            clip_spin = QSpinBox()
            clip_spin.setRange(0, 600)
            clip_spin.setSpecialValueText("Auto")
            clip_spin.setValue(int(entry.get("clip_seconds", 0)))
            clip_spin.valueChanged.connect(lambda value, r=row: self._on_clip_seconds_changed(r, value))
            self.table.setCellWidget(row, 3, clip_spin)

            status_item = QTableWidgetItem(entry.get("status", "Ready"))
            status_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(row, 4, status_item)

        self._building_table = False
        self._update_start_state()

    def _on_clip_seconds_changed(self, row: int, value: int):
        if 0 <= row < len(self.entries):
            self.entries[row]["clip_seconds"] = value

    def _on_item_changed(self, item: QTableWidgetItem):
        if self._building_table:
            return
        if item.column() == 0 and 0 <= item.row() < len(self.entries):
            self.entries[item.row()]["checked"] = item.checkState() == Qt.Checked
            self._update_start_state()
            self._update_summary()

    def apply_global_seconds_to_checked(self):
        value = self.global_seconds_spin.value()
        for row, entry in enumerate(self.entries):
            if entry["checked"]:
                entry["clip_seconds"] = value
                widget = self.table.cellWidget(row, 3)
                if widget:
                    widget.setValue(value)

    def _selected_entries(self) -> List[Dict]:
        return [entry for entry in self.entries if entry.get("checked")]

    def _build_batches(self) -> List[List[Dict]]:
        selected = self._selected_entries()
        if self.mode_combo.currentIndex() == 0:
            return [selected] if len(selected) >= 2 else []

        by_folder: Dict[str, List[Dict]] = defaultdict(list)
        for entry in selected:
            by_folder[entry["folder"]].append(entry)

        ordered_folder_lists = []
        for folder in sorted(by_folder.keys()):
            folder_items = sorted(by_folder[folder], key=lambda x: x["path"])
            ordered_folder_lists.append(folder_items)

        if len(ordered_folder_lists) < 2:
            return []

        batches: List[List[Dict]] = []
        index = 0
        while True:
            current_batch: List[Dict] = []
            for folder_items in ordered_folder_lists:
                if index < len(folder_items):
                    current_batch.append(folder_items[index])
            if not current_batch:
                break
            if len(current_batch) >= 2:
                batches.append(current_batch)
            index += 1
        return batches

    def start_merge(self):
        batches = self._build_batches()
        if not batches:
            QMessageBox.warning(self, "Cannot Start", "No valid inputs. Need at least 2 checked videos per merge.")
            return

        output_folder = self.output_edit.text().strip()
        if not output_folder:
            QMessageBox.warning(self, "Missing Output", "Please select an output folder.")
            return

        transition_map = {
            "None": "none",
            "Crossfade": "crossfade",
            "Fade": "fade",
            "Slide Left": "slide_left",
            "Slide Right": "slide_right",
            "Slide Up": "slide_up",
            "Slide Down": "slide_down",
            "Wipe Left": "wipe_left",
            "Wipe Right": "wipe_right",
            "Wipe Up": "wipe_up",
            "Wipe Down": "wipe_down",
            "Zoom In": "zoom_in",
            "Zoom Out": "zoom_out",
            "Dissolve (Random)": "dissolve_random",
            "Dissolve (Grid)": "dissolve_grid",
            "Dissolve (Radial)": "dissolve_radial",
            "Rotate": "rotate",
            "Blur": "blur",
        }
        quality_map = {"Match Source": "source"}

        merge_overrides = {
            "crop_enabled": self.crop_check.isChecked(),
            "crop_preset": self.crop_combo.currentText() if self.crop_check.isChecked() else None,
            "zoom_enabled": self.zoom_check.isChecked(),
            "zoom_factor": (self.zoom_spin.value() / 100.0) if self.zoom_check.isChecked() else 1.0,
            "flip_horizontal": self.mirror_h_check.isChecked(),
            "flip_vertical": self.mirror_v_check.isChecked(),
            "color_enhance_enabled": self.color_enhance_check.isChecked(),
            "brightness": self.brightness_spin.value() / 100.0,
            "contrast": self.contrast_spin.value() / 100.0,
            "saturation": self.saturation_spin.value() / 100.0,
            "blur_sides_enabled": self.blur_sides_check.isChecked(),
            "blur_sides_strength": float(self.blur_strength_spin.value()),
            "blur_sides_width_percent": int(self.blur_width_spin.value()),
            "blur_sides_feather_percent": int(self.blur_feather_spin.value()),
        }

        self.processor = SmartClipMergeProcessor(
            mode="simple" if self.mode_combo.currentIndex() == 0 else "bulk",
            batches=batches,
            output_folder=output_folder,
            clip_mode="center" if self.extract_mode_combo.currentText() == "Exact Center" else "random",
            global_seconds=self.global_seconds_spin.value(),
            output_format=self.format_combo.currentText().lower(),
            output_quality=quality_map.get(self.quality_combo.currentText(), self.quality_combo.currentText().lower()),
            delete_source=self.delete_source_check.isChecked(),
            transition_type=transition_map.get(self.transition_combo.currentText(), "none"),
            transition_duration=float(self.transition_duration_spin.value()),
            merge_overrides=merge_overrides,
        )

        self.processor.merge_completed.connect(self._on_merge_completed)
        self.start_btn.setEnabled(False)
        self.start_btn.setText("Processing...")
        self.merge_started.emit(self.processor)
        self.processor.start()
        logger.info(f"Started Smart Clip Merge with {len(batches)} batch(es)")

    def _on_merge_completed(self, success: bool, results: dict):
        self.start_btn.setEnabled(True)
        self.start_btn.setText("Start Smart Clip Merge")
        self.merge_completed.emit(success, results)

        if success:
            output_files = results.get("output_files", [])
            if len(output_files) == 1:
                QMessageBox.information(self, "Complete", f"Smart clip video created:\n{output_files[0]}")
            else:
                QMessageBox.information(
                    self,
                    "Complete",
                    f"Smart clip merge completed.\nGenerated files: {len(output_files)}",
                )
        else:
            error = results.get("error", "Unknown error")
            QMessageBox.critical(self, "Failed", f"Smart Clip Merge failed:\n{error}")

    def _update_summary(self):
        total = len(self.entries)
        checked = len(self._selected_entries())
        subfolders = len({entry["folder"] for entry in self.entries})

        folder_counts = defaultdict(int)
        for entry in self.entries:
            folder_counts[entry["folder_name"]] += 1

        folder_parts = [f"{name}:{count}" for name, count in sorted(folder_counts.items())]
        folder_text = " | ".join(folder_parts[:5])
        if len(folder_parts) > 5:
            folder_text += " | ..."

        self.summary_label.setText(
            f"Total videos: {total} | Checked: {checked} | Total subfolders: {subfolders}"
            + (f" | {folder_text}" if folder_text else "")
        )
        self._update_start_state()

    def _update_start_state(self):
        selected_entries = self._selected_entries()
        if self.mode_combo.currentIndex() == 0:
            self.start_btn.setEnabled(len(selected_entries) >= 2)
            return
        distinct_folders = {entry["folder"] for entry in selected_entries}
        self.start_btn.setEnabled(len(distinct_folders) >= 2 and len(selected_entries) >= 2)

    def browse_output(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder", self.output_edit.text())
        if folder:
            self.output_edit.setText(folder)

    def clear_all(self):
        self.entries = []
        self.bulk_folder_map = {}
        self.table.setRowCount(0)
        self.summary_label.setText("No input selected.")
        self._update_start_state()

    def reset(self):
        self.clear_all()
        self.global_seconds_spin.setValue(8)
        self.extract_mode_combo.setCurrentIndex(0)
        self.output_edit.setText(get_default_smart_clip_output_folder())
        self.format_combo.setCurrentText("MP4")
        self.quality_combo.setCurrentText("Match Source")
        self.transition_combo.setCurrentText("None")
        self.transition_duration_spin.setValue(1)
        self.crop_check.setChecked(False)
        self.crop_combo.setCurrentText("9:16")
        self.zoom_check.setChecked(False)
        self.zoom_spin.setValue(110)
        self.mirror_h_check.setChecked(False)
        self.mirror_v_check.setChecked(False)
        self.color_enhance_check.setChecked(False)
        self.brightness_spin.setValue(100)
        self.contrast_spin.setValue(100)
        self.saturation_spin.setValue(100)
        self.blur_sides_check.setChecked(False)
        self.blur_strength_spin.setValue(6)
        self.blur_width_spin.setValue(18)
        self.blur_feather_spin.setValue(60)
        self.delete_source_check.setChecked(False)
        self._set_preset_combo_text("Balanced")

    def get_processor(self) -> Optional[SmartClipMergeProcessor]:
        return self.processor

    def _collect_current_preset_values(self) -> Dict:
        return {
            "extract_mode": self.extract_mode_combo.currentText(),
            "global_seconds": int(self.global_seconds_spin.value()),
            "format": self.format_combo.currentText(),
            "quality": self.quality_combo.currentText(),
            "transition": self.transition_combo.currentText(),
            "transition_duration": int(self.transition_duration_spin.value()),
            "crop_enabled": self.crop_check.isChecked(),
            "crop_preset": self.crop_combo.currentText(),
            "zoom_enabled": self.zoom_check.isChecked(),
            "zoom_percent": int(self.zoom_spin.value()),
            "mirror_h": self.mirror_h_check.isChecked(),
            "mirror_v": self.mirror_v_check.isChecked(),
            "color_enhance": self.color_enhance_check.isChecked(),
            "brightness": int(self.brightness_spin.value()),
            "contrast": int(self.contrast_spin.value()),
            "saturation": int(self.saturation_spin.value()),
            "blur_sides": self.blur_sides_check.isChecked(),
            "blur_strength": int(self.blur_strength_spin.value()),
            "blur_width_percent": int(self.blur_width_spin.value()),
            "blur_feather_percent": int(self.blur_feather_spin.value()),
        }

    def _apply_preset_values(self, preset: Dict):
        self._preset_applying = True
        try:
            self.extract_mode_combo.setCurrentText(preset.get("extract_mode", "Exact Center"))
            self.global_seconds_spin.setValue(int(preset.get("global_seconds", 8)))
            self.format_combo.setCurrentText(preset.get("format", "MP4"))
            self.quality_combo.setCurrentText(preset.get("quality", "Match Source"))
            self.transition_combo.setCurrentText(preset.get("transition", "None"))
            self.transition_duration_spin.setValue(int(preset.get("transition_duration", 1)))

            self.crop_check.setChecked(bool(preset.get("crop_enabled", False)))
            self.crop_combo.setCurrentText(preset.get("crop_preset", "9:16"))

            self.zoom_check.setChecked(bool(preset.get("zoom_enabled", False)))
            self.zoom_spin.setValue(int(preset.get("zoom_percent", 110)))

            self.mirror_h_check.setChecked(bool(preset.get("mirror_h", False)))
            self.mirror_v_check.setChecked(bool(preset.get("mirror_v", False)))

            self.color_enhance_check.setChecked(bool(preset.get("color_enhance", False)))
            self.brightness_spin.setValue(int(preset.get("brightness", 100)))
            self.contrast_spin.setValue(int(preset.get("contrast", 100)))
            self.saturation_spin.setValue(int(preset.get("saturation", 100)))

            self.blur_sides_check.setChecked(bool(preset.get("blur_sides", False)))
            self.blur_strength_spin.setValue(int(preset.get("blur_strength", 6)))
            self.blur_width_spin.setValue(int(preset.get("blur_width_percent", 18)))
            self.blur_feather_spin.setValue(int(preset.get("blur_feather_percent", 60)))
        finally:
            self._preset_applying = False

    def _load_presets(self):
        loaded_custom: Dict[str, Dict] = {}
        try:
            if self.PRESET_FILE.exists():
                data = json.loads(self.PRESET_FILE.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    for name, values in data.items():
                        if isinstance(values, dict):
                            loaded_custom[name] = values
        except Exception as e:
            logger.warning(f"Failed to load smart clip presets: {e}")

        self.presets = dict(self.DEFAULT_PRESETS)
        self.presets.update(loaded_custom)

        self._preset_applying = True
        try:
            self.preset_combo.clear()
            self.preset_combo.addItems(sorted(self.presets.keys()))
        finally:
            self._preset_applying = False

        self._set_preset_combo_text("Balanced")
        self.apply_selected_preset(self.preset_combo.currentText())

    def _save_custom_presets_to_disk(self):
        try:
            custom = {
                name: values
                for name, values in self.presets.items()
                if name not in self.DEFAULT_PRESETS
            }
            self.PRESET_FILE.write_text(json.dumps(custom, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to save smart clip presets: {e}")

    def _set_preset_combo_text(self, name: str):
        idx = self.preset_combo.findText(name)
        if idx >= 0:
            self._preset_applying = True
            try:
                self.preset_combo.setCurrentIndex(idx)
            finally:
                self._preset_applying = False

    def apply_selected_preset(self, name: str):
        if self._preset_applying:
            return
        if not name or name not in self.presets:
            return
        self._apply_preset_values(self.presets[name])

    def save_current_preset(self):
        name = self.preset_name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Preset Name", "Please enter preset name.")
            return
        if name in self.DEFAULT_PRESETS:
            QMessageBox.warning(self, "Preset Name", "This name is reserved for default presets.")
            return
        self.presets[name] = self._collect_current_preset_values()
        self._save_custom_presets_to_disk()
        self._preset_applying = True
        try:
            if self.preset_combo.findText(name) < 0:
                self.preset_combo.addItem(name)
        finally:
            self._preset_applying = False
        self._set_preset_combo_text(name)
        QMessageBox.information(self, "Preset Saved", f"Preset '{name}' saved.")

    def delete_selected_preset(self):
        name = self.preset_combo.currentText()
        if not name:
            return
        if name in self.DEFAULT_PRESETS:
            QMessageBox.warning(self, "Preset", "Default presets cannot be deleted.")
            return
        if name not in self.presets:
            return
        reply = QMessageBox.question(
            self,
            "Delete Preset",
            f"Delete preset '{name}'?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        del self.presets[name]
        self._save_custom_presets_to_disk()
        self._preset_applying = True
        try:
            idx = self.preset_combo.findText(name)
            if idx >= 0:
                self.preset_combo.removeItem(idx)
        finally:
            self._preset_applying = False
        self._set_preset_combo_text("Balanced")

    def export_presets(self):
        """Export custom presets to a JSON file."""
        try:
            custom = {
                name: values
                for name, values in self.presets.items()
                if name not in self.DEFAULT_PRESETS
            }
            if not custom:
                QMessageBox.information(self, "Export Presets", "No custom presets available to export.")
                return

            suggested = str(Path.home() / "Desktop" / "smart_clip_presets.json")
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Export Smart Clip Presets",
                suggested,
                "JSON Files (*.json);;All Files (*.*)",
            )
            if not path:
                return

            Path(path).write_text(json.dumps(custom, indent=2), encoding="utf-8")
            QMessageBox.information(self, "Export Presets", f"Custom presets exported to:\n{path}")
        except Exception as e:
            logger.warning(f"Failed to export presets: {e}")
            QMessageBox.critical(self, "Export Failed", f"Could not export presets:\n{e}")

    def import_presets(self):
        """Import presets from JSON file and merge with existing custom presets."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Smart Clip Presets",
            "",
            "JSON Files (*.json);;All Files (*.*)",
        )
        if not path:
            return

        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("Invalid preset file format: root must be an object")

            imported_count = 0
            for name, values in data.items():
                if not isinstance(name, str) or not name.strip():
                    continue
                if name in self.DEFAULT_PRESETS:
                    continue
                if not isinstance(values, dict):
                    continue
                self.presets[name] = values
                imported_count += 1

            if imported_count == 0:
                QMessageBox.warning(
                    self,
                    "Import Presets",
                    "No valid custom presets found in selected file.",
                )
                return

            self._save_custom_presets_to_disk()
            self._preset_applying = True
            try:
                current_name = self.preset_combo.currentText()
                self.preset_combo.clear()
                self.preset_combo.addItems(sorted(self.presets.keys()))
                target_name = current_name if current_name in self.presets else "Balanced"
            finally:
                self._preset_applying = False

            self._set_preset_combo_text(target_name)
            self.apply_selected_preset(self.preset_combo.currentText())
            QMessageBox.information(
                self,
                "Import Presets",
                f"Imported {imported_count} custom preset(s).",
            )
        except Exception as e:
            logger.warning(f"Failed to import presets: {e}")
            QMessageBox.critical(self, "Import Failed", f"Could not import presets:\n{e}")
