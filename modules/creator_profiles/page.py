"""
modules/creator_profiles/page.py
Downloading + Editing — Creator Profile System.

Layout:
  ┌─ Header ─────────────────────────────────────────────┐
  ├─ Action Bar (all buttons at TOP) ────────────────────┤
  ├─ Responsive Card Grid (scrollable) ──────────────────┤
  └──────────────────────────────────────────────────────┘
"""

import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List
from urllib.parse import parse_qs, urlparse

from PyQt5.QtCore import Qt, QEvent, QFileSystemWatcher, QTimer
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtWidgets import (
    QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QFrame,
    QGraphicsDropShadowEffect, QGridLayout,
    QHBoxLayout, QHeaderView,
    QCheckBox, QComboBox, QDoubleSpinBox,
    QLabel, QLineEdit, QMenu, QMessageBox, QPushButton,
    QScrollArea, QSizePolicy, QSlider,
    QSpinBox,
    QTableWidget, QTableWidgetItem, QTextEdit,
    QToolButton, QStyle, QVBoxLayout, QWidget,
)

from .creator_card import CreatorCard
from .config_manager import CreatorConfig
from .queue_manager import CreatorQueueManager

# ── Theme constants ───────────────────────────────────────────────────────────
_BG        = "#050712"
_BG_PANEL  = "#0d1117"
_BG_CARD   = "#161b22"
_CYAN      = "#00d4ff"
_GREEN     = "#43B581"
_RED       = "#E74C3C"
_GOLD      = "#ffd700"
_WARN      = "#F39C12"
_BORDER    = "rgba(0,212,255,0.2)"
_MIN_CARD  = 360     # keep cards wide enough so controls don't get squeezed
_MAX_COLS  = 4

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


def _abtn(text: str, fg: str, bg: str, border: str = None) -> QPushButton:
    """Action bar button — matches app button style."""
    bc = border or f"rgba({','.join(str(int(fg.lstrip('#')[i:i+2],16)) for i in (0,2,4))},0.45)"
    b = QPushButton(text)
    b.setStyleSheet(
        f"QPushButton {{"
        f"  color:{fg}; background:#161b22;"
        f"  border:1px solid {bc};"
        f"  border-radius:5px; padding:6px 14px;"
        f"  font-weight:bold; font-size:12px;"
        f"}}"
        f"QPushButton:hover {{ background:#1c2128; border-color:{fg}; }}"
        f"QPushButton:pressed {{ background:rgba(255,255,255,0.12); }}"
    )
    return b


def _vsep() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.VLine)
    f.setFixedHeight(22)
    f.setStyleSheet("background:rgba(255,255,255,0.1); border:none; max-width:1px;")
    return f


def _hdiv() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    f.setStyleSheet(f"background:{_BORDER}; border:none; max-height:1px;")
    return f


# ── helpers ──────────────────────────────────────────────────────────────────

def _links_root() -> Path:
    return Path.home() / "Desktop" / "Links Grabber"


def _preset_names() -> List[str]:
    names: List[str] = []
    for d in ["presets/system", "presets/user", "presets/imported"]:
        p = Path(d)
        if not p.exists():
            continue
        for f in p.glob("*.json"):
            name = f.stem.replace(".preset", "")
            if name not in names:
                names.append(name)
    return names


def _scan_folders(root: Path) -> List[Path]:
    """Return creator folders: direct children + one level deeper for platform dirs."""
    results: List[Path] = []
    if not root.exists():
        return results
    try:
        for item in sorted(root.iterdir()):
            if not item.is_dir() or item.name.startswith("."):
                continue
            has_links  = any(item.glob("*links*.txt")) or any(item.glob("*.txt"))
            has_config = (item / "creator_config.json").exists()
            child_dirs = [c for c in item.iterdir() if c.is_dir() and not c.name.startswith(".")]

            if has_links or has_config or not child_dirs:
                results.append(item)
            else:
                # Platform-style folder (Facebook/, YouTube/…) — go one deeper
                for sub in sorted(child_dirs):
                    results.append(sub)
    except PermissionError:
        pass
    return results


_RESERVED_SEGMENTS = {
    "reel", "reels", "video", "videos", "featured", "watch", "shorts",
    "posts", "post", "p", "tv", "stories", "story", "about", "photos",
    "photo", "live", "clips",
}


def _safe_folder_name(name: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]+', "_", (name or "").strip())
    cleaned = cleaned.strip(". ").replace(" ", "_")
    return cleaned or "creator"


def _suggest_folder_name_from_url(url: str) -> str:
    """Extract a stable folder name from a creator URL (platform aware)."""
    try:
        parsed = urlparse((url or "").strip())
        host = (parsed.netloc or "").lower().replace("www.", "")
        parts = [p for p in parsed.path.split("/") if p]
        lower_parts = [p.lower() for p in parts]

        def pick_non_reserved(items: List[str]) -> str:
            for p in items:
                if p.lower() not in _RESERVED_SEGMENTS:
                    return p
            return ""

        # Common handle format
        for p in parts:
            if p.startswith("@") and len(p) > 1:
                return _safe_folder_name(p[1:])

        if "facebook.com" in host:
            if lower_parts and lower_parts[0] == "profile.php":
                q = parse_qs(parsed.query or "")
                profile_id = (q.get("id") or [""])[0].strip()
                if profile_id:
                    return _safe_folder_name(f"fb_{profile_id}")
            if parts:
                return _safe_folder_name(pick_non_reserved(parts) or parts[0])

        if "youtube.com" in host or "youtu.be" in host:
            if len(parts) >= 2 and lower_parts[0] in {"channel", "c", "user"}:
                return _safe_folder_name(parts[1])
            if parts:
                return _safe_folder_name(pick_non_reserved(parts) or parts[-1])

        if "instagram.com" in host and parts:
            name = pick_non_reserved(parts)
            if name:
                return _safe_folder_name(name.lstrip("@"))

        if "tiktok.com" in host and parts:
            for p in parts:
                if p.startswith("@") and len(p) > 1:
                    return _safe_folder_name(p[1:])
            return _safe_folder_name(pick_non_reserved(parts) or parts[0])

        # Generic fallback
        if parts:
            return _safe_folder_name(pick_non_reserved(parts) or parts[-1])
    except Exception:
        pass
    return "creator"


def _canonical_creator_key(url: str) -> str:
    """Canonical key used to identify same creator across custom folder names."""
    normalized = CreatorConfig._normalize_profile_url(url) or (url or "").strip()
    try:
        parsed = urlparse(normalized)
        host = (parsed.netloc or "").lower().replace("www.", "")
        path = "/".join([p for p in parsed.path.split("/") if p]).lower()
        query = parse_qs(parsed.query or "")

        if "profile.php" in path:
            pid = (query.get("id") or [""])[0].strip()
            if pid:
                return f"{host}/profile.php?id={pid.lower()}"
        return f"{host}/{path}".rstrip("/")
    except Exception:
        return normalized.lower().rstrip("/")


def _existing_creator_folder_map(root: Path) -> Dict[str, Path]:
    """Map canonical creator key -> existing folder path from creator_config.json files."""
    mapping: Dict[str, Path] = {}
    if not root.exists():
        return mapping
    for cfg_file in root.rglob("creator_config.json"):
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            key = _canonical_creator_key(data.get("creator_url", ""))
            if key:
                mapping[key] = cfg_file.parent
        except Exception:
            continue
    return mapping


# ── Single Add Dialog ────────────────────────────────────────────────────────

