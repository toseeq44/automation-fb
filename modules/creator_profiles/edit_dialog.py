"""
modules/creator_profiles/edit_dialog.py
Edit Creator Settings modal — all labels and messages in English.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFormLayout, QFrame, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QSlider, QSpinBox, QToolButton, QStyle,
    QVBoxLayout, QWidget,
)
from .config_manager import CreatorConfig

_WM_FONT_PRESETS = [
    "Arial",
    "Verdana",
    "Times New Roman",
    "Georgia",
    "Trebuchet MS",
]

_WM_COLOR_PRESETS = [
    ("White", "#FFFFFF"),
    ("Black", "#000000"),
    ("Cyan", "#00D4FF"),
    ("Gold", "#DEBF07"),
    ("Red", "#FF4D4D"),
    ("Lime", "#7CFC00"),
    ("Orange", "#FFA500"),
    ("Purple", "#B388FF"),
]


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
        self.setMinimumWidth(520)
        self.resize(540, 680)
        self.setStyleSheet(self._STYLE)
        self._build()
        self._load()

    def _build(self):
        # ── Outer layout holds scroll area + buttons ───────────────────────
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 16)
        outer.setSpacing(0)

        # ── Scroll area ────────────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.NoFrame)
        scroll.setStyleSheet(
            "QScrollArea { background: #0d1117; border: none; }"
            "QScrollBar:vertical { background:#0d1117; width:8px; border-radius:4px; }"
            "QScrollBar::handle:vertical { background:rgba(0,212,255,0.3); border-radius:4px; min-height:20px; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0px; }"
        )
        outer.addWidget(scroll, 1)

        # ── Container inside scroll ────────────────────────────────────────
        container = QWidget()
        container.setStyleSheet("background: #0d1117;")
        scroll.setWidget(container)

        inner = QVBoxLayout(container)
        inner.setContentsMargins(24, 22, 24, 12)
        inner.setSpacing(16)

        # Title
        title = QLabel("✏   Creator Settings")
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title.setStyleSheet("color: #00d4ff; background: transparent; border: none;")
        inner.addWidget(title)

        inner.addWidget(self._div())

        # Form — we assign to `outer` alias so rest of method still uses `outer.addLayout`
        # but inside the scroll container
        outer_ref = inner  # alias: all addWidget/addLayout calls below go into `inner`

        # Re-bind `outer` to point to inner for the rest of this method
        outer = inner

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
        self.dup_btn.setFixedWidth(86)
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
        self.pop_btn.setFixedWidth(86)
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
        self.rnd_btn.setFixedWidth(86)
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
        self.keep_btn.setFixedWidth(86)
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

        # ── WaterMark Section ──────────────────────────────────────────────
        wm_title = QLabel("💧  WaterMark Settings")
        wm_title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        wm_title.setStyleSheet("color:#00d4ff; background:transparent; border:none;")
        outer.addWidget(wm_title)

        wm_form = QFormLayout()
        wm_form.setSpacing(10)
        wm_form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        # Global watermark enable
        wm_en_row = QHBoxLayout()
        self.wm_enable_btn = QPushButton("OFF")
        self.wm_enable_btn.setCheckable(True)
        self.wm_enable_btn.setFixedWidth(86)
        self.wm_enable_btn.clicked.connect(lambda: self._apply_toggle_style(self.wm_enable_btn))
        self.wm_enable_btn.clicked.connect(self._on_wm_enable_change)
        wm_en_note = QLabel("Enable watermark on all downloaded/split videos.")
        wm_en_note.setStyleSheet("color:rgba(255,255,255,0.38); font-size:10px; background:transparent; border:none;")
        wm_en_row.addWidget(self.wm_enable_btn)
        wm_en_row.addSpacing(8)
        wm_en_row.addWidget(wm_en_note)
        wm_en_row.addStretch()
        wm_en_w = QWidget(); wm_en_w.setStyleSheet("background:transparent; border:none;"); wm_en_w.setLayout(wm_en_row)
        wm_form.addRow("WaterMark:", wm_en_w)

        # ── Text Watermark ────────────────────────────────────────────────
        txt_hdr = QLabel("  Text Watermark")
        txt_hdr.setStyleSheet("color:#aaa; font-size:11px; font-weight:bold; background:transparent; border:none;")
        wm_form.addRow(txt_hdr)

        txt_en_row = QHBoxLayout()
        self.wm_txt_enable_btn = QPushButton("OFF")
        self.wm_txt_enable_btn.setCheckable(True)
        self.wm_txt_enable_btn.setFixedWidth(86)
        self.wm_txt_enable_btn.clicked.connect(lambda: self._apply_toggle_style(self.wm_txt_enable_btn))
        txt_en_row.addWidget(self.wm_txt_enable_btn); txt_en_row.addStretch()
        txt_en_w = QWidget(); txt_en_w.setStyleSheet("background:transparent; border:none;"); txt_en_w.setLayout(txt_en_row)
        wm_form.addRow("  Enable Text:", txt_en_w)

        self.wm_text_edit = QLineEdit()
        self.wm_text_edit.setPlaceholderText("Leave blank to use @folderName")
        wm_form.addRow("  Text:", self.wm_text_edit)

        self.wm_txt_pos_cb = QComboBox()
        self.wm_txt_pos_cb.addItems([
            "TopLeft", "TopRight", "BottomLeft", "BottomRight", "Center", "AnimateAround"
        ])
        self.wm_txt_pos_cb.setFixedWidth(160)
        wm_form.addRow("  Position:", self.wm_txt_pos_cb)

        self.wm_txt_opacity_sl = QSlider(Qt.Horizontal)
        self.wm_txt_opacity_sl.setRange(0, 100)
        self.wm_txt_opacity_sl.setValue(80)
        self.wm_txt_opacity_lbl = QLabel("80%")
        self.wm_txt_opacity_lbl.setStyleSheet("color:white; background:transparent; border:none; min-width:32px;")
        self.wm_txt_opacity_sl.valueChanged.connect(lambda v: self.wm_txt_opacity_lbl.setText(f"{v}%"))
        op_row = QHBoxLayout(); op_row.addWidget(self.wm_txt_opacity_sl); op_row.addWidget(self.wm_txt_opacity_lbl)
        op_w = QWidget(); op_w.setStyleSheet("background:transparent; border:none;"); op_w.setLayout(op_row)
        wm_form.addRow("  Opacity:", op_w)

        self.wm_txt_font_edit = QComboBox()
        self.wm_txt_font_edit.setEditable(True)
        self.wm_txt_font_edit.setMinimumWidth(160)
        self._init_wm_font_presets(self.wm_txt_font_edit)
        wm_form.addRow("  Font Family:", self.wm_txt_font_edit)

        self.wm_txt_color_preset_cb = QComboBox()
        self.wm_txt_color_preset_cb.setMinimumWidth(248)
        self._init_wm_color_presets(self.wm_txt_color_preset_cb)
        wm_form.addRow("  Font Color:", self.wm_txt_color_preset_cb)

        self.wm_txt_size_sp = QSpinBox()
        self.wm_txt_size_sp.setRange(8, 200)
        self.wm_txt_size_sp.setValue(24)
        self.wm_txt_size_sp.setFixedWidth(80)
        wm_form.addRow("  Font Size:", self.wm_txt_size_sp)

        self.wm_txt_weight_cb = QComboBox()
        self.wm_txt_weight_cb.addItems(["normal", "bold"])
        self.wm_txt_weight_cb.setFixedWidth(100)
        wm_form.addRow("  Font Weight:", self.wm_txt_weight_cb)

        self.wm_txt_style_cb = QComboBox()
        self.wm_txt_style_cb.addItems(["normal", "italic"])
        self.wm_txt_style_cb.setFixedWidth(100)
        wm_form.addRow("  Font Style:", self.wm_txt_style_cb)

        self.wm_txt_render_style_cb = QComboBox()
        self.wm_txt_render_style_cb.addItems(
            ["normal", "outline_hollow", "outline_shadow"]
        )
        self.wm_txt_render_style_cb.setFixedWidth(140)
        wm_form.addRow("  Render Style:", self.wm_txt_render_style_cb)

        self.wm_txt_shadow_opacity_sl = QSlider(Qt.Horizontal)
        self.wm_txt_shadow_opacity_sl.setRange(0, 100)
        self.wm_txt_shadow_opacity_sl.setValue(75)
        self.wm_txt_shadow_opacity_lbl = QLabel("75%")
        self.wm_txt_shadow_opacity_lbl.setStyleSheet(
            "color:white; background:transparent; border:none; min-width:32px;"
        )
        self.wm_txt_shadow_opacity_sl.valueChanged.connect(
            lambda v: self.wm_txt_shadow_opacity_lbl.setText(f"{v}%")
        )
        sop_row = QHBoxLayout()
        sop_row.addWidget(self.wm_txt_shadow_opacity_sl)
        sop_row.addWidget(self.wm_txt_shadow_opacity_lbl)
        sop_w = QWidget()
        sop_w.setStyleSheet("background:transparent; border:none;")
        sop_w.setLayout(sop_row)
        wm_form.addRow("  Shadow Opacity:", sop_w)

        self.wm_txt_shadow_offset_sp = QSpinBox()
        self.wm_txt_shadow_offset_sp.setRange(0, 50)
        self.wm_txt_shadow_offset_sp.setValue(2)
        self.wm_txt_shadow_offset_sp.setFixedWidth(80)
        wm_form.addRow("  Shadow Offset:", self.wm_txt_shadow_offset_sp)

        self.wm_txt_spacing_sp = QSpinBox()
        self.wm_txt_spacing_sp.setRange(0, 50)
        self.wm_txt_spacing_sp.setValue(0)
        self.wm_txt_spacing_sp.setFixedWidth(80)
        wm_form.addRow("  Letter Spacing:", self.wm_txt_spacing_sp)

        # ── Logo Watermark ────────────────────────────────────────────────
        logo_hdr = QLabel("  Logo Watermark")
        logo_hdr.setStyleSheet("color:#aaa; font-size:11px; font-weight:bold; background:transparent; border:none;")
        wm_form.addRow(logo_hdr)

        logo_en_row = QHBoxLayout()
        self.wm_logo_enable_btn = QPushButton("OFF")
        self.wm_logo_enable_btn.setCheckable(True)
        self.wm_logo_enable_btn.setFixedWidth(86)
        self.wm_logo_enable_btn.clicked.connect(lambda: self._apply_toggle_style(self.wm_logo_enable_btn))
        logo_en_row.addWidget(self.wm_logo_enable_btn); logo_en_row.addStretch()
        logo_en_w = QWidget(); logo_en_w.setStyleSheet("background:transparent; border:none;"); logo_en_w.setLayout(logo_en_row)
        wm_form.addRow("  Enable Logo:", logo_en_w)

        logo_path_row = QHBoxLayout()
        self.wm_logo_path_edit = QLineEdit()
        self.wm_logo_path_edit.setPlaceholderText("Leave blank to auto-detect logo.* in creator folder")
        logo_browse_btn = QToolButton()
        logo_browse_btn.setIcon(self.style().standardIcon(QStyle.SP_DirOpenIcon))
        logo_browse_btn.setToolTip("Select logo file")
        logo_browse_btn.setAutoRaise(True)
        logo_browse_btn.setFixedSize(30, 28)
        logo_browse_btn.setStyleSheet(
            "QToolButton { background:#2a2410; border:1px solid rgba(222,191,7,0.7); border-radius:4px; }"
            "QToolButton:hover { background:#3a3216; border-color:#DEBF07; }"
        )
        logo_browse_btn.clicked.connect(self._browse_logo)
        logo_path_row.addWidget(self.wm_logo_path_edit)
        logo_path_row.addWidget(logo_browse_btn)
        logo_path_w = QWidget(); logo_path_w.setStyleSheet("background:transparent; border:none;"); logo_path_w.setLayout(logo_path_row)
        wm_form.addRow("  Logo Path:", logo_path_w)

        self.wm_logo_pos_cb = QComboBox()
        self.wm_logo_pos_cb.addItems([
            "TopLeft", "TopRight", "BottomLeft", "BottomRight", "Center", "AnimateAround"
        ])
        self.wm_logo_pos_cb.setFixedWidth(160)
        wm_form.addRow("  Position:", self.wm_logo_pos_cb)

        self.wm_logo_opacity_sl = QSlider(Qt.Horizontal)
        self.wm_logo_opacity_sl.setRange(0, 100)
        self.wm_logo_opacity_sl.setValue(80)
        self.wm_logo_opacity_lbl = QLabel("80%")
        self.wm_logo_opacity_lbl.setStyleSheet("color:white; background:transparent; border:none; min-width:32px;")
        self.wm_logo_opacity_sl.valueChanged.connect(lambda v: self.wm_logo_opacity_lbl.setText(f"{v}%"))
        lop_row = QHBoxLayout(); lop_row.addWidget(self.wm_logo_opacity_sl); lop_row.addWidget(self.wm_logo_opacity_lbl)
        lop_w = QWidget(); lop_w.setStyleSheet("background:transparent; border:none;"); lop_w.setLayout(lop_row)
        wm_form.addRow("  Opacity:", lop_w)

        self._set_color_preset_from_hex(self.wm_txt_color_preset_cb, "#FFFFFF")

        outer.addLayout(wm_form)
        outer.addStretch(1)  # push content to top inside scroll

        # ── Buttons — outside scroll, fixed at bottom ──────────────────────
        btn_sep = self._div()
        btn_sep.setStyleSheet("background:rgba(0,212,255,0.15); border:none; max-height:1px;")
        outer_ref.addWidget(btn_sep)

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
        btn_w = QWidget()
        btn_w.setStyleSheet("background:#0d1117; border:none;")
        btn_layout = QHBoxLayout(btn_w)
        btn_layout.setContentsMargins(24, 8, 24, 8)
        btn_layout.addWidget(btns)
        outer_ref.addWidget(btn_w)

    @staticmethod
    def _div() -> QFrame:
        d = QFrame()
        d.setFrameShape(QFrame.HLine)
        d.setStyleSheet(
            "background: rgba(0,212,255,0.12); border: none; max-height: 1px;"
        )
        return d

    @staticmethod
    def _init_wm_font_presets(combo: QComboBox):
        seen = set()
        for font_name in _WM_FONT_PRESETS:
            key = font_name.lower()
            if key in seen:
                continue
            combo.addItem(font_name)
            seen.add(key)
        combo.setCurrentText("Arial")

    @staticmethod
    def _init_wm_color_presets(combo: QComboBox):
        for name, hex_color in _WM_COLOR_PRESETS:
            combo.addItem(f"{name} ({hex_color})", hex_color)
            idx = combo.count() - 1
            bg = QColor(hex_color)
            combo.setItemData(idx, bg, Qt.BackgroundRole)
            luminance = (bg.red() * 299 + bg.green() * 587 + bg.blue() * 114) / 1000
            fg = QColor("#111111") if luminance > 150 else QColor("#f5f7ff")
            combo.setItemData(idx, fg, Qt.ForegroundRole)

    @staticmethod
    def _set_color_preset_from_hex(combo: QComboBox, hex_color: str):
        wanted = (hex_color or "").strip().upper()
        for i in range(combo.count()):
            val = str(combo.itemData(i) or "").strip().upper()
            if val == wanted:
                combo.setCurrentIndex(i)
                return

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

        # Load watermark settings
        self.wm_enable_btn.setChecked(c.watermark_enabled)
        self._apply_toggle_style(self.wm_enable_btn)

        wt = c.watermark_text
        self.wm_txt_enable_btn.setChecked(bool(wt.get("enabled", False)))
        self._apply_toggle_style(self.wm_txt_enable_btn)
        self.wm_text_edit.setText(wt.get("text", ""))
        pos_list = ["TopLeft", "TopRight", "BottomLeft", "BottomRight", "Center", "AnimateAround"]
        txt_pos = wt.get("position", "BottomRight")
        if txt_pos in pos_list:
            self.wm_txt_pos_cb.setCurrentText(txt_pos)
        self.wm_txt_opacity_sl.setValue(int(wt.get("opacity", 80)))
        self.wm_txt_font_edit.setCurrentText(wt.get("font_family", "Arial"))
        font_color = wt.get("font_color", "#FFFFFF")
        self._set_color_preset_from_hex(self.wm_txt_color_preset_cb, font_color)
        self.wm_txt_size_sp.setValue(int(wt.get("font_size", 24)))
        fw = wt.get("font_weight", "bold")
        self.wm_txt_weight_cb.setCurrentText(fw if fw in ["normal", "bold"] else "bold")
        fs = wt.get("font_style", "normal")
        self.wm_txt_style_cb.setCurrentText(fs if fs in ["normal", "italic"] else "normal")
        rs = str(wt.get("render_style", "normal") or "normal").strip().lower()
        self.wm_txt_render_style_cb.setCurrentText(
            rs if rs in ["normal", "outline_hollow", "outline_shadow"] else "normal"
        )
        self.wm_txt_shadow_opacity_sl.setValue(int(wt.get("shadow_opacity", 75)))
        self.wm_txt_shadow_offset_sp.setValue(int(wt.get("shadow_offset", 2)))
        self.wm_txt_spacing_sp.setValue(int(wt.get("letter_spacing", 0)))

        wl = c.watermark_logo
        self.wm_logo_enable_btn.setChecked(bool(wl.get("enabled", False)))
        self._apply_toggle_style(self.wm_logo_enable_btn)
        self.wm_logo_path_edit.setText(wl.get("path", ""))
        logo_pos = wl.get("position", "TopLeft")
        if logo_pos in pos_list:
            self.wm_logo_pos_cb.setCurrentText(logo_pos)
        self.wm_logo_opacity_sl.setValue(int(wl.get("opacity", 80)))

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
             " border-radius:4px; padding:6px 16px; border:1px solid rgba(67,181,129,0.75); }"
             "QPushButton:hover { background:#236e23; border-color:#43B581; }")
            if on else
            ("QPushButton { background:#2a2a2a; color:#9AA6B2; font-weight:bold;"
             " border-radius:4px; padding:6px 16px; border:1px solid rgba(255,255,255,0.22); }"
             "QPushButton:hover { background:#333; border-color:rgba(255,255,255,0.35); }")
        )

    def _on_wm_enable_change(self):
        pass  # Future: could show/hide watermark sub-sections

    def _browse_logo(self):
        from PyQt5.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Logo File", "",
            "Image Files (*.png *.jpg *.jpeg *.webp *.bmp *.svg *.gif);;All Files (*)"
        )
        if path:
            self.wm_logo_path_edit.setText(path)

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
            "watermark_enabled":   self.wm_enable_btn.isChecked(),
            "watermark_text": {
                "enabled":        self.wm_txt_enable_btn.isChecked(),
                "text":           self.wm_text_edit.text().strip(),
                "position":       self.wm_txt_pos_cb.currentText(),
                "opacity":        self.wm_txt_opacity_sl.value(),
                "font_family":    self.wm_txt_font_edit.currentText().strip() or "Arial",
                "font_color":     str(self.wm_txt_color_preset_cb.currentData() or "#FFFFFF"),
                "font_size":      self.wm_txt_size_sp.value(),
                "font_weight":    self.wm_txt_weight_cb.currentText(),
                "font_style":     self.wm_txt_style_cb.currentText(),
                "render_style":   self.wm_txt_render_style_cb.currentText(),
                "shadow_opacity": self.wm_txt_shadow_opacity_sl.value(),
                "shadow_offset":  self.wm_txt_shadow_offset_sp.value(),
                "letter_spacing": self.wm_txt_spacing_sp.value(),
            },
            "watermark_logo": {
                "enabled":  self.wm_logo_enable_btn.isChecked(),
                "path":     self.wm_logo_path_edit.text().strip(),
                "position": self.wm_logo_pos_cb.currentText(),
                "opacity":  self.wm_logo_opacity_sl.value(),
            },
        })
        self.config.save()
        self.accept()
