"""
modules/creator_profiles/edit_dialog.py
Edit Creator Settings modal — all labels and messages in English.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFormLayout, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from .config_manager import CreatorConfig


class EditCreatorDialog(QDialog):

    _STYLE = """
        QDialog  { background: #0d1117; color: white; }
        QLabel   { color: rgba(255,255,255,0.82); background: transparent; border: none; }
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
            background: #161b22; color: white;
            border: 1px solid rgba(0,212,255,0.28);
            border-radius: 4px; padding: 6px;
        }
        QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
            border: 1px solid #00d4ff;
        }
        QComboBox::drop-down { border: none; }
        QComboBox QAbstractItemView {
            background: #161b22; color: white;
            border: 1px solid #00d4ff;
            selection-background-color: rgba(0,212,255,0.2);
        }
        QPushButton {
            background: #161b22; color: white;
            border: 1px solid rgba(0,212,255,0.3);
            border-radius: 5px; padding: 7px 18px; font-weight: bold;
        }
        QPushButton:hover { background: #1c2128; border-color: #00d4ff; }
    """

    def __init__(self, config: CreatorConfig, preset_names: list, parent=None):
        super().__init__(parent)
        self.config       = config
        self.preset_names = preset_names
        self.setWindowTitle("Edit Creator Settings")
        self.setMinimumWidth(500)
        self.setStyleSheet(self._STYLE)
        self._build()
        self._load()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 22, 24, 22)
        outer.setSpacing(16)

        # Title
        title = QLabel("✏   Creator Settings")
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title.setStyleSheet("color: #00d4ff; background: transparent; border: none;")
        outer.addWidget(title)

        outer.addWidget(self._div())

        # Form
        form = QFormLayout()
        form.setSpacing(11)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        # Creator URL
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText(
            "https://www.tiktok.com/@username   or   https://youtube.com/@channel"
        )
        form.addRow("Creator URL:", self.url_edit)

        # N Videos
        self.n_spin = QSpinBox()
        self.n_spin.setRange(1, 100)
        self.n_spin.setFixedWidth(96)
        form.addRow("N Videos:", self.n_spin)

        # Editing mode
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["None", "Preset", "Split"])
        self.mode_combo.setFixedWidth(110)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_change)
        form.addRow("Editing Mode:", self.mode_combo)

        # Preset
        self.preset_lbl   = QLabel("Preset:")
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(self.preset_names or ["— no presets —"])
        form.addRow(self.preset_lbl, self.preset_combo)

        # Split duration
        self.split_lbl  = QLabel("Split Duration:")
        self.split_spin = QDoubleSpinBox()
        self.split_spin.setRange(1.0, 3600.0)
        self.split_spin.setSuffix(" seconds")
        self.split_spin.setFixedWidth(140)
        form.addRow(self.split_lbl, self.split_spin)

        # Duplication toggle
        dup_row = QHBoxLayout()
        self.dup_btn = QPushButton("ON")
        self.dup_btn.setCheckable(True)
        self.dup_btn.setFixedWidth(76)
        self.dup_btn.clicked.connect(lambda: self._apply_toggle_style(self.dup_btn))
        dup_note = QLabel(
            "ON  =  Tiered scan (Latest → Popular → Weekly) + skip already downloaded\n"
            "OFF =  Download latest N videos, no duplicate check"
        )
        dup_note.setStyleSheet(
            "color: rgba(255,255,255,0.38); font-size: 10px;"
            " background: transparent; border: none;"
        )
        dup_row.addWidget(self.dup_btn)
        dup_row.addSpacing(8)
        dup_row.addWidget(dup_note)
        dup_row.addStretch()
        dup_w = QWidget()
        dup_w.setStyleSheet("background: transparent; border: none;")
        dup_w.setLayout(dup_row)
        form.addRow("Duplication:", dup_w)

        # Popular fallback
        pop_row = QHBoxLayout()
        self.pop_btn = QPushButton("ON")
        self.pop_btn.setCheckable(True)
        self.pop_btn.setFixedWidth(76)
        self.pop_btn.clicked.connect(lambda: self._apply_toggle_style(self.pop_btn))
        pop_note = QLabel("Use popular videos if latest/week backlog cannot fill N.")
        pop_note.setStyleSheet(
            "color: rgba(255,255,255,0.38); font-size: 10px;"
            " background: transparent; border: none;"
        )
        pop_row.addWidget(self.pop_btn)
        pop_row.addSpacing(8)
        pop_row.addWidget(pop_note)
        pop_row.addStretch()
        pop_w = QWidget()
        pop_w.setStyleSheet("background: transparent; border: none;")
        pop_w.setLayout(pop_row)
        form.addRow("Popular Fallback:", pop_w)

        # Randomize queue
        rnd_row = QHBoxLayout()
        self.rnd_btn = QPushButton("OFF")
        self.rnd_btn.setCheckable(True)
        self.rnd_btn.setFixedWidth(76)
        self.rnd_btn.clicked.connect(lambda: self._apply_toggle_style(self.rnd_btn))
        rnd_note = QLabel("Shuffle candidates before download.")
        rnd_note.setStyleSheet(
            "color: rgba(255,255,255,0.38); font-size: 10px;"
            " background: transparent; border: none;"
        )
        rnd_row.addWidget(self.rnd_btn)
        rnd_row.addSpacing(8)
        rnd_row.addWidget(rnd_note)
        rnd_row.addStretch()
        rnd_w = QWidget()
        rnd_w.setStyleSheet("background: transparent; border: none;")
        rnd_w.setLayout(rnd_row)
        form.addRow("Randomize:", rnd_w)

        # Keep original after edit
        keep_row = QHBoxLayout()
        self.keep_btn = QPushButton("ON")
        self.keep_btn.setCheckable(True)
        self.keep_btn.setFixedWidth(76)
        self.keep_btn.clicked.connect(lambda: self._apply_toggle_style(self.keep_btn))
        keep_note = QLabel("ON = keep original video, OFF = delete original after edit.")
        keep_note.setStyleSheet(
            "color: rgba(255,255,255,0.38); font-size: 10px;"
            " background: transparent; border: none;"
        )
        keep_row.addWidget(self.keep_btn)
        keep_row.addSpacing(8)
        keep_row.addWidget(keep_note)
        keep_row.addStretch()
        keep_w = QWidget()
        keep_w.setStyleSheet("background: transparent; border: none;")
        keep_w.setLayout(keep_row)
        form.addRow("Keep Original:", keep_w)

        outer.addLayout(form)
        outer.addWidget(self._div())

        # Buttons
        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Save).setStyleSheet(
            "background:#1a5c1a; color:white; font-weight:bold;"
            " padding:7px 22px; border-radius:5px;"
        )
        btns.button(QDialogButtonBox.Cancel).setStyleSheet(
            "background:#3a1a1a; color:white; font-weight:bold;"
            " padding:7px 22px; border-radius:5px;"
        )
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        outer.addWidget(btns)

    @staticmethod
    def _div() -> QFrame:
        d = QFrame()
        d.setFrameShape(QFrame.HLine)
        d.setStyleSheet(
            "background: rgba(0,212,255,0.12); border: none; max-height: 1px;"
        )
        return d

    def _load(self):
        c = self.config
        self.url_edit.setText(c.creator_url)
        self.n_spin.setValue(c.n_videos)
        self.split_spin.setValue(c.split_duration)
        self.mode_combo.setCurrentIndex(
            {"none": 0, "preset": 1, "split": 2}.get(c.editing_mode, 0)
        )
        if c.preset_name and c.preset_name in self.preset_names:
            self.preset_combo.setCurrentText(c.preset_name)
        self.dup_btn.setChecked(c.duplication_control)
        self.pop_btn.setChecked(c.popular_fallback)
        self.rnd_btn.setChecked(c.randomize_links)
        self.keep_btn.setChecked(c.keep_original_after_edit)
        self._apply_toggle_style(self.dup_btn)
        self._apply_toggle_style(self.pop_btn)
        self._apply_toggle_style(self.rnd_btn)
        self._apply_toggle_style(self.keep_btn)
        self._on_mode_change()

    def _on_mode_change(self):
        m = self.mode_combo.currentIndex()
        self.preset_lbl.setVisible(m == 1)
        self.preset_combo.setVisible(m == 1)
        self.split_lbl.setVisible(m == 2)
        self.split_spin.setVisible(m == 2)

    def _apply_toggle_style(self, btn: QPushButton):
        on = btn.isChecked()
        btn.setText("ON" if on else "OFF")
        btn.setStyleSheet(
            ("QPushButton { background:#1a5c1a; color:white; font-weight:bold;"
             " border-radius:4px; padding:5px 14px; border:none; }"
             "QPushButton:hover { background:#236e23; }")
            if on else
            ("QPushButton { background:#2a2a2a; color:#777; font-weight:bold;"
             " border-radius:4px; padding:5px 14px; border:none; }"
             "QPushButton:hover { background:#333; }")
        )

    def _save(self):
        mode = ["none", "preset", "split"][self.mode_combo.currentIndex()]
        self.config.data.update({
            "creator_url":         self.url_edit.text().strip(),
            "n_videos":            self.n_spin.value(),
            "editing_mode":        mode,
            "preset_name":         self.preset_combo.currentText(),
            "split_duration":      self.split_spin.value(),
            "duplication_control": self.dup_btn.isChecked(),
            "popular_fallback":    self.pop_btn.isChecked(),
            "randomize_links":     self.rnd_btn.isChecked(),
            "keep_original_after_edit": self.keep_btn.isChecked(),
        })
        self.config.save()
        self.accept()