class AddCreatorDialog(QDialog):

    _SS = """
        QDialog  { background:#0d1117; color:white; }
        QLabel   { color:rgba(255,255,255,0.82); background:transparent; border:none; }
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
            background:#161b22; color:white;
            border:1px solid rgba(0,212,255,0.28);
            border-radius:4px; padding:6px;
        }
        QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
            border-color:#00d4ff;
        }
        QComboBox::drop-down { border:none; }
        QComboBox QAbstractItemView {
            background:#161b22; color:white; border:1px solid #00d4ff;
            selection-background-color:rgba(0,212,255,0.2);
        }
        QCheckBox {
            color:#e8f1ff;
            spacing:10px;
            font-size:13px;
            font-weight:600;
        }
        QCheckBox::indicator {
            width:18px;
            height:18px;
        }
        QSlider::groove:horizontal {
            background:rgba(0,212,255,0.15); height:4px; border-radius:2px;
        }
        QSlider::handle:horizontal {
            background:#00d4ff; width:14px; height:14px;
            margin:-5px 0; border-radius:7px;
        }
        QSlider::sub-page:horizontal { background:rgba(0,212,255,0.5); border-radius:2px; }
        QPushButton {
            background:#161b22; color:white;
            border:1px solid rgba(0,212,255,0.3);
            border-radius:5px; padding:7px 18px; font-weight:bold;
        }
        QPushButton:hover { background:#1c2128; border-color:#00d4ff; }
    """

    def __init__(self, root: Path, preset_names: List[str], parent=None):
        super().__init__(parent)
        self.root = root
        self.preset_names = preset_names
        self.created_folder: Path = None
        self.setWindowTitle("Add Creator")
        self.setMinimumWidth(620)
        self.resize(640, 700)
        self.setStyleSheet(self._SS)
        self._build()

    def _build(self):
        # ── Outer layout: scroll + fixed buttons ──────────────────────────
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 12)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.NoFrame)
        scroll.setStyleSheet(
            "QScrollArea { background:#0d1117; border:none; }"
            "QScrollBar:vertical { background:#0d1117; width:8px; border-radius:4px; }"
            "QScrollBar::handle:vertical { background:rgba(0,212,255,0.3); border-radius:4px; min-height:20px; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0px; }"
        )
        outer.addWidget(scroll, 1)

        container = QWidget()
        container.setStyleSheet("background:#0d1117;")
        scroll.setWidget(container)

        v = QVBoxLayout(container)
        v.setContentsMargins(24, 22, 24, 12)
        v.setSpacing(14)

        t = QLabel("➕  Single Creator")
        t.setFont(QFont("Segoe UI", 14, QFont.Bold))
        t.setStyleSheet(f"color:{_CYAN}; background:transparent; border:none;")
        v.addWidget(t)

        form = QFormLayout()
        form.setSpacing(10)
        self.url_edit  = QLineEdit()
        self.url_edit.setPlaceholderText(
            "https://www.tiktok.com/@username   or   https://youtube.com/@channel"
        )
        self.url_edit.textChanged.connect(self._suggest)
        form.addRow("Creator URL:", self.url_edit)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Auto-filled from URL  (edit if needed)")
        form.addRow("Folder Name:", self.name_edit)

        self.n_spin = QSpinBox()
        self.n_spin.setRange(1, 500)
        self.n_spin.setValue(5)
        form.addRow("N Videos:", self.n_spin)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["None", "Preset", "Split"])
        self.mode_combo.currentIndexChanged.connect(self._on_mode_change)
        form.addRow("Editing Mode:", self.mode_combo)

        self.preset_combo = QComboBox()
        self.preset_combo.addItems(self.preset_names or ["- no presets -"])
        form.addRow("Preset:", self.preset_combo)

        self.split_spin = QDoubleSpinBox()
        self.split_spin.setRange(1.0, 3600.0)
        self.split_spin.setValue(15.0)
        self.split_spin.setSuffix(" s")
        form.addRow("Split Duration:", self.split_spin)

        self.dup_check = QCheckBox("Skip already downloaded")
        self.dup_check.setChecked(True)
        form.addRow("Duplication:", self.dup_check)

        self.pop_check = QCheckBox("Use popular fallback")
        self.pop_check.setChecked(True)
        form.addRow("Popular Fallback:", self.pop_check)

        self.rand_check = QCheckBox("Randomize links")
        self.rand_check.setChecked(False)
        form.addRow("Randomize:", self.rand_check)

        self.keep_original_check = QCheckBox("Keep original video after editing")
        self.keep_original_check.setChecked(True)
        form.addRow("Original File:", self.keep_original_check)

        self.delete_before_dl_check = QCheckBox("Delete existing media before downloading")
        self.delete_before_dl_check.setChecked(False)
        form.addRow("Cleanup:", self.delete_before_dl_check)

        self._on_mode_change()
        v.addLayout(form)

        # ── WaterMark Section ──────────────────────────────────────────────
        wm_div = QFrame()
        wm_div.setFrameShape(QFrame.HLine)
        wm_div.setStyleSheet("background:rgba(0,212,255,0.15); border:none; max-height:1px;")
        v.addWidget(wm_div)

        wm_title = QLabel("💧  WaterMark Settings")
        wm_title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        wm_title.setStyleSheet(f"color:{_CYAN}; background:transparent; border:none;")
        v.addWidget(wm_title)

        wm_form = QFormLayout()
        wm_form.setSpacing(9)
        wm_form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        # Global enable
        wm_en_row = QHBoxLayout()
        self.wm_enable_btn = QPushButton("OFF")
        self.wm_enable_btn.setCheckable(True)
        self.wm_enable_btn.setFixedWidth(68)
        self.wm_enable_btn.clicked.connect(lambda: self._toggle_style(self.wm_enable_btn))
        wm_en_row.addWidget(self.wm_enable_btn); wm_en_row.addStretch()
        wm_en_w = QWidget(); wm_en_w.setStyleSheet("background:transparent; border:none;"); wm_en_w.setLayout(wm_en_row)
        wm_form.addRow("WaterMark:", wm_en_w)

        # Text watermark header
        txt_hdr = QLabel("  Text Watermark")
        txt_hdr.setStyleSheet("color:#aaa; font-size:11px; font-weight:bold; background:transparent; border:none;")
        wm_form.addRow(txt_hdr)

        txt_en_row = QHBoxLayout()
        self.wm_txt_enable_btn = QPushButton("OFF")
        self.wm_txt_enable_btn.setCheckable(True)
        self.wm_txt_enable_btn.setFixedWidth(68)
        self.wm_txt_enable_btn.clicked.connect(lambda: self._toggle_style(self.wm_txt_enable_btn))
        txt_en_row.addWidget(self.wm_txt_enable_btn); txt_en_row.addStretch()
        txt_en_w = QWidget(); txt_en_w.setStyleSheet("background:transparent; border:none;"); txt_en_w.setLayout(txt_en_row)
        wm_form.addRow("  Enable Text:", txt_en_w)

        self.wm_text_edit = QLineEdit()
        self.wm_text_edit.setPlaceholderText("Leave blank to use @folderName")
        wm_form.addRow("  Text:", self.wm_text_edit)

        self.wm_txt_pos_cb = QComboBox()
        self.wm_txt_pos_cb.addItems(["TopLeft", "TopRight", "BottomLeft", "BottomRight", "Center", "AnimateAround"])
        self.wm_txt_pos_cb.setCurrentText("BottomRight")
        self.wm_txt_pos_cb.setFixedWidth(150)
        wm_form.addRow("  Position:", self.wm_txt_pos_cb)

        self.wm_txt_opacity_sl = QSlider(Qt.Horizontal)
        self.wm_txt_opacity_sl.setRange(0, 100); self.wm_txt_opacity_sl.setValue(80)
        self.wm_txt_opacity_lbl = QLabel("80%")
        self.wm_txt_opacity_lbl.setStyleSheet("color:white; background:transparent; border:none; min-width:32px;")
        self.wm_txt_opacity_sl.valueChanged.connect(lambda v: self.wm_txt_opacity_lbl.setText(f"{v}%"))
        op_row = QHBoxLayout(); op_row.addWidget(self.wm_txt_opacity_sl); op_row.addWidget(self.wm_txt_opacity_lbl)
        op_w = QWidget(); op_w.setStyleSheet("background:transparent; border:none;"); op_w.setLayout(op_row)
        wm_form.addRow("  Opacity:", op_w)

        self.wm_txt_font_edit = QComboBox()
        self.wm_txt_font_edit.setEditable(True)
        self.wm_txt_font_edit.setFixedWidth(150)
        self._init_wm_font_presets(self.wm_txt_font_edit)
        wm_form.addRow("  Font Family:", self.wm_txt_font_edit)

        self.wm_txt_color_preset_cb = QComboBox()
        self.wm_txt_color_preset_cb.setFixedWidth(248)
        self._init_wm_color_presets(self.wm_txt_color_preset_cb)
        wm_form.addRow("  Font Color:", self.wm_txt_color_preset_cb)

        self.wm_txt_size_sp = QSpinBox()
        self.wm_txt_size_sp.setRange(8, 200); self.wm_txt_size_sp.setValue(24); self.wm_txt_size_sp.setFixedWidth(75)
        wm_form.addRow("  Font Size:", self.wm_txt_size_sp)

        self.wm_txt_weight_cb = QComboBox()
        self.wm_txt_weight_cb.addItems(["normal", "bold"]); self.wm_txt_weight_cb.setCurrentText("bold")
        self.wm_txt_weight_cb.setFixedWidth(95)
        wm_form.addRow("  Font Weight:", self.wm_txt_weight_cb)

        self.wm_txt_style_cb = QComboBox()
        self.wm_txt_style_cb.addItems(["normal", "italic"]); self.wm_txt_style_cb.setFixedWidth(95)
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
        self.wm_txt_shadow_opacity_lbl.setStyleSheet("color:white; background:transparent; border:none; min-width:32px;")
        self.wm_txt_shadow_opacity_sl.valueChanged.connect(lambda v: self.wm_txt_shadow_opacity_lbl.setText(f"{v}%"))
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
        self.wm_txt_shadow_offset_sp.setFixedWidth(75)
        wm_form.addRow("  Shadow Offset:", self.wm_txt_shadow_offset_sp)

        self.wm_txt_spacing_sp = QSpinBox()
        self.wm_txt_spacing_sp.setRange(0, 50); self.wm_txt_spacing_sp.setValue(0); self.wm_txt_spacing_sp.setFixedWidth(75)
        wm_form.addRow("  Letter Spacing:", self.wm_txt_spacing_sp)

        # Logo watermark header
        logo_hdr = QLabel("  Logo Watermark")
        logo_hdr.setStyleSheet("color:#aaa; font-size:11px; font-weight:bold; background:transparent; border:none;")
        wm_form.addRow(logo_hdr)

        logo_en_row = QHBoxLayout()
        self.wm_logo_enable_btn = QPushButton("OFF")
        self.wm_logo_enable_btn.setCheckable(True)
        self.wm_logo_enable_btn.setFixedWidth(68)
        self.wm_logo_enable_btn.clicked.connect(lambda: self._toggle_style(self.wm_logo_enable_btn))
        logo_en_row.addWidget(self.wm_logo_enable_btn); logo_en_row.addStretch()
        logo_en_w = QWidget(); logo_en_w.setStyleSheet("background:transparent; border:none;"); logo_en_w.setLayout(logo_en_row)
        wm_form.addRow("  Enable Logo:", logo_en_w)

        logo_path_row = QHBoxLayout()
        self.wm_logo_path_edit = QLineEdit()
        self.wm_logo_path_edit.setPlaceholderText("Leave blank to auto-detect logo.* in folder")
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
        logo_path_row.addWidget(self.wm_logo_path_edit); logo_path_row.addWidget(logo_browse_btn)
        logo_path_w = QWidget(); logo_path_w.setStyleSheet("background:transparent; border:none;"); logo_path_w.setLayout(logo_path_row)
        wm_form.addRow("  Logo Path:", logo_path_w)

        self.wm_logo_pos_cb = QComboBox()
        self.wm_logo_pos_cb.addItems(["TopLeft", "TopRight", "BottomLeft", "BottomRight", "Center", "AnimateAround"])
        self.wm_logo_pos_cb.setFixedWidth(150)
        wm_form.addRow("  Position:", self.wm_logo_pos_cb)

        self.wm_logo_opacity_sl = QSlider(Qt.Horizontal)
        self.wm_logo_opacity_sl.setRange(0, 100); self.wm_logo_opacity_sl.setValue(80)
        self.wm_logo_opacity_lbl = QLabel("80%")
        self.wm_logo_opacity_lbl.setStyleSheet("color:white; background:transparent; border:none; min-width:32px;")
        self.wm_logo_opacity_sl.valueChanged.connect(lambda v: self.wm_logo_opacity_lbl.setText(f"{v}%"))
        lop_row = QHBoxLayout(); lop_row.addWidget(self.wm_logo_opacity_sl); lop_row.addWidget(self.wm_logo_opacity_lbl)
        lop_w = QWidget(); lop_w.setStyleSheet("background:transparent; border:none;"); lop_w.setLayout(lop_row)
        wm_form.addRow("  Opacity:", lop_w)
        self._set_color_preset_from_hex(self.wm_txt_color_preset_cb, "#FFFFFF")

        v.addLayout(wm_form)
        v.addStretch(1)

        # ── Fixed buttons outside scroll ───────────────────────────────────
        note = QLabel(
            "Folder created at:  Desktop / Links Grabber / <name>\n"
            "Then click ✏ Edit on the card to reconfigure settings."
        )
        note.setStyleSheet("color:rgba(255,255,255,0.35); font-size:11px;"
                           " background:transparent; border:none;")
        note.setContentsMargins(24, 4, 24, 0)
        outer.addWidget(note)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Ok).setText("Create")
        btns.button(QDialogButtonBox.Ok).setStyleSheet(
            "background:#1a5c1a; color:white; font-weight:bold;"
            " padding:7px 22px; border-radius:5px;"
        )
        btns.button(QDialogButtonBox.Cancel).setStyleSheet(
            "background:#2a1414; color:white; font-weight:bold;"
            " padding:7px 22px; border-radius:5px;"
        )
        btns.accepted.connect(self._create)
        btns.rejected.connect(self.reject)
        btn_w = QWidget(); btn_w.setStyleSheet("background:#0d1117; border:none;")
        btn_layout = QHBoxLayout(btn_w); btn_layout.setContentsMargins(24, 6, 24, 0)
        btn_layout.addWidget(btns)
        outer.addWidget(btn_w)

    def _suggest(self, url: str):
        self.name_edit.setText(_suggest_folder_name_from_url(url))

    def _on_mode_change(self):
        idx = self.mode_combo.currentIndex()
        self.preset_combo.setVisible(idx == 1)
        self.split_spin.setVisible(idx == 2)

    @staticmethod
    def _toggle_style(btn: QPushButton):
        on = btn.isChecked()
        btn.setText("ON" if on else "OFF")
        btn.setStyleSheet(
            ("QPushButton { background:#1a5c1a; color:white; font-weight:bold;"
             " border-radius:4px; padding:4px 12px; border:none; }"
             "QPushButton:hover { background:#236e23; }")
            if on else
            ("QPushButton { background:#2a2a2a; color:#777; font-weight:bold;"
             " border-radius:4px; padding:4px 12px; border:none; }"
             "QPushButton:hover { background:#333; }")
        )

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

    def _browse_logo(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Logo File", "",
            "Image Files (*.png *.jpg *.jpeg *.webp *.bmp *.svg *.gif);;All Files (*)"
        )
        if path:
            self.wm_logo_path_edit.setText(path)

    def _collect_settings(self) -> Dict[str, object]:
        mode = ["none", "preset", "split"][self.mode_combo.currentIndex()]
        return {
            "n_videos": self.n_spin.value(),
            "editing_mode": mode,
            "preset_name": self.preset_combo.currentText(),
            "split_duration": self.split_spin.value(),
            "duplication_control": self.dup_check.isChecked(),
            "popular_fallback": self.pop_check.isChecked(),
            "prefer_popular_first": False,
            "randomize_links": self.rand_check.isChecked(),
            "keep_original_after_edit": self.keep_original_check.isChecked(),
            "delete_before_download": self.delete_before_dl_check.isChecked(),
            "watermark_enabled": self.wm_enable_btn.isChecked(),
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
        }

    def _create(self):
        url  = self.url_edit.text().strip()
        name = self.name_edit.text().strip()
        if not url:
            QMessageBox.warning(self, "Required", "Please enter the Creator URL.")
            return
        if not name:
            QMessageBox.warning(self, "Required", "Please enter a Folder Name.")
            return
        normalized_url = CreatorConfig._normalize_profile_url(url) or url
        creator_key = _canonical_creator_key(normalized_url)
        existing_by_key = _existing_creator_folder_map(self.root)
        folder = existing_by_key.get(creator_key, self.root / name)
        try:
            folder.mkdir(parents=True, exist_ok=True)
            cfg = CreatorConfig(folder)
            cfg.data["creator_url"] = normalized_url
            cfg.data.update(self._collect_settings())
            cfg.save()
            self.created_folder = folder
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create folder:\n{e}")


# ── Bulk Add Dialog ──────────────────────────────────────────────────────────

