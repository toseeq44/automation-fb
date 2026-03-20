"""
Compact dialog for Creator Profile "Split + Edit" settings.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .config_manager import merge_split_edit_settings, summarize_split_edit_settings


class SplitEditDialog(QDialog):
    _STYLE = """
        QDialog { background: #0d1117; color: white; }
        QLabel { color: rgba(255,255,255,0.84); background: transparent; border: none; }
        QComboBox, QSpinBox {
            background: #161b22; color: white;
            border: 1px solid rgba(0,212,255,0.28);
            border-radius: 4px; padding: 6px;
        }
        QComboBox:focus, QSpinBox:focus {
            border: 1px solid #00d4ff;
        }
        QCheckBox {
            color: white;
            spacing: 6px;
        }
        QCheckBox::indicator {
            width: 16px;
            height: 16px;
        }
        QSlider::groove:horizontal {
            background: rgba(0,212,255,0.15);
            height: 4px;
            border-radius: 2px;
        }
        QSlider::handle:horizontal {
            background: #00d4ff;
            width: 14px;
            height: 14px;
            margin: -5px 0;
            border-radius: 7px;
        }
        QPushButton {
            background: #161b22; color: white;
            border: 1px solid rgba(0,212,255,0.3);
            border-radius: 5px; padding: 7px 18px; font-weight: bold;
        }
        QPushButton:hover { background: #1c2128; border-color: #00d4ff; }
    """

    def __init__(self, settings=None, parent=None, title: str = "Split + Edit Options"):
        super().__init__(parent)
        self._settings = merge_split_edit_settings(settings)
        self.setWindowTitle(title)
        self.setMinimumWidth(460)
        self.resize(500, 430)
        self.setStyleSheet(self._STYLE)
        self._build()
        self._load()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 14)
        root.setSpacing(12)

        title = QLabel("Split + Edit")
        title.setFont(QFont("Segoe UI", 13, QFont.Bold))
        title.setStyleSheet("color:#00d4ff; background:transparent; border:none;")
        root.addWidget(title)

        note = QLabel(
            "Processing order: download -> split -> edit each split clip -> watermark if enabled."
        )
        note.setWordWrap(True)
        note.setStyleSheet(
            "color:rgba(255,255,255,0.56); font-size:11px; background:transparent; border:none;"
        )
        root.addWidget(note)
        root.addWidget(self._div())

        form = QFormLayout()
        form.setSpacing(11)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.zoom_spin = QSpinBox()
        self.zoom_spin.setRange(50, 200)
        self.zoom_spin.setSuffix(" %")
        self.zoom_spin.valueChanged.connect(self._update_summary)
        form.addRow("Zoom:", self.zoom_spin)

        self.music_remove_check = QCheckBox("Reduce background music and keep vocals")
        self.music_remove_check.stateChanged.connect(self._update_summary)
        form.addRow("Audio:", self.music_remove_check)

        self.voice_enable_check = QCheckBox("Enable voice enhancement")
        self.voice_enable_check.stateChanged.connect(self._update_voice_controls)
        form.addRow("Voice:", self.voice_enable_check)

        self.voice_pitch_slider = QSlider(Qt.Horizontal)
        self.voice_pitch_slider.setRange(-10, 10)
        self.voice_pitch_label = QLabel("0%")
        self.voice_pitch_label.setStyleSheet(
            "color:white; background:transparent; border:none; min-width:36px;"
        )
        self.voice_pitch_slider.valueChanged.connect(
            lambda value: self.voice_pitch_label.setText(f"{value:+d}%")
        )
        self.voice_pitch_slider.valueChanged.connect(self._update_summary)
        pitch_row = QHBoxLayout()
        pitch_row.setContentsMargins(0, 0, 0, 0)
        pitch_row.setSpacing(6)
        pitch_row.addWidget(self.voice_pitch_slider, 1)
        pitch_row.addWidget(self.voice_pitch_label)
        pitch_wrap = QWidget()
        pitch_wrap.setStyleSheet("background:transparent; border:none;")
        pitch_wrap.setLayout(pitch_row)
        form.addRow("Voice Pitch:", pitch_wrap)

        self.voice_clarity_combo = QComboBox()
        self.voice_clarity_combo.addItems(["Mild", "Strong"])
        self.voice_clarity_combo.currentIndexChanged.connect(self._update_summary)
        form.addRow("Voice Clarity:", self.voice_clarity_combo)

        self.metadata_combo = QComboBox()
        self.metadata_combo.addItems(["Off", "Medium", "High"])
        self.metadata_combo.currentIndexChanged.connect(self._update_summary)
        form.addRow("Metadata:", self.metadata_combo)

        self.mirror_check = QCheckBox("Mirror video left-right")
        self.mirror_check.stateChanged.connect(self._update_summary)
        form.addRow("Mirror:", self.mirror_check)

        root.addLayout(form)
        root.addWidget(self._div())

        self.summary_lbl = QLabel("")
        self.summary_lbl.setWordWrap(True)
        self.summary_lbl.setStyleSheet(
            "color:rgba(255,255,255,0.72); font-size:11px; background:transparent; border:none;"
        )
        root.addWidget(self.summary_lbl)

        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Save).setStyleSheet(
            "background:#1a5c1a; color:white; font-weight:bold; padding:7px 22px; border-radius:5px;"
        )
        btns.button(QDialogButtonBox.Cancel).setStyleSheet(
            "background:#3a1a1a; color:white; font-weight:bold; padding:7px 22px; border-radius:5px;"
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

    @staticmethod
    def _div() -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet(
            "background: rgba(0,212,255,0.12); border: none; max-height: 1px;"
        )
        return line

    def _load(self) -> None:
        settings = self._settings
        self.zoom_spin.setValue(int(settings["zoom_percent"]))
        self.music_remove_check.setChecked(bool(settings["remove_background_music"]))
        self.voice_enable_check.setChecked(bool(settings["voice_enhance_enabled"]))
        self.voice_pitch_slider.setValue(int(settings["voice_pitch_percent"]))
        self.voice_clarity_combo.setCurrentText(str(settings["voice_clarity"]).capitalize())
        self.metadata_combo.setCurrentText(str(settings["metadata_level"]).capitalize())
        self.mirror_check.setChecked(bool(settings["mirror_horizontal"]))
        self._update_voice_controls()
        self._update_summary()

    def _update_voice_controls(self) -> None:
        enabled = self.voice_enable_check.isChecked()
        self.voice_pitch_slider.setEnabled(enabled)
        self.voice_clarity_combo.setEnabled(enabled)
        self._update_summary()

    def _update_summary(self) -> None:
        self.summary_lbl.setText(f"Summary: {summarize_split_edit_settings(self.get_settings())}")

    def get_settings(self) -> dict:
        return merge_split_edit_settings(
            {
                "zoom_percent": self.zoom_spin.value(),
                "remove_background_music": self.music_remove_check.isChecked(),
                "voice_enhance_enabled": self.voice_enable_check.isChecked(),
                "voice_pitch_percent": self.voice_pitch_slider.value(),
                "voice_clarity": self.voice_clarity_combo.currentText().strip().lower(),
                "metadata_level": self.metadata_combo.currentText().strip().lower(),
                "mirror_horizontal": self.mirror_check.isChecked(),
            }
        )