class BulkAddDialog(QDialog):
    """Paste multiple URLs → preview table → create all at once."""

    _SS = """
        QDialog  { background:#0d1117; color:white; }
        QLabel   { color:rgba(255,255,255,0.82); background:transparent; border:none; }
        QTextEdit, QTableWidget {
            background:#161b22; color:white;
            border:1px solid rgba(0,212,255,0.25);
            border-radius:4px;
        }
        QTableWidget {
            alternate-background-color: #141b28;
            gridline-color: rgba(0, 212, 255, 0.20);
        }
        QHeaderView::section {
            background:#0b1323; color:#00d4ff;
            border:1px solid rgba(0,212,255,0.2);
            padding:8px 10px; font-weight:bold;
        }
        QTableWidget::item { padding:8px 10px; border: none; }
        QTableWidget::item:selected {
            background:rgba(0,212,255,0.28);
            color:#ffffff;
        }
        QTableWidget::item:selected:active {
            background:rgba(0,212,255,0.34);
            color:#ffffff;
        }
        QTableWidget QLineEdit {
            background:#0f1726;
            color:#ffffff;
            border:1px solid #00d4ff;
            border-radius:4px;
            padding:6px 8px;
            min-height:28px;
            font-size:13px;
            selection-background-color:rgba(0,212,255,0.35);
            selection-color:#ffffff;
        }
        QSpinBox, QDoubleSpinBox, QComboBox {
            background:#0f1726;
            color:#ffffff;
            border:1px solid rgba(0,212,255,0.35);
            border-radius:4px;
            padding:6px 8px;
            min-height: 26px;
        }
        QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
            border:1px solid #00d4ff;
        }
        QCheckBox {
            color:#e8f1ff;
            spacing:10px;
            font-size:13px;
            font-weight:600;
        }
        QCheckBox::indicator {
            width:18px;
            height:18px;
        }
        QSlider::groove:horizontal {
            background:rgba(0,212,255,0.15); height:4px; border-radius:2px;
        }
        QSlider::handle:horizontal {
            background:#00d4ff; width:14px; height:14px;
            margin:-5px 0; border-radius:7px;
        }
        QSlider::sub-page:horizontal { background:rgba(0,212,255,0.5); border-radius:2px; }
        QPushButton {
            background:#161b22; color:white;
            border:1px solid rgba(0,212,255,0.3);
            border-radius:5px; padding:7px 18px; font-weight:bold;
        }
        QPushButton:hover { background:#1c2128; border-color:#00d4ff; }
    """

    def __init__(self, root: Path, preset_names: List[str], parent=None):
        super().__init__(parent)
        self.root = root
        self.preset_names = preset_names
        self.created_count = 0
        self.setWindowTitle("Bulk Add Creators")
        self.setMinimumSize(900, 700)
        self.resize(980, 760)
        self.setSizeGripEnabled(True)
        self.setStyleSheet(self._SS)
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 12)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.NoFrame)
        scroll.setStyleSheet(
            "QScrollArea { background:#0d1117; border:none; }"
            "QScrollBar:vertical { background:#0d1117; width:8px; border-radius:4px; }"
            "QScrollBar::handle:vertical { background:rgba(0,212,255,0.3); border-radius:4px; min-height:20px; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0px; }"
        )
        outer.addWidget(scroll, 1)

        container = QWidget()
        container.setStyleSheet("background:#0d1117;")
        scroll.setWidget(container)

        v = QVBoxLayout(container)
        v.setContentsMargins(22, 20, 22, 14)
        v.setSpacing(12)

        t = QLabel("📋  Bulk Add Creators")
        t.setFont(QFont("Segoe UI", 14, QFont.Bold))
        t.setStyleSheet(f"color:{_CYAN}; background:transparent; border:none;")
        v.addWidget(t)

        inst = QLabel("Paste one creator URL per line, then click  Parse URLs  to preview.")
        inst.setStyleSheet("color:rgba(255,255,255,0.5); font-size:12px;"
                           " background:transparent; border:none;")
        v.addWidget(inst)

        self.url_box = QTextEdit()
        self.url_box.setPlaceholderText(
            "https://www.tiktok.com/@creator1\n"
            "https://youtube.com/@channel2\n"
            "https://instagram.com/user3"
        )
        self.url_box.setMaximumHeight(130)
        v.addWidget(self.url_box)

        parse_btn = QPushButton("Parse URLs  →")
        parse_btn.setStyleSheet(
            f"background:#0a1628; color:{_CYAN};"
            f" border:1px solid rgba(0,212,255,0.4); border-radius:5px;"
            " padding:6px 16px; font-weight:bold;"
        )
        parse_btn.clicked.connect(self._parse)
        v.addWidget(parse_btn, alignment=Qt.AlignLeft)

        preview_lbl = QLabel("Preview (you can type custom folder name per URL):")
        preview_lbl.setStyleSheet(
            "color:rgba(255,255,255,0.6); font-size:12px; font-weight:bold;"
            " background:transparent; border:none;"
        )
        v.addWidget(preview_lbl)

        preview_hint = QLabel(
            "Suggested Name is read-only. Edit only Custom Name column if you want your own folder naming."
        )
        preview_hint.setStyleSheet(
            "color:rgba(255,255,255,0.46); font-size:11px; background:transparent; border:none;"
        )
        preview_hint.setWordWrap(True)
        v.addWidget(preview_hint)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Creator URL", "Suggested Name", "Custom Name (Optional)"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setMinimumSectionSize(120)
        header.setFixedHeight(40)
        self.table.setColumnWidth(1, 200)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(38)
        self.table.setEditTriggers(
            QTableWidget.DoubleClicked
            | QTableWidget.SelectedClicked
            | QTableWidget.EditKeyPressed
            | QTableWidget.AnyKeyPressed
        )
        self.table.setWordWrap(False)
        self.table.setTextElideMode(Qt.ElideMiddle)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        visible_rows = 10
        row_h = self.table.verticalHeader().defaultSectionSize() or 34
        header_h = self.table.horizontalHeader().height() or 36
        frame_h = self.table.frameWidth() * 2
        self.table.setMinimumHeight(frame_h + header_h + (row_h * visible_rows) + 2)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        v.addWidget(self.table)

        settings_label = QLabel("Default settings for all creators in this batch:")
        settings_label.setStyleSheet(
            "color:rgba(255,255,255,0.6); font-size:12px; font-weight:bold;"
            " background:transparent; border:none;"
        )
        v.addWidget(settings_label)

        self.n_spin = QSpinBox()
        self.n_spin.setRange(1, 500)
        self.n_spin.setValue(5)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["None", "Preset", "Split"])
        self.mode_combo.currentIndexChanged.connect(self._on_mode_change)
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(self.preset_names or ["- no presets -"])
        self.split_spin = QDoubleSpinBox()
        self.split_spin.setRange(1.0, 3600.0)
        self.split_spin.setValue(15.0)
        self.split_spin.setSuffix(" s")
        self.dup_check = QCheckBox("Skip already downloaded")
        self.dup_check.setChecked(True)
        self.pop_check = QCheckBox("Use popular fallback")
        self.pop_check.setChecked(True)
        self.rand_check = QCheckBox("Randomize links")
        self.rand_check.setChecked(False)
        self.keep_original_check = QCheckBox("Keep original video after editing")
        self.keep_original_check.setChecked(True)
        self.delete_before_dl_check = QCheckBox("Delete existing media before downloading")
        self.delete_before_dl_check.setChecked(False)

        settings_form = QFormLayout()
        settings_form.setSpacing(8)
        settings_form.setHorizontalSpacing(20)
        settings_form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        settings_form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        settings_form.addRow("N Videos:", self.n_spin)
        settings_form.addRow("Editing Mode:", self.mode_combo)
        settings_form.addRow("Preset:", self.preset_combo)
        settings_form.addRow("Split Duration:", self.split_spin)
        settings_form.addRow("Duplication:", self.dup_check)
        settings_form.addRow("Popular Fallback:", self.pop_check)
        settings_form.addRow("Randomize:", self.rand_check)
        settings_form.addRow("Original File:", self.keep_original_check)
        settings_form.addRow("Cleanup:", self.delete_before_dl_check)
        v.addLayout(settings_form)
        self._on_mode_change()

        # ── WaterMark Section ──────────────────────────────────────────────
        wm_div = QFrame()
        wm_div.setFrameShape(QFrame.HLine)
        wm_div.setStyleSheet("background:rgba(0,212,255,0.15); border:none; max-height:1px;")
        v.addWidget(wm_div)

        wm_title = QLabel("💧  WaterMark Settings  (applied to all creators in this batch)")
        wm_title.setStyleSheet(f"color:{_CYAN}; font-size:12px; font-weight:bold; background:transparent; border:none;")
        v.addWidget(wm_title)

        wm_panel = QFrame()
        wm_panel.setStyleSheet(
            "QFrame { background:#111827; border:1px solid rgba(0,212,255,0.22); border-radius:8px; }"
        )
        wm_wrap = QVBoxLayout(wm_panel)
        wm_wrap.setContentsMargins(12, 10, 12, 10)
        wm_wrap.setSpacing(8)

        def _wm_tag(text: str) -> QLabel:
            lbl = QLabel(text)
            lbl.setStyleSheet(
                "color:rgba(255,255,255,0.72); font-size:11px; font-weight:bold;"
                " background:transparent; border:none;"
            )
            return lbl

        # Toggle row
        self.wm_enable_btn = QPushButton("OFF")
        self.wm_enable_btn.setCheckable(True)
        self.wm_enable_btn.setFixedWidth(65)
        self.wm_enable_btn.clicked.connect(lambda: self._toggle_style(self.wm_enable_btn))

        self.wm_txt_enable_btn = QPushButton("OFF")
        self.wm_txt_enable_btn.setCheckable(True)
        self.wm_txt_enable_btn.setFixedWidth(65)
        self.wm_txt_enable_btn.clicked.connect(lambda: self._toggle_style(self.wm_txt_enable_btn))

        self.wm_logo_enable_btn = QPushButton("OFF")
        self.wm_logo_enable_btn.setCheckable(True)
        self.wm_logo_enable_btn.setFixedWidth(65)
        self.wm_logo_enable_btn.clicked.connect(lambda: self._toggle_style(self.wm_logo_enable_btn))

        toggle_row = QHBoxLayout()
        toggle_row.setContentsMargins(0, 0, 0, 0)
        toggle_row.setSpacing(10)
        toggle_row.addWidget(_wm_tag("WaterMark"))
        toggle_row.addWidget(self.wm_enable_btn)
        toggle_row.addSpacing(8)
        toggle_row.addWidget(_wm_tag("Text WM"))
        toggle_row.addWidget(self.wm_txt_enable_btn)
        toggle_row.addSpacing(8)
        toggle_row.addWidget(_wm_tag("Logo WM"))
        toggle_row.addWidget(self.wm_logo_enable_btn)
        toggle_row.addStretch()
        wm_wrap.addLayout(toggle_row)

        # Text row
        self.wm_text_edit = QLineEdit()
        self.wm_text_edit.setPlaceholderText("Leave blank to use @folderName")
        self.wm_text_edit.setMinimumWidth(240)

        self.wm_txt_pos_cb = QComboBox()
        self.wm_txt_pos_cb.addItems(["TopLeft", "TopRight", "BottomLeft", "BottomRight", "Center", "AnimateAround"])
        self.wm_txt_pos_cb.setCurrentText("BottomRight")
        self.wm_txt_pos_cb.setMinimumWidth(130)

        self.wm_txt_opacity_sl = QSlider(Qt.Horizontal)
        self.wm_txt_opacity_sl.setRange(0, 100)
        self.wm_txt_opacity_sl.setValue(80)
        self.wm_txt_opacity_lbl = QLabel("80%")
        self.wm_txt_opacity_lbl.setStyleSheet("color:white; background:transparent; border:none; min-width:32px;")
        self.wm_txt_opacity_sl.valueChanged.connect(lambda v: self.wm_txt_opacity_lbl.setText(f"{v}%"))
        op_row = QHBoxLayout()
        op_row.setContentsMargins(0, 0, 0, 0)
        op_row.setSpacing(6)
        op_row.addWidget(self.wm_txt_opacity_sl, 1)
        op_row.addWidget(self.wm_txt_opacity_lbl)
        op_w = QWidget()
        op_w.setStyleSheet("background:transparent; border:none;")
        op_w.setLayout(op_row)

        text_row = QHBoxLayout()
        text_row.setContentsMargins(0, 0, 0, 0)
        text_row.setSpacing(8)
        text_row.addWidget(_wm_tag("Text"))
        text_row.addWidget(self.wm_text_edit, 2)
        text_row.addWidget(_wm_tag("Position"))
        text_row.addWidget(self.wm_txt_pos_cb)
        text_row.addWidget(_wm_tag("Opacity"))
        text_row.addWidget(op_w, 2)
        wm_wrap.addLayout(text_row)

        # Text style row
        self.wm_txt_font_edit = QComboBox()
        self.wm_txt_font_edit.setEditable(True)
        self.wm_txt_font_edit.setMinimumWidth(140)
        self._init_wm_font_presets(self.wm_txt_font_edit)

        self.wm_txt_color_preset_cb = QComboBox()
        self.wm_txt_color_preset_cb.setMinimumWidth(200)
        self._init_wm_color_presets(self.wm_txt_color_preset_cb)

        self.wm_txt_size_sp = QSpinBox()
        self.wm_txt_size_sp.setRange(8, 200)
        self.wm_txt_size_sp.setValue(24)
        self.wm_txt_size_sp.setMaximumWidth(84)

        self.wm_txt_weight_cb = QComboBox()
        self.wm_txt_weight_cb.addItems(["normal", "bold"])
        self.wm_txt_weight_cb.setCurrentText("bold")
        self.wm_txt_weight_cb.setMinimumWidth(92)

        self.wm_txt_style_cb = QComboBox()
        self.wm_txt_style_cb.addItems(["normal", "italic"])
        self.wm_txt_style_cb.setMinimumWidth(92)

        self.wm_txt_render_style_cb = QComboBox()
        self.wm_txt_render_style_cb.addItems(
            ["normal", "outline_hollow", "outline_shadow"]
        )
        self.wm_txt_render_style_cb.setMinimumWidth(132)

        self.wm_txt_shadow_opacity_sl = QSlider(Qt.Horizontal)
        self.wm_txt_shadow_opacity_sl.setRange(0, 100)
        self.wm_txt_shadow_opacity_sl.setValue(75)
        self.wm_txt_shadow_opacity_lbl = QLabel("75%")
        self.wm_txt_shadow_opacity_lbl.setStyleSheet("color:white; background:transparent; border:none; min-width:32px;")
        self.wm_txt_shadow_opacity_sl.valueChanged.connect(lambda v: self.wm_txt_shadow_opacity_lbl.setText(f"{v}%"))
        shadow_op_row = QHBoxLayout()
        shadow_op_row.setContentsMargins(0, 0, 0, 0)
        shadow_op_row.setSpacing(6)
        shadow_op_row.addWidget(self.wm_txt_shadow_opacity_sl, 1)
        shadow_op_row.addWidget(self.wm_txt_shadow_opacity_lbl)
        shadow_op_w = QWidget()
        shadow_op_w.setStyleSheet("background:transparent; border:none;")
        shadow_op_w.setLayout(shadow_op_row)

        self.wm_txt_shadow_offset_sp = QSpinBox()
        self.wm_txt_shadow_offset_sp.setRange(0, 50)
        self.wm_txt_shadow_offset_sp.setValue(2)
        self.wm_txt_shadow_offset_sp.setMaximumWidth(84)

        self.wm_txt_spacing_sp = QSpinBox()
        self.wm_txt_spacing_sp.setRange(0, 50)
        self.wm_txt_spacing_sp.setValue(0)
        self.wm_txt_spacing_sp.setMaximumWidth(84)

        style_row = QHBoxLayout()
        style_row.setContentsMargins(0, 0, 0, 0)
        style_row.setSpacing(8)
        style_row.addWidget(_wm_tag("Font"))
        style_row.addWidget(self.wm_txt_font_edit)
        style_row.addWidget(_wm_tag("Color"))
        style_row.addWidget(self.wm_txt_color_preset_cb)
        style_row.addWidget(_wm_tag("Size"))
        style_row.addWidget(self.wm_txt_size_sp)
        style_row.addWidget(_wm_tag("Weight"))
        style_row.addWidget(self.wm_txt_weight_cb)
        style_row.addWidget(_wm_tag("Style"))
        style_row.addWidget(self.wm_txt_style_cb)
        style_row.addWidget(_wm_tag("Render"))
        style_row.addWidget(self.wm_txt_render_style_cb)
        style_row.addWidget(_wm_tag("Spacing"))
        style_row.addWidget(self.wm_txt_spacing_sp)
        style_row.addStretch()
        wm_wrap.addLayout(style_row)

        shadow_row = QHBoxLayout()
        shadow_row.setContentsMargins(0, 0, 0, 0)
        shadow_row.setSpacing(8)
        shadow_row.addWidget(_wm_tag("Shadow Opacity"))
        shadow_row.addWidget(shadow_op_w, 2)
        shadow_row.addWidget(_wm_tag("Shadow Offset"))
        shadow_row.addWidget(self.wm_txt_shadow_offset_sp)
        shadow_row.addStretch()
        wm_wrap.addLayout(shadow_row)

        # Logo row
        self.wm_logo_path_edit = QLineEdit()
        self.wm_logo_path_edit.setPlaceholderText("Leave blank to auto-detect logo.* in folder")
        self.wm_logo_path_edit.setMinimumWidth(240)
        logo_browse_btn = QToolButton()
        logo_browse_btn.setIcon(self.style().standardIcon(QStyle.SP_DirOpenIcon))
        logo_browse_btn.setFixedSize(30, 28)
        logo_browse_btn.setAutoRaise(True)
        logo_browse_btn.setStyleSheet(
            "QToolButton { background:#2a2410; border:1px solid rgba(222,191,7,0.7); border-radius:4px; }"
            "QToolButton:hover { background:#3a3216; border-color:#DEBF07; }"
        )
        logo_browse_btn.setToolTip("Select logo file")
        logo_browse_btn.clicked.connect(self._browse_logo)

        self.wm_logo_pos_cb = QComboBox()
        self.wm_logo_pos_cb.addItems(["TopLeft", "TopRight", "BottomLeft", "BottomRight", "Center", "AnimateAround"])
        self.wm_logo_pos_cb.setMinimumWidth(130)

        self.wm_logo_opacity_sl = QSlider(Qt.Horizontal)
        self.wm_logo_opacity_sl.setRange(0, 100)
        self.wm_logo_opacity_sl.setValue(80)
        self.wm_logo_opacity_lbl = QLabel("80%")
        self.wm_logo_opacity_lbl.setStyleSheet("color:white; background:transparent; border:none; min-width:32px;")
        self.wm_logo_opacity_sl.valueChanged.connect(lambda v: self.wm_logo_opacity_lbl.setText(f"{v}%"))
        lop_row = QHBoxLayout()
        lop_row.setContentsMargins(0, 0, 0, 0)
        lop_row.setSpacing(6)
        lop_row.addWidget(self.wm_logo_opacity_sl, 1)
        lop_row.addWidget(self.wm_logo_opacity_lbl)
        lop_w = QWidget()
        lop_w.setStyleSheet("background:transparent; border:none;")
        lop_w.setLayout(lop_row)

        logo_row = QHBoxLayout()
        logo_row.setContentsMargins(0, 0, 0, 0)
        logo_row.setSpacing(8)
        logo_row.addWidget(_wm_tag("Logo Path"))
        logo_row.addWidget(self.wm_logo_path_edit, 2)
        logo_row.addWidget(logo_browse_btn)
        logo_row.addWidget(_wm_tag("Position"))
        logo_row.addWidget(self.wm_logo_pos_cb)
        logo_row.addWidget(_wm_tag("Opacity"))
        logo_row.addWidget(lop_w, 2)
        wm_wrap.addLayout(logo_row)

        # Keep OFF buttons visually explicit from start.
        self._toggle_style(self.wm_enable_btn)
        self._toggle_style(self.wm_txt_enable_btn)
        self._toggle_style(self.wm_logo_enable_btn)
        self._set_color_preset_from_hex(self.wm_txt_color_preset_cb, "#FFFFFF")

        v.addWidget(wm_panel)
        v.addStretch(1)

        # Fixed footer buttons (outside scroll content)
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(22, 8, 22, 0)
        btn_row.setSpacing(8)
        create_btn = QPushButton("✅  Create All")
        create_btn.setStyleSheet(
            "background:#1a5c1a; color:white; font-weight:bold;"
            " padding:7px 22px; border-radius:5px;"
        )
        create_btn.clicked.connect(self._create_all)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(
            "background:#2a1414; color:white; font-weight:bold;"
            " padding:7px 22px; border-radius:5px;"
        )
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(create_btn)
        btn_row.addWidget(cancel_btn)
        btn_row.addStretch()
        outer.addLayout(btn_row)

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

    def _parse(self):
        text = self.url_box.toPlainText()
        raw_urls = [l.strip() for l in text.splitlines() if l.strip().startswith("http")]
        urls = []
        seen_keys = set()
        for u in raw_urls:
            key = _canonical_creator_key(u)
            if key and key in seen_keys:
                continue
            if key:
                seen_keys.add(key)
            urls.append(u)
        self.table.setRowCount(0)
        for url in urls:
            row = self.table.rowCount()
            self.table.insertRow(row)
            url_item = QTableWidgetItem(url)
            url_item.setFlags(url_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 0, url_item)

            suggested = _suggest_folder_name_from_url(url)
            suggested_item = QTableWidgetItem(suggested)
            suggested_item.setFlags(suggested_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 1, suggested_item)
            custom_item = QTableWidgetItem(suggested)
            self.table.setItem(row, 2, custom_item)

    def _on_mode_change(self):
        idx = self.mode_combo.currentIndex()
        self.preset_combo.setVisible(idx == 1)
        self.split_spin.setVisible(idx == 2)

    @staticmethod
    def _toggle_style(btn: QPushButton):
        on = btn.isChecked()
        btn.setText("ON" if on else "OFF")
        btn.setStyleSheet(
            ("QPushButton { background:#1a5c1a; color:white; font-weight:bold;"
             " border-radius:4px; padding:4px 12px; border:none; }"
             "QPushButton:hover { background:#236e23; }")
            if on else
            ("QPushButton { background:#2a2a2a; color:#777; font-weight:bold;"
             " border-radius:4px; padding:4px 12px; border:none; }"
             "QPushButton:hover { background:#333; }")
        )

    def _browse_logo(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Logo File", "",
            "Image Files (*.png *.jpg *.jpeg *.webp *.bmp *.svg *.gif);;All Files (*)"
        )
        if path:
            self.wm_logo_path_edit.setText(path)

    def _collect_settings(self) -> Dict[str, object]:
        mode = ["none", "preset", "split"][self.mode_combo.currentIndex()]
        return {
            "n_videos": self.n_spin.value(),
            "editing_mode": mode,
            "preset_name": self.preset_combo.currentText(),
            "split_duration": self.split_spin.value(),
            "duplication_control": self.dup_check.isChecked(),
            "popular_fallback": self.pop_check.isChecked(),
            "prefer_popular_first": False,
            "randomize_links": self.rand_check.isChecked(),
            "keep_original_after_edit": self.keep_original_check.isChecked(),
            "delete_before_download": self.delete_before_dl_check.isChecked(),
            "watermark_enabled": self.wm_enable_btn.isChecked(),
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
        }

    def _create_all(self):
        count = 0
        merged_count = 0
        existing_by_key = _existing_creator_folder_map(self.root)
        created_by_key: Dict[str, Path] = {}
        for row in range(self.table.rowCount()):
            url  = self.table.item(row, 0).text().strip()
            suggested_name = (self.table.item(row, 1).text() or "").strip()
            custom_item = self.table.item(row, 2)
            custom_name = (custom_item.text() if custom_item else "").strip()
            name = _safe_folder_name(custom_name or suggested_name)
            if not url or not name:
                continue
            normalized_url = CreatorConfig._normalize_profile_url(url) or url
            creator_key = _canonical_creator_key(normalized_url)

            # Resolve folder: same creator key must map to one folder only.
            if creator_key in created_by_key:
                folder = created_by_key[creator_key]
                merged_count += 1
            elif creator_key in existing_by_key:
                folder = existing_by_key[creator_key]
                merged_count += 1
                created_by_key[creator_key] = folder
            else:
                folder = self.root / name
                created_by_key[creator_key] = folder

            try:
                folder.mkdir(parents=True, exist_ok=True)
                cfg = CreatorConfig(folder)
                cfg.data["creator_url"] = normalized_url
                cfg.data.update(self._collect_settings())
                cfg.save()
                count += 1
            except Exception:
                pass
        self.created_count = count
        if count:
            if merged_count > 0:
                QMessageBox.information(
                    self,
                    "Duplicate Creators Merged",
                    f"{merged_count} duplicate row(s) matched an existing creator URL,\n"
                    "so settings were updated in the same creator folder instead of creating new folders.",
                )
            self.accept()
        else:
            QMessageBox.warning(self, "Nothing Created",
                                "Parse URLs first, then click Create All.")


# ─────────────────────────── main page ──────────────────────────────────────

class AllSettingsDialog(QDialog):
    """Centralized settings dialog for applying common settings to all creator cards."""

    _SS = """
        QDialog  { background:#0d1117; color:white; }
        QLabel   { color:rgba(255,255,255,0.82); background:transparent; border:none; }
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
            background:#161b22; color:white;
            border:1px solid rgba(0,212,255,0.28);
            border-radius:4px; padding:6px;
            min-height:28px;
        }
        QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
            border-color:#00d4ff;
        }
        QCheckBox {
            color:#e8f1ff;
            spacing:8px;
            font-size:13px;
            font-weight:600;
        }
        QCheckBox::indicator { width:16px; height:16px; }
        QSlider::groove:horizontal {
            background:rgba(0,212,255,0.15); height:4px; border-radius:2px;
        }
        QSlider::handle:horizontal {
            background:#00d4ff; width:14px; height:14px;
            margin:-5px 0; border-radius:7px;
        }
        QSlider::sub-page:horizontal { background:rgba(0,212,255,0.5); border-radius:2px; }
        QPushButton {
            background:#161b22; color:white;
            border:1px solid rgba(0,212,255,0.3);
            border-radius:5px; padding:7px 18px; font-weight:bold;
        }
        QPushButton:hover { background:#1c2128; border-color:#00d4ff; }
    """

    def __init__(self, baseline_cfg: CreatorConfig, preset_names: List[str], parent=None):
        super().__init__(parent)
        self.baseline_cfg = baseline_cfg
        self.preset_names = preset_names
        self.result_settings: Dict[str, object] = {}
        self.setWindowTitle("All Settings")
        self.setMinimumSize(860, 680)
        self.resize(920, 760)
        self.setSizeGripEnabled(True)
        self.setStyleSheet(self._SS)
        self._build()
        self._load_from_config()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 18, 20, 12)
        outer.setSpacing(8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setStyleSheet(
            "QScrollArea { background:#0d1117; border:none; }"
            "QScrollBar:vertical { background:#0d1117; width:8px; border-radius:4px; }"
            "QScrollBar::handle:vertical { background:rgba(0,212,255,0.3); border-radius:4px; min-height:20px; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0px; }"
        )
        outer.addWidget(scroll, 1)

        container = QWidget()
        container.setStyleSheet("background:#0d1117;")
        scroll.setWidget(container)

        content = QVBoxLayout(container)
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(10)

        title = QLabel("All Settings  —  Apply Common Settings To All Creators")
        title.setFont(QFont("Segoe UI", 13, QFont.Bold))
        title.setStyleSheet(f"color:{_CYAN}; background:transparent; border:none;")
        content.addWidget(title)

        settings_form = QFormLayout()
        settings_form.setSpacing(10)
        settings_form.setHorizontalSpacing(22)
        settings_form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        settings_form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        self.n_spin = QSpinBox()
        self.n_spin.setRange(1, 500)
        self.n_spin.setMinimumWidth(130)
        settings_form.addRow("N Videos:", self.n_spin)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["None", "Preset", "Split"])
        self.mode_combo.setMinimumWidth(170)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_change)
        settings_form.addRow("Editing Mode:", self.mode_combo)

        self.preset_combo = QComboBox()
        self.preset_combo.addItems(self.preset_names or ["- no presets -"])
        self.preset_combo.setMinimumWidth(220)
        settings_form.addRow("Preset:", self.preset_combo)

        self.split_spin = QDoubleSpinBox()
        self.split_spin.setRange(1.0, 3600.0)
        self.split_spin.setSuffix(" s")
        self.split_spin.setMinimumWidth(170)
        settings_form.addRow("Split Duration:", self.split_spin)

        self.dup_check = QCheckBox("Skip already downloaded")
        settings_form.addRow("Duplication:", self.dup_check)

        self.pop_check = QCheckBox("Use popular fallback")
        settings_form.addRow("Popular Fallback:", self.pop_check)

        self.rand_check = QCheckBox("Randomize links")
        settings_form.addRow("Randomize:", self.rand_check)

        content.addLayout(settings_form)
        content.addWidget(_hdiv())

        wm_title = QLabel("WaterMark Settings")
        wm_title.setStyleSheet(
            f"color:{_CYAN}; font-size:12px; font-weight:bold; background:transparent; border:none;"
        )
        content.addWidget(wm_title)

        wm_form = QFormLayout()
        wm_form.setSpacing(10)
        wm_form.setHorizontalSpacing(22)
        wm_form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        wm_form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        self.wm_enable_check = QCheckBox("Enable watermark")
        wm_form.addRow("WaterMark:", self.wm_enable_check)

        self.wm_txt_enable_check = QCheckBox("Enable text watermark")
        wm_form.addRow("Text WM:", self.wm_txt_enable_check)

        self.wm_text_edit = QLineEdit()
        self.wm_text_edit.setPlaceholderText("Leave blank to use @folderName")
        self.wm_text_edit.setMinimumWidth(300)
        wm_form.addRow("Text:", self.wm_text_edit)

        self.wm_txt_pos_cb = QComboBox()
        self.wm_txt_pos_cb.addItems(["TopLeft", "TopRight", "BottomLeft", "BottomRight", "Center", "AnimateAround"])
        self.wm_txt_pos_cb.setMinimumWidth(170)
        wm_form.addRow("Text Position:", self.wm_txt_pos_cb)

        self.wm_txt_opacity_sl = QSlider(Qt.Horizontal)
        self.wm_txt_opacity_sl.setRange(0, 100)
        self.wm_txt_opacity_lbl = QLabel("80%")
        self.wm_txt_opacity_lbl.setStyleSheet("color:white; background:transparent; border:none; min-width:32px;")
        self.wm_txt_opacity_sl.valueChanged.connect(lambda v: self.wm_txt_opacity_lbl.setText(f"{v}%"))
        txt_op_row = QHBoxLayout()
        txt_op_row.setContentsMargins(0, 0, 0, 0)
        txt_op_row.setSpacing(6)
        txt_op_row.addWidget(self.wm_txt_opacity_sl, 1)
        txt_op_row.addWidget(self.wm_txt_opacity_lbl)
        txt_op_w = QWidget()
        txt_op_w.setStyleSheet("background:transparent; border:none;")
        txt_op_w.setLayout(txt_op_row)
        wm_form.addRow("Text Opacity:", txt_op_w)

        self.wm_txt_font_edit = QComboBox()
        self.wm_txt_font_edit.setEditable(True)
        self._init_wm_font_presets(self.wm_txt_font_edit)
        self.wm_txt_font_edit.setMinimumWidth(190)
        wm_form.addRow("Font Family:", self.wm_txt_font_edit)

        self.wm_txt_color_preset_cb = QComboBox()
        self._init_wm_color_presets(self.wm_txt_color_preset_cb)
        self.wm_txt_color_preset_cb.setMinimumWidth(210)
        wm_form.addRow("Font Color:", self.wm_txt_color_preset_cb)

        self.wm_txt_size_sp = QSpinBox()
        self.wm_txt_size_sp.setRange(8, 200)
        wm_form.addRow("Font Size:", self.wm_txt_size_sp)

        self.wm_txt_weight_cb = QComboBox()
        self.wm_txt_weight_cb.addItems(["normal", "bold"])
        wm_form.addRow("Font Weight:", self.wm_txt_weight_cb)

        self.wm_txt_style_cb = QComboBox()
        self.wm_txt_style_cb.addItems(["normal", "italic"])
        wm_form.addRow("Font Style:", self.wm_txt_style_cb)

        self.wm_txt_render_style_cb = QComboBox()
        self.wm_txt_render_style_cb.addItems(["normal", "outline_hollow", "outline_shadow"])
        wm_form.addRow("Render Style:", self.wm_txt_render_style_cb)

        self.wm_txt_shadow_opacity_sl = QSlider(Qt.Horizontal)
        self.wm_txt_shadow_opacity_sl.setRange(0, 100)
        self.wm_txt_shadow_opacity_sl.setValue(75)
        self.wm_txt_shadow_opacity_lbl = QLabel("75%")
        self.wm_txt_shadow_opacity_lbl.setStyleSheet("color:white; background:transparent; border:none; min-width:32px;")
        self.wm_txt_shadow_opacity_sl.valueChanged.connect(lambda v: self.wm_txt_shadow_opacity_lbl.setText(f"{v}%"))
        txt_shadow_row = QHBoxLayout()
        txt_shadow_row.setContentsMargins(0, 0, 0, 0)
        txt_shadow_row.setSpacing(6)
        txt_shadow_row.addWidget(self.wm_txt_shadow_opacity_sl, 1)
        txt_shadow_row.addWidget(self.wm_txt_shadow_opacity_lbl)
        txt_shadow_w = QWidget()
        txt_shadow_w.setStyleSheet("background:transparent; border:none;")
        txt_shadow_w.setLayout(txt_shadow_row)
        wm_form.addRow("Shadow Opacity:", txt_shadow_w)

        self.wm_txt_shadow_offset_sp = QSpinBox()
        self.wm_txt_shadow_offset_sp.setRange(0, 50)
        self.wm_txt_shadow_offset_sp.setValue(2)
        wm_form.addRow("Shadow Offset:", self.wm_txt_shadow_offset_sp)

        self.wm_txt_spacing_sp = QSpinBox()
        self.wm_txt_spacing_sp.setRange(0, 50)
        wm_form.addRow("Letter Spacing:", self.wm_txt_spacing_sp)

        self.wm_logo_enable_check = QCheckBox("Enable logo watermark")
        wm_form.addRow("Logo WM:", self.wm_logo_enable_check)

        logo_row = QHBoxLayout()
        logo_row.setContentsMargins(0, 0, 0, 0)
        logo_row.setSpacing(6)
        self.wm_logo_path_edit = QLineEdit()
        self.wm_logo_path_edit.setPlaceholderText("Leave blank to auto-detect logo.* in folder")
        self.wm_logo_path_edit.setMinimumWidth(300)
        logo_btn = QToolButton()
        logo_btn.setIcon(self.style().standardIcon(QStyle.SP_DirOpenIcon))
        logo_btn.setToolTip("Select logo file")
        logo_btn.setAutoRaise(True)
        logo_btn.setFixedSize(30, 28)
        logo_btn.setStyleSheet(
            "QToolButton { background:#2a2410; border:1px solid rgba(222,191,7,0.7); border-radius:4px; }"
            "QToolButton:hover { background:#3a3216; border-color:#DEBF07; }"
        )
        logo_btn.clicked.connect(self._browse_logo)
        logo_row.addWidget(self.wm_logo_path_edit, 1)
        logo_row.addWidget(logo_btn)
        logo_w = QWidget()
        logo_w.setStyleSheet("background:transparent; border:none;")
        logo_w.setLayout(logo_row)
        wm_form.addRow("Logo Path:", logo_w)

        self.wm_logo_pos_cb = QComboBox()
        self.wm_logo_pos_cb.addItems(["TopLeft", "TopRight", "BottomLeft", "BottomRight", "Center", "AnimateAround"])
        self.wm_logo_pos_cb.setMinimumWidth(170)
        wm_form.addRow("Logo Position:", self.wm_logo_pos_cb)

        self.wm_logo_opacity_sl = QSlider(Qt.Horizontal)
        self.wm_logo_opacity_sl.setRange(0, 100)
        self.wm_logo_opacity_lbl = QLabel("80%")
        self.wm_logo_opacity_lbl.setStyleSheet("color:white; background:transparent; border:none; min-width:32px;")
        self.wm_logo_opacity_sl.valueChanged.connect(lambda v: self.wm_logo_opacity_lbl.setText(f"{v}%"))
        logo_op_row = QHBoxLayout()
        logo_op_row.setContentsMargins(0, 0, 0, 0)
        logo_op_row.setSpacing(6)
        logo_op_row.addWidget(self.wm_logo_opacity_sl, 1)
        logo_op_row.addWidget(self.wm_logo_opacity_lbl)
        logo_op_w = QWidget()
        logo_op_w.setStyleSheet("background:transparent; border:none;")
        logo_op_w.setLayout(logo_op_row)
        wm_form.addRow("Logo Opacity:", logo_op_w)

        content.addLayout(wm_form)
        content.addStretch(1)

        for ctrl in (
            self.n_spin, self.mode_combo, self.preset_combo, self.split_spin,
            self.wm_text_edit, self.wm_txt_pos_cb, self.wm_txt_font_edit, self.wm_txt_color_preset_cb,
            self.wm_txt_size_sp, self.wm_txt_weight_cb, self.wm_txt_style_cb,
            self.wm_txt_render_style_cb, self.wm_txt_shadow_offset_sp, self.wm_txt_spacing_sp, self.wm_logo_path_edit,
            self.wm_logo_pos_cb
        ):
            ctrl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Ok).setText("Apply To All")
        btns.button(QDialogButtonBox.Ok).setStyleSheet(
            "background:#1a5c1a; color:white; font-weight:bold; padding:7px 22px; border-radius:5px;"
        )
        btns.button(QDialogButtonBox.Cancel).setStyleSheet(
            "background:#3a1a1a; color:white; font-weight:bold; padding:7px 22px; border-radius:5px;"
        )
        btns.accepted.connect(self._accept_apply)
        btns.rejected.connect(self.reject)
        outer.addWidget(btns)

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

    def _browse_logo(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Logo File", "",
            "Image Files (*.png *.jpg *.jpeg *.webp *.bmp *.svg *.gif);;All Files (*)"
        )
        if path:
            self.wm_logo_path_edit.setText(path)

    def _on_mode_change(self):
        m = self.mode_combo.currentIndex()
        self.preset_combo.setVisible(m == 1)
        self.split_spin.setVisible(m == 2)

    def _load_from_config(self):
        c = self.baseline_cfg
        mode_map = {"none": 0, "preset": 1, "split": 2}
        self.n_spin.setValue(c.n_videos)
        self.mode_combo.setCurrentIndex(mode_map.get(c.editing_mode, 0))
        if c.preset_name and c.preset_name in self.preset_names:
            self.preset_combo.setCurrentText(c.preset_name)
        self.split_spin.setValue(c.split_duration)
        self.dup_check.setChecked(c.duplication_control)
        self.pop_check.setChecked(c.popular_fallback)
        self.rand_check.setChecked(c.randomize_links)

        self.wm_enable_check.setChecked(c.watermark_enabled)
        wt = c.watermark_text
        self.wm_txt_enable_check.setChecked(bool(wt.get("enabled", False)))
        self.wm_text_edit.setText(str(wt.get("text", "")))
        self.wm_txt_pos_cb.setCurrentText(str(wt.get("position", "BottomRight")))
        self.wm_txt_opacity_sl.setValue(int(wt.get("opacity", 80)))
        self.wm_txt_font_edit.setCurrentText(str(wt.get("font_family", "Arial")))
        self._set_color_preset_from_hex(self.wm_txt_color_preset_cb, str(wt.get("font_color", "#FFFFFF")))
        self.wm_txt_size_sp.setValue(int(wt.get("font_size", 24)))
        self.wm_txt_weight_cb.setCurrentText(str(wt.get("font_weight", "bold")))
        self.wm_txt_style_cb.setCurrentText(str(wt.get("font_style", "normal")))
        self.wm_txt_render_style_cb.setCurrentText(str(wt.get("render_style", "normal")))
        self.wm_txt_shadow_opacity_sl.setValue(int(wt.get("shadow_opacity", 75)))
        self.wm_txt_shadow_offset_sp.setValue(int(wt.get("shadow_offset", 2)))
        self.wm_txt_spacing_sp.setValue(int(wt.get("letter_spacing", 0)))

        wl = c.watermark_logo
        self.wm_logo_enable_check.setChecked(bool(wl.get("enabled", False)))
        self.wm_logo_path_edit.setText(str(wl.get("path", "")))
        self.wm_logo_pos_cb.setCurrentText(str(wl.get("position", "TopLeft")))
        self.wm_logo_opacity_sl.setValue(int(wl.get("opacity", 80)))
        self._on_mode_change()

    def _collect_settings(self) -> Dict[str, object]:
        mode = ["none", "preset", "split"][self.mode_combo.currentIndex()]
        return {
            "n_videos": self.n_spin.value(),
            "editing_mode": mode,
            "preset_name": self.preset_combo.currentText(),
            "split_duration": self.split_spin.value(),
            "duplication_control": self.dup_check.isChecked(),
            "popular_fallback": self.pop_check.isChecked(),
            "prefer_popular_first": False,
            "randomize_links": self.rand_check.isChecked(),
            "watermark_enabled": self.wm_enable_check.isChecked(),
            "watermark_text": {
                "enabled":        self.wm_txt_enable_check.isChecked(),
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
                "enabled":  self.wm_logo_enable_check.isChecked(),
                "path":     self.wm_logo_path_edit.text().strip(),
                "position": self.wm_logo_pos_cb.currentText(),
                "opacity":  self.wm_logo_opacity_sl.value(),
            },
        }

    def _accept_apply(self):
        self.result_settings = self._collect_settings()
        self.accept()


class FailedSummaryDialog(QDialog):
    def __init__(self, failed_list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Failed Downloads Summary")
        self.setMinimumSize(400, 350)
        self.setStyleSheet(
            "QDialog { background: #0d1117; color: white; }"
            "QLabel { color: #00d4ff; font-weight: bold; font-size: 14px; background: transparent; border: none; }"
            "QTextEdit { background: #161b22; color: #E74C3C; border: 1px solid rgba(231,76,60,0.4); border-radius: 4px; font-size: 13px; }"
            "QPushButton { background: #161b22; color: white; border: 1px solid rgba(0,212,255,0.3); border-radius: 5px; padding: 7px 18px; font-weight: bold; }"
            "QPushButton:hover { background: #1c2128; border-color: #00d4ff; }"
        )
        v = QVBoxLayout(self)
        v.addWidget(QLabel("The following folders had errors:"))
        
        self.txt = QTextEdit()
        self.txt.setReadOnly(True)
        self.txt.setPlainText("\n".join(failed_list))
        v.addWidget(self.txt)
        
        btn_layout = QHBoxLayout()
        copy_btn = QPushButton("Copy to Clipboard")
        copy_btn.clicked.connect(self._copy)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(copy_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        v.addLayout(btn_layout)
        
    def _copy(self):
        from PyQt5.QtWidgets import QApplication
        QApplication.clipboard().setText(self.txt.toPlainText())

class CreatorProfilesPage(QWidget):
    """Downloading + Editing main page — self-contained layout, top action bar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.root         = _links_root()
        self.presets      = _preset_names()
        self.cards: Dict[Path, CreatorCard] = {}
        self._search_query = ""
        self.daily_guard_enabled = False
        self.daily_guard_interval_minutes = 30
        self._queue_manager = CreatorQueueManager(self)
        self._queue_manager.queue_progress.connect(self._on_queue_progress)
        self._queue_manager.creator_started.connect(self._on_queue_creator_started)
        self._queue_manager.creator_finished.connect(self._on_queue_creator_finished)
        self._queue_manager.creator_progress_pct.connect(self._on_queue_creator_pct)
        self._queue_manager.queue_finished.connect(self._on_queue_finished)
        self._queue_manager.paused.connect(self._on_queue_paused)
        # Queue stats tracking
        self._queue_stats = {"total": 0, "done": 0, "success": 0, "failed": 0}
        self._cols        = 2
        self._col_timer   = QTimer(self)
        self._col_timer.setSingleShot(True)
        self._col_timer.setInterval(50)
        self._col_timer.timeout.connect(self._update_cols)
        self._daily_guard_timer = QTimer(self)
        self._daily_guard_timer.timeout.connect(self._daily_guard_cycle)

        self.setStyleSheet(f"QWidget {{ background:{_BG}; color:white; }}")
        self._build_ui()
        self._setup_watcher()
        self._refresh_cards()
        # Check for crash recovery after UI is ready (delayed so window is visible)
        QTimer.singleShot(1500, self._check_crash_recovery)

    def cleanup(self):
        """Close IXBrowser session if active. Called on app exit."""
        try:
            from .ix_link_grabber import get_ix_session
            ix = get_ix_session()
            if ix.is_alive():
                print("[CreatorProfiles] Closing IXBrowser session on app exit...")
                ix.close_session()
                print("[CreatorProfiles] IXBrowser session closed.")
        except Exception as e:
            print(f"[CreatorProfiles] Cleanup error: {e}")

    # ── UI ────────────────────────────────────────────────────────────────

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 14, 18, 12)
        outer.setSpacing(10)

        # ── Header ────────────────────────────────────────────────────────
        hdr = QFrame()  # legacy placeholder
        hdr.setStyleSheet(f"""
            QFrame {{
                background:{_BG_CARD};
                border:1px solid {_BORDER};
                border-radius:10px;
            }}
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(18); shadow.setOffset(0, 3)
        shadow.setColor(QColor(0, 212, 255, 45))
        hdr.setGraphicsEffect(shadow)

        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(18, 12, 18, 12)

        title = QLabel("⚡  Downloading + Editing")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title.setStyleSheet(f"color:{_CYAN}; background:transparent; border:none;")
        hl.addWidget(title)
        hl.addStretch()

        info_col = QVBoxLayout()
        info_col.setSpacing(2)
        self.root_lbl  = QLabel()
        self.count_lbl = QLabel()
        for l in (self.root_lbl, self.count_lbl):
            l.setStyleSheet(
                "color:rgba(255,255,255,0.38); font-size:11px;"
                " background:transparent; border:none;"
            )
            l.setAlignment(Qt.AlignRight)
            info_col.addWidget(l)
        hl.addLayout(info_col)
        outer.addWidget(hdr)
        hdr.setVisible(False)

        # ── Action bar (TOP) ──────────────────────────────────────────────
        action_panel = QFrame()
        action_panel.setStyleSheet(f"""
            QFrame {{
                background:{_BG_PANEL};
                border:1px solid rgba(0,212,255,0.12);
                border-radius:8px;
            }}
        """)
        action_vbox = QVBoxLayout(action_panel)
        action_vbox.setContentsMargins(12, 8, 12, 8)
        action_vbox.setSpacing(5)

        # ── Row 1: primary actions (Run All + OneGo) ─────────────────────
        row1 = QHBoxLayout()
        row1.setSpacing(7)

        run_all = _abtn("▶  Run All", _GREEN, "#161b22")
        run_all.clicked.connect(self._on_run_all)
        row1.addWidget(run_all)

        self.onego_btn = _abtn("▶  OneGo", _CYAN, "#161b22")
        self.onego_btn.setToolTip("Run download + upload workflow in one click")
        self.onego_btn.clicked.connect(self._on_onego)
        row1.addWidget(self.onego_btn)

        self.pause_all_btn = _abtn("⏸  Pause", _WARN, "#161b22")
        self.pause_all_btn.setVisible(False)
        self.pause_all_btn.clicked.connect(self._on_pause_all)
        row1.addWidget(self.pause_all_btn)

        self.resume_all_btn = _abtn("▶  Resume", _GREEN, "#161b22")
        self.resume_all_btn.setVisible(False)
        self.resume_all_btn.clicked.connect(self._on_resume_all)
        row1.addWidget(self.resume_all_btn)

        stop_b = _abtn("⏹  Stop", _RED, "#161b22")
        stop_b.clicked.connect(self._on_stop_all)
        row1.addWidget(stop_b)

        self.summary_btn = _abtn("📋 Final Summary", _WARN, "#161b22")
        self.summary_btn.setVisible(False)
        self.summary_btn.clicked.connect(self._on_summary_clicked)
        row1.addWidget(self.summary_btn)

        # ── Queue status label (inline in row 1) ─────────────────────────
        self.queue_status_lbl = QLabel("")
        self.queue_status_lbl.setStyleSheet(
            f"color:{_CYAN}; font-size:11px; font-weight:bold;"
            " background:transparent; border:none; padding-left:8px;"
        )
        self.queue_status_lbl.setVisible(False)
        row1.addWidget(self.queue_status_lbl)

        row1.addStretch()
        action_vbox.addLayout(row1)

        # ── Row 2: secondary actions ─────────────────────────────────────
        row2 = QHBoxLayout()
        row2.setSpacing(7)

        # Add Creator (dropdown menu)
        self.add_btn = _abtn("+ Add Creator  ▾", _CYAN, "#161b22")
        add_menu = QMenu(self.add_btn)
        add_menu.setStyleSheet(f"""
            QMenu {{
                background:{_BG_CARD}; color:white;
                border:1px solid {_BORDER}; border-radius:6px; padding:4px;
            }}
            QMenu::item {{ padding:8px 22px; border-radius:4px; }}
            QMenu::item:selected {{ background:rgba(0,212,255,0.12); color:{_CYAN}; }}
        """)
        add_menu.addAction("➕  Single Creator",         self._on_add_single)
        add_menu.addAction("📋  Bulk Add (Multiple URLs)", self._on_add_bulk)
        self.add_btn.setMenu(add_menu)
        row2.addWidget(self.add_btn)

        imp_btn = _abtn("⬆  Import", _CYAN, "#161b22")
        imp_btn.setToolTip("Import creator settings from JSON file")
        imp_btn.clicked.connect(self._on_import)
        row2.addWidget(imp_btn)

        exp_btn = _abtn("⬇  Export", _CYAN, "#161b22")
        exp_btn.setToolTip("Export all creator settings to JSON file")
        exp_btn.clicked.connect(self._on_export)
        row2.addWidget(exp_btn)

        all_settings_btn = _abtn("⚙  All Settings", _CYAN, "#161b22")
        all_settings_btn.setToolTip("Open one panel to edit common settings and apply to all creators")
        all_settings_btn.clicked.connect(self._on_all_settings)
        row2.addWidget(all_settings_btn)

        row2.addWidget(_vsep())

        clr_b = _abtn("🗑  Clear History", _CYAN, "#161b22")
        clr_b.clicked.connect(self._on_clear_history)
        row2.addWidget(clr_b)

        self.guard_b = _abtn("🛡  Start Daily Guard", _GREEN, "#161b22")
        self.guard_b.setVisible(False)
        self.guard_b.clicked.connect(self._on_toggle_daily_guard)
        row2.addWidget(self.guard_b)

        ref_b = _abtn("↺  Reset App", "rgba(255,255,255,0.7)", _BG_CARD,
                       "rgba(255,255,255,0.12)")
        ref_b.setVisible(False)
        ref_b.clicked.connect(self._on_reset_app)
        row2.addWidget(ref_b)

        sav_b = _abtn("💾  Save All", "rgba(255,255,255,0.7)", _BG_CARD,
                       "rgba(255,255,255,0.12)")
        sav_b.setVisible(False)
        sav_b.clicked.connect(self._on_save_all)
        row2.addWidget(sav_b)

        row2.addStretch()

        self.root_lbl.setStyleSheet(
            "color:white; font-size:11px; background:transparent; border:none;"
        )
        self.count_lbl.setStyleSheet(
            "color:white; font-size:11px; background:transparent; border:none;"
        )
        info_col = QVBoxLayout()
        info_col.setContentsMargins(0, 0, 0, 0)
        info_col.setSpacing(1)
        self.root_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.count_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        info_col.addWidget(self.root_lbl)
        info_col.addWidget(self.count_lbl)
        row2.addLayout(info_col)
        row2.addSpacing(10)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search Creator")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setMinimumWidth(240)
        self.search_input.setMaximumWidth(340)
        self.search_input.setFixedHeight(32)
        self.search_input.setToolTip("Search by creator name or profile URL")
        self.search_input.setStyleSheet(
            f"""
            QLineEdit {{
                color:white;
                background:#161b22;
                border:1px solid {_BORDER};
                border-radius:5px;
                padding:5px 10px;
                font-size:12px;
            }}
            QLineEdit:focus {{
                border-color:{_CYAN};
                background:#1c2128;
            }}
            QLineEdit::placeholder {{
                color:rgba(255,255,255,0.45);
            }}
            """
        )
        self.search_input.textChanged.connect(self._on_search_text_changed)
        row2.addWidget(self.search_input)

        action_vbox.addLayout(row2)
        outer.addWidget(action_panel)
        outer.addWidget(_hdiv())

        # ── Scrollable card grid ──────────────────────────────────────────
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll.setStyleSheet("""
            QScrollArea          { background:transparent; border:none; }
            QScrollBar:vertical  { background:#0a0e1a; width:8px; border-radius:4px; }
            QScrollBar::handle:vertical {
                background:rgba(0,212,255,0.4); border-radius:4px; min-height:20px;
            }
            QScrollBar::handle:vertical:hover { background:#00d4ff; }
            QScrollBar::add-line, QScrollBar::sub-line { height:0; width:0; }
        """)

        # scroll content widget
        self.scroll_content = QWidget()
        self.scroll_content.setStyleSheet("background:transparent;")
        sv = QVBoxLayout(self.scroll_content)
        sv.setContentsMargins(0, 0, 4, 0)
        sv.setSpacing(0)

        self.cards_w = QWidget()
        self.cards_w.setStyleSheet("background:transparent;")
        self.cards_w.setMinimumWidth(0)
        self.cards_grid = QGridLayout(self.cards_w)
        self.cards_grid.setSpacing(12)
        self.cards_grid.setContentsMargins(0, 0, 0, 0)

        sv.addWidget(self.cards_w)
        sv.addStretch()

        self.scroll.setWidget(self.scroll_content)
        # Fire column recalc whenever the scroll viewport itself resizes
        self.scroll.viewport().installEventFilter(self)
        outer.addWidget(self.scroll, 1)

        # ── Empty state ───────────────────────────────────────────────────
        self.empty = QFrame()
        self.empty.setStyleSheet(f"""
            QFrame {{
                background:{_BG_CARD};
                border:1px solid {_BORDER};
                border-radius:10px;
            }}
        """)
        el = QVBoxLayout(self.empty)
        el.setAlignment(Qt.AlignCenter)
        el.setContentsMargins(40, 70, 40, 70)

        for text, style in [
            ("📂", f"font-size:44px; background:transparent; border:none;"),
            ("No Creator Folders Found",
             "color:rgba(255,255,255,0.5); font-size:15px; font-weight:bold;"
             " background:transparent; border:none;"),
            ("Desktop / Links Grabber / should contain creator subfolders,\n"
             "or click  '+ Add Creator'  to add one manually.",
             "color:rgba(255,255,255,0.28); font-size:12px;"
             " background:transparent; border:none;"),
        ]:
            l = QLabel(text)
            l.setAlignment(Qt.AlignCenter)
            l.setStyleSheet(style)
            el.addWidget(l)

        outer.addWidget(self.empty, 1)

    # ── watcher ───────────────────────────────────────────────────────────

    def _setup_watcher(self):
        self.watcher = QFileSystemWatcher()
        if self.root.exists():
            self.watcher.addPath(str(self.root))
        self.watcher.directoryChanged.connect(lambda _: self._refresh_cards())

    # ── card management ───────────────────────────────────────────────────

    def _refresh_cards(self):
        self.root_lbl.setText(f"Scan:  {self.root}")
        folders = _scan_folders(self.root)
        folder_set = set(folders)

        # Remove stale cards
        for fp in list(self.cards.keys()):
            if fp not in folder_set:
                card = self.cards.pop(fp)
                card.stop_worker()
                card.deleteLater()

        # Add new cards
        for fp in folders:
            if fp not in self.cards:
                card = CreatorCard(fp, self.root, self.presets)
                card.remove_requested.connect(self._on_remove_card)
                card.run_started.connect(self._on_card_run_started)
                card.run_finished.connect(self._on_card_run_finished)
                self.cards[fp] = card
                self.watcher.addPath(str(fp))

        self._rebuild_grid()
        n = len(self.cards)
        self.count_lbl.setText(
            f"{n} creator{'s' if n != 1 else ''} loaded"
        )
        self._toggle_empty(n == 0)

    def _rebuild_grid(self):
        """Clear and re-populate the QGridLayout with current column count."""
        while self.cards_grid.count():
            self.cards_grid.takeAt(0)
        # Reset all column stretches, then apply equal stretch for active cols
        for c in range(_MAX_COLS):
            self.cards_grid.setColumnStretch(c, 0)
        for c in range(self._cols):
            self.cards_grid.setColumnStretch(c, 1)
        visible_cards = []
        for fp, card in self.cards.items():
            matched = self._card_matches_search(card)
            card.set_search_highlight(bool(self._search_query) and matched)
            if matched:
                visible_cards.append((fp, card))

        for i, (fp, card) in enumerate(visible_cards):
            r, c = divmod(i, self._cols)
            self.cards_grid.addWidget(card, r, c)

    def _on_search_text_changed(self, text: str):
        self._search_query = (text or "").strip().lower()
        self._rebuild_grid()

    def _card_matches_search(self, card: CreatorCard) -> bool:
        if not self._search_query:
            return True
        folder_name = card.folder.name.lower()
        creator_url = ""
        try:
            creator_url = str(card.config.creator_url or "").lower()
        except Exception:
            creator_url = ""
        return (
            self._search_query in folder_name
            or (creator_url and self._search_query in creator_url)
        )

    def _toggle_empty(self, empty: bool):
        self.empty.setVisible(empty)
        self.scroll.setVisible(not empty)

    def _on_remove_card(self, folder: Path):
        folder = Path(folder)

        # Safety: only allow deletion inside configured Links Grabber root.
        try:
            root_resolved = self.root.resolve()
            folder_resolved = folder.resolve()
            folder_resolved.relative_to(root_resolved)
            can_delete = True
        except Exception:
            can_delete = False

        if can_delete and folder.exists():
            try:
                shutil.rmtree(folder)
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Delete Failed",
                    f"Could not delete folder:\n{folder}\n\nReason: {e}",
                )
                return

        if folder in self.cards:
            try:
                self.watcher.removePath(str(folder))
            except Exception:
                pass
            card = self.cards.pop(folder)
            card.stop_worker()
            card.deleteLater()
        self._rebuild_grid()
        self._toggle_empty(len(self.cards) == 0)

    # ── responsive columns ────────────────────────────────────────────────

    def eventFilter(self, watched, event):
        """Catch viewport resize to immediately retrigger column recalc."""
        if watched is self.scroll.viewport() and event.type() == QEvent.Resize:
            self._col_timer.start()
        return super().eventFilter(watched, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._col_timer.start()

    def _update_cols(self):
        if self.scroll.isVisible():
            vp_w = self.scroll.viewport().width()
        else:
            vp_w = self.width()
        # Subtract scroll content right margin (4px) to get true available width
        avail = max(1, vp_w - 4)
        new_cols = max(1, min(_MAX_COLS, avail // _MIN_CARD))
        # Always enforce max width to prevent horizontal overflow
        self.cards_w.setMaximumWidth(avail)
        if new_cols != self._cols:
            self._cols = new_cols
            self._rebuild_grid()

    # ── action bar slots ──────────────────────────────────────────────────

    def _on_add_single(self):
        self.root.mkdir(parents=True, exist_ok=True)
        dlg = AddCreatorDialog(self.root, self.presets, self)
        if dlg.exec_() and dlg.created_folder:
            self._refresh_cards()

    def _on_add_bulk(self):
        self.root.mkdir(parents=True, exist_ok=True)
        dlg = BulkAddDialog(self.root, self.presets, self)
        if dlg.exec_() and dlg.created_count:
            self._refresh_cards()
            QMessageBox.information(
                self, "Done",
                f"{dlg.created_count} creator(s) added successfully."
            )

    def _on_all_settings(self):
        if not self.cards:
            QMessageBox.information(self, "No Creators", "No creator cards available to update.")
            return

        first_folder = next(iter(self.cards.keys()))
        baseline_cfg = CreatorConfig(first_folder)
        dlg = AllSettingsDialog(baseline_cfg, self.presets, self)
        if dlg.exec_() != QDialog.Accepted:
            return

        settings = dict(dlg.result_settings or {})
        if not settings:
            return

        updated = 0
        failed: List[str] = []
        for fp, card in self.cards.items():
            try:
                cfg = CreatorConfig(fp)
                cfg.data.update(settings)
                cfg.save()

                # Refresh card UI from persisted config.
                card.config = CreatorConfig(fp)
                card._load_values()
                card._refresh_activity()
                updated += 1
            except Exception as exc:
                failed.append(f"{fp.name}: {exc}")

        if failed:
            QMessageBox.warning(
                self,
                "Partially Applied",
                f"Applied to {updated} creator(s), failed on {len(failed)}.\n\n"
                + "\n".join(failed[:8]),
            )
        else:
            QMessageBox.information(
                self,
                "Applied",
                f"Common settings applied to all {updated} creator(s).",
            )

    def _on_onego(self):
        """Open OneGo start dialog and run download+upload workflow."""
        from .onego.start_dialog import OneGoStartDialog
        from .onego.workflow import OneGoWorker, MODE_DOWNLOAD_UPLOAD

        dlg = OneGoStartDialog(self)
        if dlg.exec_() != OneGoStartDialog.Accepted:
            return
        result = dlg.get_result()
        if not result:
            return

        if not self.cards:
            QMessageBox.information(self, "OneGo", "No creators configured yet.")
            return

        card_folders = list(self.cards.keys())

        # Download trigger: start the existing queue, signal OneGo when done
        def download_trigger():
            self._on_run_all()

        worker = OneGoWorker(
            mode=result["mode"],
            api_url=result["api_url"],
            email=result["email"],
            password=result["password"],
            profile_hint=result.get("profile_hint", ""),
            card_folders=card_folders,
            links_root=self.root,
            download_trigger=download_trigger if result["mode"] == MODE_DOWNLOAD_UPLOAD else None,
            parent=self,
        )

        # If download+upload mode, connect queue_finished to mark download done
        if result["mode"] == MODE_DOWNLOAD_UPLOAD:
            def _on_dl_done():
                worker.mark_download_done()
            self._onego_dl_done_cb = _on_dl_done  # prevent GC
            self._queue_manager.queue_finished.connect(_on_dl_done)

        self._onego_worker = worker
        worker.progress.connect(self._on_onego_progress)
        worker.finished_signal.connect(self._on_onego_finished)
        worker.start()
        self.onego_btn.setEnabled(False)
        self.onego_btn.setText("OneGo Running...")

    def _on_onego_progress(self, msg: str):
        self.queue_status_lbl.setText(msg)
        self.queue_status_lbl.setVisible(True)

    def _on_onego_finished(self, report: dict):
        self.onego_btn.setEnabled(True)
        self.onego_btn.setText("\u25b6  OneGo")
        self.queue_status_lbl.setVisible(False)

        # Disconnect download-done callback if it was connected
        if hasattr(self, "_onego_dl_done_cb"):
            try:
                self._queue_manager.queue_finished.disconnect(self._onego_dl_done_cb)
            except Exception:
                pass
            del self._onego_dl_done_cb

        # Store report and show detailed report dialog
        self._onego_last_report = report
        from .onego.report_dialog import OneGoReportDialog
        dlg = OneGoReportDialog(report, self)
        dlg.exec_()

    def _on_run_all(self):
        """Start sequential queue using CreatorQueueManager."""
        if not self.cards:
            return
        folders = list(self.cards.keys())
        self.summary_btn.setVisible(False)
        self._queue_stats = {"total": len(folders), "done": 0, "success": 0, "failed": 0}
        # Show queued status on all cards
        for i, card in enumerate(self.cards.values()):
            card._set_state("idle", f"Queued ({i + 1}/{len(folders)})")
        # Show Pause button, hide Resume
        self.pause_all_btn.setVisible(True)
        self.resume_all_btn.setVisible(False)
        self.queue_status_lbl.setVisible(True)
        # Lock all manual run buttons during queue
        for card in self.cards.values():
            card.set_manual_run_locked(True)
        self._queue_manager.start_queue(folders)

    def _on_pause_all(self):
        """Pause the queue after current video finishes."""
        self._queue_manager.pause()
        self.pause_all_btn.setVisible(False)
        self.resume_all_btn.setVisible(True)

    def _on_resume_all(self):
        """Resume the paused queue."""
        self._queue_manager.resume()
        self.pause_all_btn.setVisible(True)
        self.resume_all_btn.setVisible(False)

    def _on_stop_all(self):
        """Stop the queue and all active downloads."""
        self._queue_manager.stop()
        self.pause_all_btn.setVisible(False)
        self.resume_all_btn.setVisible(False)
        self.queue_status_lbl.setVisible(False)
        for card in self.cards.values():
            card.stop_worker()
            card.set_manual_run_locked(False)
            card.set_queue_active(False)
            if card._state == "idle" and card.status_lbl.text().startswith("Queued"):
                card._set_state("idle", "Stopped.")

    # ── Queue manager signal handlers ────────────────────────────────────

    def _on_queue_progress(self, msg: str):
        """Update queue status label and active card's status."""
        self.queue_status_lbl.setText(msg)
        self.queue_status_lbl.setVisible(True)
        # Also update the active card's status text
        for fp, card in self.cards.items():
            if card._queue_active:
                # Extract creator-specific message (strip "@name: " prefix)
                display = msg
                prefix = f"@{fp.name}: "
                if display.startswith(prefix):
                    display = display[len(prefix):]
                card._set_state("running", display)
                break

    def _on_queue_creator_started(self, creator_name: str):
        """Highlight the card being processed (queue manager runs its own worker)."""
        for fp, card in self.cards.items():
            if fp.name == creator_name:
                card.set_queue_active(True)
                card._set_state("running", "Queue: Starting...")
            else:
                if not card._queue_active:
                    continue
                card.set_queue_active(False)

    def _on_queue_creator_pct(self, creator_name: str, pct: int):
        """Forward download percentage to the active card's dot."""
        for fp, card in self.cards.items():
            if fp.name == creator_name:
                card._on_progress_percent(pct)
                break

    def _on_queue_creator_finished(self, creator_name: str, success: bool):
        """Un-highlight the finished card, update stats and summary."""
        self._queue_stats["done"] += 1
        if success:
            self._queue_stats["success"] += 1
        else:
            self._queue_stats["failed"] += 1
        # Update summary label
        s = self._queue_stats
        videos = self._queue_manager._total_videos_downloaded
        self.queue_status_lbl.setText(
            f"Run All: {s['done']}/{s['total']} creators done"
            f" | {videos} videos downloaded"
            f" | {s['failed']} failed"
        )
        for fp, card in self.cards.items():
            if fp.name == creator_name:
                card.set_queue_active(False)
                # Reload config to get updated last_activity
                card.config = CreatorConfig(fp)
                card._refresh_activity()
                card._refresh_header()
                if success:
                    card._set_state("done", "Queue: Complete")
                else:
                    card._set_state("error", "Queue: Failed")
                card._set_run_button_state(False)
                break

    def _on_queue_finished(self):
        """Queue completed — show summary, unlock cards."""
        self.pause_all_btn.setVisible(False)
        self.resume_all_btn.setVisible(False)
        # Unlock all cards
        for card in self.cards.values():
            card.set_manual_run_locked(False)
            card.set_queue_active(False)
        # Collect failures
        failed = [c.folder.name for c in self.cards.values()
                  if c._state in ("error", "partial")]
        self._failed_folders_cache = failed
        if failed:
            self.summary_btn.setVisible(True)
            self.summary_btn.setEnabled(True)

    def _on_queue_paused(self):
        """Queue is paused."""
        self.pause_all_btn.setVisible(False)
        self.resume_all_btn.setVisible(True)

    def _check_crash_recovery(self):
        """Check if a previous queue session was interrupted and offer to resume."""
        saved = self._queue_manager.load_saved_state()
        if not saved:
            return
        queue_folders = saved.get("queue", [])
        current_idx = saved.get("current_index", 0)
        total = len(queue_folders)
        if total == 0:
            return
        paused_at = saved.get("paused_at", "")
        creator_name = Path(paused_at).name if paused_at else "unknown"

        reply = QMessageBox.question(
            self,
            "Resume Previous Session?",
            f"A previous queue session was interrupted.\n\n"
            f"Progress: {current_idx}/{total} creators completed\n"
            f"Stopped at: @{creator_name}\n\n"
            f"Would you like to resume from where it left off?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._queue_manager.restore_from_state(saved)
            self.pause_all_btn.setVisible(False)
            self.resume_all_btn.setVisible(True)
            self.queue_status_lbl.setText(
                f"Queue: Restored — paused at {current_idx + 1}/{total} (@{creator_name}). Click Resume to continue."
            )
            self.queue_status_lbl.setVisible(True)
            # Lock all cards
            for card in self.cards.values():
                card.set_manual_run_locked(True)
        else:
            # User chose not to resume — clear the state file
            self._queue_manager._delete_state()

    def _on_card_run_started(self, folder):
        """Lock all other cards' Run buttons when one card starts running."""
        for fp, card in self.cards.items():
            if fp != Path(folder):
                card.set_manual_run_locked(True)

    def _on_card_run_finished(self, folder):
        """Unlock all cards when a manual (non-queue) run finishes."""
        # Only unlock if queue is NOT running (queue manages its own locking)
        if not self._queue_manager.isRunning():
            for card in self.cards.values():
                card.set_manual_run_locked(False)

    def _on_summary_clicked(self):
        dlg = FailedSummaryDialog(getattr(self, "_failed_folders_cache", []), self)
        dlg.exec_()

    def _on_toggle_daily_guard(self):
        self.daily_guard_enabled = not self.daily_guard_enabled
        if self.daily_guard_enabled:
            self._daily_guard_timer.start(self.daily_guard_interval_minutes * 60 * 1000)
            self.guard_b.setText("🛑  Stop Daily Guard")
            self.guard_b.setStyleSheet(
                "QPushButton { color:#E74C3C; background:#161b22; border:1px solid rgba(231,76,60,0.45); border-radius:5px; padding:6px 14px; font-weight:bold; font-size:12px; }"
                "QPushButton:hover { background:#1c2128; border-color:#E74C3C; }"
                "QPushButton:pressed { background:rgba(255,255,255,0.12); }"
            )
            self._daily_guard_cycle()  # run immediately once
            QMessageBox.information(
                self,
                "Daily Guard Started",
                f"Daily Guard active. Auto-check every {self.daily_guard_interval_minutes} minutes.",
            )
        else:
            self._daily_guard_timer.stop()
            self.guard_b.setText("🛡  Start Daily Guard")
            self.guard_b.setStyleSheet(
                "QPushButton { color:#43B581; background:#161b22; border:1px solid rgba(67,181,129,0.45); border-radius:5px; padding:6px 14px; font-weight:bold; font-size:12px; }"
                "QPushButton:hover { background:#1c2128; border-color:#43B581; }"
                "QPushButton:pressed { background:rgba(255,255,255,0.12); }"
            )
            QMessageBox.information(self, "Daily Guard Stopped", "Background auto-check disabled.")

    def _daily_guard_cycle(self):
        self._refresh_cards()
        for card in self.cards.values():
            if not card.is_running():
                card.trigger_run()

    def _on_reset_app(self):
        self._on_stop_all()
        self._refresh_cards()

    def _on_clear_history(self):
        if not self.cards:
            return
        if QMessageBox.question(
            self, "Clear History",
            f"Clear download history for all {len(self.cards)} creators?\n"
            "This allows re-downloading previously seen videos.",
            QMessageBox.Yes | QMessageBox.No
        ) != QMessageBox.Yes:
            return
        for fp, card in self.cards.items():
            cfg = CreatorConfig(fp)
            cfg.data["downloaded_ids"] = []
            cfg.data["last_activity"]  = {
                "date": None, "result": None,
                "tier_used": None, "videos_downloaded": 0,
            }
            cfg.save()
            card.config = CreatorConfig(fp)
            card._refresh_activity()
        QMessageBox.information(self, "Done", "Download history cleared for all creators.")

    def _on_save_all(self):
        for card in self.cards.values():
            card._auto_save()
        QMessageBox.information(self, "Saved", "All creator settings saved.")

    # ── import / export ───────────────────────────────────────────────────

    def _on_export(self):
        if not self.cards:
            QMessageBox.information(self, "Nothing to Export", "No creators configured yet.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Creator Settings",
            str(Path.home() / "onesoul_creators.json"),
            "JSON Files (*.json)"
        )
        if not path:
            return
        data = {
            "version":     "1.0",
            "exported_at": datetime.now().isoformat(),
            "creators":    [],
        }
        for fp in self.cards:
            cfg = CreatorConfig(fp)
            data["creators"].append({
                "folder_name":         fp.name,
                "creator_url":         cfg.creator_url,
                "n_videos":            cfg.n_videos,
                "editing_mode":        cfg.editing_mode,
                "preset_name":         cfg.preset_name,
                "split_duration":      cfg.split_duration,
                "duplication_control": cfg.duplication_control,
                "popular_fallback":    cfg.popular_fallback,
                "prefer_popular_first": cfg.prefer_popular_first,
                "randomize_links":     cfg.randomize_links,
                "keep_original_after_edit": cfg.keep_original_after_edit,
                "delete_before_download": cfg.delete_before_download,
                "uploading_target":      cfg.uploading_target,
            })
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        QMessageBox.information(self, "Exported", f"Settings saved to:\n{path}")

    def _on_import(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Creator Settings",
            str(Path.home()), "JSON Files (*.json)"
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            creators = data.get("creators", [])
            count = 0
            for entry in creators:
                name = entry.get("folder_name", "").strip()
                if not name:
                    continue
                folder = self.root / name
                folder.mkdir(parents=True, exist_ok=True)
                cfg = CreatorConfig(folder)
                for key in ("creator_url", "n_videos", "editing_mode",
                            "preset_name", "split_duration", "duplication_control",
                            "popular_fallback", "prefer_popular_first", "randomize_links",
                            "keep_original_after_edit", "delete_before_download",
                            "uploading_target"):
                    if key in entry:
                        cfg.data[key] = entry[key]
                cfg.save()
                count += 1
            self._refresh_cards()
            QMessageBox.information(
                self, "Import Complete",
                f"{count} creator(s) imported / updated."
            )
        except Exception as e:
            QMessageBox.critical(self, "Import Error", str(e))
