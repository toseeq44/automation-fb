"""
modules/creator_profiles/creator_card.py
Creator card widget for Downloading+Editing page.
"""

import os
import re
from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QPainter, QPainterPath, QPixmap
from PyQt5.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .config_manager import CreatorConfig, summarize_split_edit_settings
from .download_engine import CreatorDownloadWorker

_BG_CARD = "#161b22"
_BG_HOVER = "#1c2128"
_BG_INPUT = "#0a0e1a"
_CYAN = "#00d4ff"
_GREEN = "#43B581"
_RED = "#E74C3C"
_WARN = "#F39C12"
_BORDER = "rgba(0,212,255,0.2)"
_BORDER_HI = "rgba(0,212,255,0.5)"
_CARD_BORDER = "#0B4355"    # default card border — white
_CARD_BORDER_HI = "#F1CE04"                # hover card border  — yellow/gold
_ICON_RING = "#00D4FF"


def _hex_to_rgba(hex_color: str, alpha: float) -> str:
    hex_color = (hex_color or "").strip().lstrip("#")
    if len(hex_color) != 6:
        return f"rgba(0,212,255,{alpha})"
    try:
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        return f"rgba({r},{g},{b},{alpha})"
    except Exception:
        return f"rgba(0,212,255,{alpha})"


def _button_ss(
    fg: str,
    border_alpha: float = 0.45,
    bg: str = "#161b22",
    hover_bg: str = "#1c2128",
    border_color: str = None,
) -> str:
    bc = border_color or _hex_to_rgba(fg, border_alpha)
    return (
        "QPushButton {"
        f"  color:{fg}; background:{bg};"
        f"  border:1px solid {bc};"
        "  border-radius:5px; padding:6px 12px;"
        "  font-weight:bold; font-size:12px;"
        "}"
        f"QPushButton:hover {{ background:{hover_bg}; border-color:{fg}; }}"
        "QPushButton:pressed { background:rgba(255,255,255,0.12); }"
    )


def _input_ss() -> str:
    return (
        f"background:{_BG_INPUT}; color:white;"
        f" border:1px solid {_BORDER}; border-radius:4px; padding:5px 7px;"
        " font-size:12px;"
    )


def card_btn(text: str, color: str, width: int = 0) -> QPushButton:
    specs = {
        "green": (_GREEN, "rgba(67,181,129,0.3)", "#161b22"),
        "cyan": (_CYAN, "rgba(0,212,255,0.3)", "#161b22"),
        "red": (_RED, "rgba(231,76,60,0.3)", "#161b22"),
        "warn": (_WARN, "rgba(243,156,18,0.3)", "#161b22"),
    }
    fg, border_c, bg = specs.get(color, (_CYAN, _BORDER, "#161b22"))
    b = QPushButton(text)
    b.setStyleSheet(_button_ss(fg=fg, bg=bg, border_color=border_c))
    b.setMinimumHeight(30)
    b.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    if width:
        b.setFixedWidth(width)
    return b


def _lbl(text: str, size: int = 12, alpha: float = 0.6) -> QLabel:
    l = QLabel(text)
    l.setStyleSheet(
        f"color:white; font-size:{size}px;"
        " font-weight:bold; background:transparent; border:none;"
    )
    return l


class _NoWheelSpinBox(QSpinBox):
    """Let the parent scroll area consume mouse-wheel scrolling."""

    def wheelEvent(self, event):
        event.ignore()


class _NoWheelDoubleSpinBox(QDoubleSpinBox):
    """Let the parent scroll area consume mouse-wheel scrolling."""

    def wheelEvent(self, event):
        event.ignore()


class _NoWheelComboBox(QComboBox):
    """Prevent accidental hover-wheel selection changes on creator cards."""

    def wheelEvent(self, event):
        event.ignore()


# ── Platform icon assets ──────────────────────────────────────────────────────
import sys as _sys

def _resolve_asset_dir() -> str:
    """Resolve gui-redesign/assets path for both dev and frozen EXE."""
    if getattr(_sys, 'frozen', False):
        # Frozen EXE: assets are in _internal/gui-redesign/assets/
        base = getattr(_sys, '_MEIPASS', os.path.dirname(_sys.executable))
        candidate = os.path.join(base, 'gui-redesign', 'assets')
        if os.path.isdir(candidate):
            return candidate
        # Fallback: check _internal explicitly
        candidate2 = os.path.join(os.path.dirname(_sys.executable), '_internal', 'gui-redesign', 'assets')
        if os.path.isdir(candidate2):
            return candidate2
    # Dev mode: relative from this file
    return os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "..", "..", "gui-redesign", "assets")
    )

_ASSET_DIR = _resolve_asset_dir()

# PNG filename per platform keyword
_ICON_PNG = {
    "youtube":   "youtubeicon.png",
    "youtu.be":  "youtubeicon.png",
    "tiktok":    "tiktokicon.png",
    "instagram": "instagrameicon.png",
    "facebook":  "facebookicon.png",
    "fb.com":    "facebookicon.png",
}

# Text fallback (char, color) for platforms without PNG
_ICON_FALLBACK = {
    "twitter": ("\u229b", "#1DA1F2"),
    "x.com":   ("\u229b", "#1DA1F2"),
    "twitch":  ("\u25c8", "#9146FF"),
}


_GENERIC_NAME_SEGMENTS = {
    "reel", "reels", "video", "videos", "featured", "watch", "shorts",
    "posts", "post", "p", "tv", "stories", "story", "about", "photos",
    "photo", "live", "clips",
}

_SPEED_RE = re.compile(r"(\d+(?:\.\d+)?)\s*([KMG]?i?B/s)", re.IGNORECASE)
_ROCKET_ICON = "\U0001F680"
_DONE_ICON = "\u2705"
_ERROR_ICON = "\u274C"
_WARN_ICON = "\u26A0"


def _extract_creator_name(url: str) -> str:
    """Extract short @handle or last-path-segment from a creator URL."""
    if not url:
        return ""
    m = re.search(r"@([\w.]+)", url)
    if m:
        return f"@{m.group(1)}"
    m = re.search(r"/([^/?#]+)/?$", url.rstrip("/"))
    if m:
        return m.group(1)
    return url


def _make_zoomed_circle_icon(path: str, size: int = 22, zoom: float = 1.2) -> QPixmap:
    """
    Load icon image, center-crop with slight zoom, and clip to a circle.
    This hides square/black corners from source PNGs.
    """
    src = QPixmap(path)
    if src.isNull():
        return QPixmap()

    src_w = src.width()
    src_h = src.height()
    crop_w = max(1, int(src_w / max(zoom, 1.0)))
    crop_h = max(1, int(src_h / max(zoom, 1.0)))
    crop_x = max(0, (src_w - crop_w) // 2)
    crop_y = max(0, (src_h - crop_h) // 2)

    cropped = src.copy(crop_x, crop_y, crop_w, crop_h).scaled(
        size,
        size,
        Qt.KeepAspectRatioByExpanding,
        Qt.SmoothTransformation,
    )

    out = QPixmap(size, size)
    out.fill(Qt.transparent)

    painter = QPainter(out)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
    clip = QPainterPath()
    clip.addEllipse(0, 0, size, size)
    painter.setClipPath(clip)
    painter.drawPixmap(0, 0, cropped)
    painter.end()
    return out


def _div() -> QFrame:
    d = QFrame()
    d.setFrameShape(QFrame.HLine)
    d.setStyleSheet("background:rgba(0,212,255,0.1); border:none; max-height:1px;")
    return d


def _progress_bar_ss(bar_color: str) -> str:
    """Stylesheet for the card progress bar with the given bar fill color."""
    return (
        "QProgressBar {"
        "  background: #1a1f2e;"
        "  border: 1px solid rgba(0,212,255,0.15);"
        "  border-radius: 5px;"
        "  text-align: center;"
        "  color: white;"
        "  font-size: 10px;"
        "  font-weight: bold;"
        "}"
        "QProgressBar::chunk {"
        f"  background: {bar_color};"
        "  border-radius: 4px;"
        "}"
    )


class RocketProgressBar(QProgressBar):
    """Progress bar with a rocket glyph that moves with percentage."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rocket_visible = False

    def setRocketVisible(self, visible: bool):
        self._rocket_visible = bool(visible)
        self.update()

    def paintEvent(self, event):
        # [UI-Guard] Wrap entire paint in try/except so a stale native
        # handle or mid-destruction widget never crashes the app.
        try:
            super().paintEvent(event)

            if not self._rocket_visible:
                return
            if self.maximum() <= self.minimum():
                return

            rng = self.maximum() - self.minimum()
            if rng <= 0:
                return

            ratio = (self.value() - self.minimum()) / float(rng)
            ratio = max(0.0, min(1.0, ratio))

            r = self.rect().adjusted(6, 1, -6, -1)
            if r.width() <= 8:
                return

            painter = QPainter(self)
            if not painter.isActive():
                return
            painter.setRenderHint(QPainter.TextAntialiasing, True)
            f = painter.font()
            f.setPointSize(max(9, f.pointSize()))
            painter.setFont(f)
            fm = painter.fontMetrics()
            rocket_w = fm.horizontalAdvance(_ROCKET_ICON)
            max_x = max(r.left(), r.right() - rocket_w)
            x = int(r.left() + (max_x - r.left()) * ratio)
            baseline = int(r.center().y() + (fm.ascent() - fm.descent()) / 2)
            painter.drawText(x, baseline, _ROCKET_ICON)
            painter.end()
        except (RuntimeError, OSError, Exception):
            # Widget may be partially destroyed — silently ignore paint errors
            pass


class CreatorCard(QFrame):
    remove_requested = pyqtSignal(Path)
    run_started = pyqtSignal(Path)
    run_finished = pyqtSignal(Path)

    def __init__(self, folder: Path, root: Path, preset_names: list, parent=None):
        super().__init__(parent)
        self.folder = Path(folder)
        self.root = Path(root)
        self.preset_names = preset_names
        self.config = CreatorConfig(folder)
        self.worker = None
        self._state = "idle"
        self._queue_active = False   # True while this card is being processed by the queue
        self._manual_run_locked = False
        self._manual_run_active = False
        self._mouse_hovered = False
        self._search_highlight = False
        self._active_highlight = False
        self._current_speed = ""

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.setObjectName("creatorCard")
        self._style(False)
        self._build()
        self._load_values()
        self._refresh_activity()

    def _style(self, hovered: bool):
        self._mouse_hovered = bool(hovered)
        effective_hover = self._mouse_hovered or self._search_highlight or self._active_highlight
        bg = _BG_HOVER if effective_hover else _BG_CARD
        border = _CARD_BORDER_HI if effective_hover else _CARD_BORDER
        self.setStyleSheet(
            f"""
            QFrame#creatorCard {{
                background: {bg};
                border: 1px solid {border};
                border-radius: 12px;
            }}
            """
        )

    def set_search_highlight(self, highlighted: bool):
        self._search_highlight = bool(highlighted)
        self._style(self._mouse_hovered)

    def enterEvent(self, e):
        super().enterEvent(e)
        self._style(True)

    def leaveEvent(self, e):
        super().leaveEvent(e)
        self._style(False)

    def set_queue_active(self, active: bool):
        """Called by queue manager to mark active creator card."""
        self._queue_active = bool(active)
        self._active_highlight = bool(active)
        self.run_btn.setEnabled(not self._queue_active and not self._manual_run_locked)
        self._style(self._mouse_hovered)

    def set_manual_run_locked(self, locked: bool):
        """
        External lock from page-level coordinator:
        - True: block starting manual run on this card.
        - False: allow manual run.
        """
        self._manual_run_locked = bool(locked)
        if self.worker and self.worker.isRunning():
            return
        self.run_btn.setEnabled(not self._manual_run_locked and not self._queue_active)

    def _build(self):
        v = QVBoxLayout(self)
        v.setContentsMargins(11, 7, 11, 7)
        v.setSpacing(6)

        # ── Header: platform icon + creator name (H1 style) + status dot ──
        hrow = QHBoxLayout()
        hrow.setSpacing(6)

        self.platform_lbl = QLabel("\u25c8")
        self.platform_lbl.setFixedSize(30, 30)
        self.platform_lbl.setAlignment(Qt.AlignCenter)
        self.platform_lbl.setStyleSheet(
            f"color:{_CYAN}; font-size:16px; font-weight:bold;"
            f" background:#101722; border:1px solid {_ICON_RING}; border-radius:15px;"
        )
        hrow.addWidget(self.platform_lbl)

        self.title_lbl = QLabel("")
        _f = QFont("Segoe UI", 13)
        _f.setWeight(80)
        self.title_lbl.setFont(_f)
        self.title_lbl.setStyleSheet("color:#1ABC9C; background:transparent; border:none;")
        self.title_lbl.setWordWrap(False)
        hrow.addWidget(self.title_lbl, 1)

        # Compact activity summary on top-right
        act_top = QVBoxLayout()
        act_top.setSpacing(1)
        act_top.setContentsMargins(0, 0, 0, 0)

        self.act_top_lbl = QLabel("Last Activity")
        self.act_top_lbl.setStyleSheet(
            "color:white; font-size:11px; font-weight:bold; background:transparent; border:none;"
        )
        self.act_top_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        act_top.addWidget(self.act_top_lbl)

        self.act_top_date_lbl = QLabel("-")
        self.act_top_date_lbl.setStyleSheet(
            "color:white; font-size:11px; font-weight:bold; background:transparent; border:none;"
        )
        self.act_top_date_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        act_top.addWidget(self.act_top_date_lbl)

        self.act_top_status_lbl = QLabel("Status: -")
        self.act_top_status_lbl.setStyleSheet(
            "color:rgba(255,255,255,0.8); font-size:11px; font-weight:bold; background:transparent; border:none;"
        )
        self.act_top_status_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        act_top.addWidget(self.act_top_status_lbl)

        hrow.addLayout(act_top)
        v.addLayout(hrow)

        # ── Progress bar — full width below header ──
        self.progress_bar = RocketProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(16)
        self.progress_bar.setFormat("%p%")
        self.progress_bar.setRocketVisible(False)
        self.progress_bar.setStyleSheet(_progress_bar_ss(_CYAN))
        self.progress_bar.setVisible(False)
        v.addWidget(self.progress_bar)

        # ── Path + compact flags info ──
        parts = self.folder.parts
        short_path = str(self.folder) if len(parts) <= 3 else "…/" + "/".join(parts[-3:])
        self.path_lbl = QLabel(short_path)
        self.path_lbl.setToolTip(str(self.folder))
        self.path_lbl.setStyleSheet(
            "color:white; font-size:10px; background:transparent; border:none;"
        )
        self.path_lbl.setWordWrap(False)
        self.path_lbl.setMaximumHeight(18)
        v.addSpacing(2)
        v.addWidget(self.path_lbl)
        v.addWidget(_div())

        # ── Grid: Videos + Editing Mode (Flags row removed) ──
        controls_wrap = QVBoxLayout()
        controls_wrap.setSpacing(6)
        controls_wrap.setContentsMargins(0, 0, 0, 0)

        controls = QHBoxLayout()
        controls.setSpacing(8)
        controls.setContentsMargins(0, 0, 0, 0)

        controls.addWidget(_lbl("Max:"))
        self.n_spin = _NoWheelSpinBox()
        self.n_spin.setRange(1, 500)
        self.n_spin.setMinimumWidth(56)
        self.n_spin.setMaximumWidth(72)
        self.n_spin.setFixedHeight(30)
        self.n_spin.setStyleSheet(_input_ss())
        self.n_spin.valueChanged.connect(self._auto_save)
        controls.addWidget(self.n_spin)

        controls.addSpacing(6)
        controls.addWidget(_lbl("Upload:"))
        self.upload_spin = _NoWheelSpinBox()
        self.upload_spin.setRange(0, 500)
        self.upload_spin.setMinimumWidth(56)
        self.upload_spin.setMaximumWidth(72)
        self.upload_spin.setFixedHeight(30)
        self.upload_spin.setToolTip("Upload target per OneGo run (0 = skip)")
        self.upload_spin.setStyleSheet(_input_ss())
        self.upload_spin.valueChanged.connect(self._auto_save)
        controls.addWidget(self.upload_spin)

        controls.addSpacing(8)
        controls.addWidget(_lbl("Editing:"))
        self.mode_cb = _NoWheelComboBox()
        self.mode_cb.addItems(["None", "Preset", "Split", "Split + Edit"])
        self.mode_cb.setMinimumWidth(108)
        self.mode_cb.setMaximumWidth(150)
        self.mode_cb.setFixedHeight(30)
        self.mode_cb.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.mode_cb.setStyleSheet(_input_ss())
        self.mode_cb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.mode_cb.currentIndexChanged.connect(self._on_mode)
        controls.addWidget(self.mode_cb, 1)

        controls_wrap.addLayout(controls)

        edit_row = QHBoxLayout()
        edit_row.setSpacing(6)
        edit_row.setContentsMargins(0, 0, 0, 0)
        self.preset_cb = _NoWheelComboBox()
        self.preset_cb.addItems(self.preset_names or ["- no presets -"])
        self.preset_cb.setMinimumWidth(110)
        self.preset_cb.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.preset_cb.setStyleSheet(_input_ss())
        self.preset_cb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.preset_cb.currentTextChanged.connect(self._auto_save)
        edit_row.addWidget(self.preset_cb, 1)

        self.split_sp = _NoWheelDoubleSpinBox()
        self.split_sp.setRange(1.0, 3600.0)
        self.split_sp.setSuffix(" s")
        self.split_sp.setFixedWidth(92)
        self.split_sp.setStyleSheet(_input_ss())
        self.split_sp.valueChanged.connect(self._auto_save)
        edit_row.addWidget(self.split_sp)

        self.split_edit_btn = card_btn("Options", "cyan")
        self.split_edit_btn.setFixedWidth(88)
        self.split_edit_btn.clicked.connect(self._open_split_edit_dialog)
        edit_row.addWidget(self.split_edit_btn)
        edit_row.addStretch(1)

        self.edit_extra_w = QWidget()
        self.edit_extra_w.setStyleSheet("background:transparent; border:none;")
        self.edit_extra_w.setLayout(edit_row)
        self.edit_extra_w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        controls_wrap.addWidget(self.edit_extra_w)

        v.addLayout(controls_wrap)

        # ── Toggle buttons — left-aligned, no "Flags:" label ──
        toggles_wrap = QVBoxLayout()
        toggles_wrap.setSpacing(4)
        toggles_wrap.setContentsMargins(0, 2, 0, 0)

        top_toggles = QHBoxLayout()
        top_toggles.setSpacing(4)
        top_toggles.setContentsMargins(0, 0, 0, 0)

        bottom_toggles = QHBoxLayout()
        bottom_toggles.setSpacing(4)
        bottom_toggles.setContentsMargins(0, 0, 0, 0)

        self.dup_btn = card_btn("Skip", "green")
        self.dup_btn.setToolTip("Skip already downloaded videos")
        self.dup_btn.setCheckable(True)
        self.dup_btn.clicked.connect(self._on_toggle_changed)
        self.dup_btn.setMinimumHeight(28)
        self.dup_btn.setMaximumHeight(28)
        self.dup_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        top_toggles.addWidget(self.dup_btn, 1)

        self.pop_btn = card_btn("Popular", "warn")
        self.pop_btn.setToolTip("Use popular fallback")
        self.pop_btn.setCheckable(True)
        self.pop_btn.clicked.connect(self._on_toggle_changed)
        self.pop_btn.setMinimumHeight(28)
        self.pop_btn.setMaximumHeight(28)
        self.pop_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        top_toggles.addWidget(self.pop_btn, 1)

        self.rand_btn = card_btn("Random", "cyan")
        self.rand_btn.setToolTip("Randomize link order")
        self.rand_btn.setCheckable(True)
        self.rand_btn.clicked.connect(self._on_toggle_changed)
        self.rand_btn.setMinimumHeight(28)
        self.rand_btn.setMaximumHeight(28)
        self.rand_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        top_toggles.addWidget(self.rand_btn, 1)

        self.wm_btn = card_btn("WaterMark", "cyan")
        self.wm_btn.setToolTip("Enable watermark processing")
        self.wm_btn.setCheckable(True)
        self.wm_btn.clicked.connect(self._on_toggle_changed)
        self.wm_btn.setMinimumHeight(28)
        self.wm_btn.setMaximumHeight(28)
        self.wm_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        bottom_toggles.addWidget(self.wm_btn, 1)

        self.del_dl_btn = card_btn("Delete B4 DL", "warn")
        self.del_dl_btn.setToolTip("Delete old media before new downloads")
        self.del_dl_btn.setCheckable(True)
        self.del_dl_btn.clicked.connect(self._on_toggle_changed)
        self.del_dl_btn.setMinimumHeight(28)
        self.del_dl_btn.setMaximumHeight(28)
        self.del_dl_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        bottom_toggles.addWidget(self.del_dl_btn, 1)

        self.yt_type_cb = _NoWheelComboBox()
        self.yt_type_cb.addItems(["All", "Shorts", "Long"])
        self.yt_type_cb.setToolTip("YouTube content type: All / Shorts only / Long videos only")
        self.yt_type_cb.setMinimumHeight(28)
        self.yt_type_cb.setMaximumHeight(28)
        self.yt_type_cb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.yt_type_cb.setStyleSheet(
            "QComboBox { background: #161b22; color: #c9d1d9; border: 1px solid #30363d;"
            " border-radius: 4px; padding: 2px 6px; font-size: 11px; }"
        )
        self.yt_type_cb.currentIndexChanged.connect(self._on_yt_type_changed)
        self.yt_type_cb.setVisible(False)  # shown only for YouTube creators
        bottom_toggles.addWidget(self.yt_type_cb, 1)

        toggles_wrap.addLayout(top_toggles)
        toggles_wrap.addLayout(bottom_toggles)

        v.addLayout(toggles_wrap)
        v.addWidget(_div())

        # ── Last Activity — single wrappable label ──
        v.addWidget(_div())

        # ── Action row: Run / Edit / Remove + status ──
        ar = QHBoxLayout()
        ar.setSpacing(7)
        self.run_btn = card_btn("\u25b6 Run", "green")
        self.run_btn.clicked.connect(self._on_run)
        ar.addWidget(self.run_btn)

        self.pause_btn = card_btn("\u23f8 Pause", "warn")
        self.pause_btn.clicked.connect(self._on_pause)
        self.pause_btn.setVisible(False)
        ar.addWidget(self.pause_btn)

        self.resume_btn = card_btn("\u25b6 Resume", "green")
        self.resume_btn.clicked.connect(self._on_resume)
        self.resume_btn.setVisible(False)
        ar.addWidget(self.resume_btn)

        edit_b = card_btn("\u270f Edit", "cyan")
        edit_b.clicked.connect(self._on_edit)
        ar.addWidget(edit_b)

        rm_b = card_btn("\u2715", "red", 36)
        rm_b.clicked.connect(self._on_remove)
        ar.addWidget(rm_b)
        ar.addSpacing(6)

        self.status_lbl = QLabel("Waiting...")
        self.status_lbl.setStyleSheet(
            "color:white; font-size:11px; background:transparent; border:none;"
        )
        self.status_lbl.setWordWrap(True)
        self.status_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        ar.addWidget(self.status_lbl, 1)
        v.addLayout(ar)

    def _refresh_header(self):
        creator_url = (self.config.creator_url or "").strip()
        folder_name = self.folder.name.strip()
        if creator_url:
            extracted = (_extract_creator_name(creator_url) or "").lstrip("@").strip().lower()
            if not extracted or extracted in _GENERIC_NAME_SEGMENTS:
                name = folder_name
            else:
                name = folder_name
            u = creator_url.lower()
            # Try PNG icon first
            png_fname = next((v for k, v in _ICON_PNG.items() if k in u), None)
            if png_fname:
                icon_path = os.path.join(_ASSET_DIR, png_fname)
                if os.path.exists(icon_path):
                    pm = _make_zoomed_circle_icon(icon_path, size=22, zoom=1.24)
                    self.platform_lbl.clear()
                    self.platform_lbl.setPixmap(pm)
                    self.platform_lbl.setStyleSheet(
                        f"color:{_CYAN}; font-size:16px; font-weight:bold;"
                        f" background:#101722; border:1px solid {_ICON_RING}; border-radius:15px;"
                    )
                else:
                    char, color = next((v for k, v in _ICON_FALLBACK.items() if k in u), ("\u25c8", "#00d4ff"))
                    self.platform_lbl.clear()
                    self.platform_lbl.setText(char)
                    self.platform_lbl.setStyleSheet(
                        f"color:{color}; font-size:16px; font-weight:bold;"
                        f" background:#101722; border:1px solid {_ICON_RING}; border-radius:15px;"
                    )
            else:
                char, color = next((v for k, v in _ICON_FALLBACK.items() if k in u), ("\u25c8", "#00d4ff"))
                self.platform_lbl.clear()
                self.platform_lbl.setText(char)
                self.platform_lbl.setStyleSheet(
                    f"color:{color}; font-size:16px; font-weight:bold;"
                    f" background:#101722; border:1px solid {_ICON_RING}; border-radius:15px;"
                )
        else:
            name = folder_name
            self.platform_lbl.clear()
            self.platform_lbl.setText("\u25c8")
            self.platform_lbl.setStyleSheet(
                f"color:rgba(255,255,255,0.7); font-size:16px; font-weight:bold;"
                f" background:#101722; border:1px solid {_ICON_RING}; border-radius:15px;"
            )
        self.title_lbl.setText(name)

        # Show Shorts/Long dropdown only for YouTube creators
        is_yt = "youtube" in (creator_url or "").lower() or "youtu.be" in (creator_url or "").lower()
        self.yt_type_cb.setVisible(is_yt)

    def _load_values(self):
        c = self.config
        c.ensure_creator_url()
        mode_value = str(c.editing_mode).strip().lower()
        mode_map = {
            "none": 0,
            "preset": 1,
            "split": 2,
            "split_edit": 3,
            "0": 0,
            "1": 1,
            "2": 2,
            "3": 3,
        }
        mode_index = mode_map.get(mode_value, 0)

        # Prevent accidental autosave/overwrite while loading values into UI.
        widgets_to_block = [
            self.n_spin,
            self.upload_spin,
            self.split_sp,
            self.mode_cb,
            self.preset_cb,
            self.dup_btn,
            self.pop_btn,
            self.rand_btn,
            self.wm_btn,
            self.del_dl_btn,
        ]
        for w in widgets_to_block:
            w.blockSignals(True)
        self._loading_values = True
        try:
            self.n_spin.setValue(c.n_videos)
            self.upload_spin.setValue(c.uploading_target)
            self.split_sp.setValue(c.split_duration)
            self.mode_cb.setCurrentIndex(mode_index)
            if c.preset_name and c.preset_name in self.preset_names:
                self.preset_cb.setCurrentText(c.preset_name)

            self.dup_btn.setChecked(c.duplication_control)
            self.pop_btn.setChecked(c.popular_fallback)
            self.rand_btn.setChecked(c.randomize_links)
            self.wm_btn.setChecked(c.watermark_enabled)
            self.del_dl_btn.setChecked(c.delete_before_download)
            _yt_map = {"all": 0, "shorts": 1, "long": 2}
            self.yt_type_cb.setCurrentIndex(_yt_map.get(c.yt_content_type, 0))
        finally:
            self._loading_values = False
            for w in widgets_to_block:
                w.blockSignals(False)

        self._refresh_toggle_styles()
        self._update_edit_vis()
        self._refresh_split_edit_button()
        self._refresh_header()

    def _refresh_toggle_styles(self):
        for btn in (
            self.dup_btn,
            self.pop_btn,
            self.rand_btn,
            self.wm_btn,
            self.del_dl_btn,
        ):
            if btn.isChecked():
                btn.setStyleSheet(_button_ss(
                    fg=_CYAN,
                    bg="#161b22",
                    border_color=_hex_to_rgba(_CYAN, 0.45),
                ))
            else:
                btn.setStyleSheet(_button_ss(
                    fg="#9aa",
                    bg="#222",
                    border_color="rgba(255,255,255,0.12)",
                ))

    def _auto_save(self):
        mode = ["none", "preset", "split", "split_edit"][self.mode_cb.currentIndex()]
        self.config.data.update(
            {
                "n_videos": self.n_spin.value(),
                "uploading_target": self.upload_spin.value(),
                "editing_mode": mode,
                "preset_name": self.preset_cb.currentText(),
                "split_duration": self.split_sp.value(),
                "duplication_control": self.dup_btn.isChecked(),
                "popular_fallback": self.pop_btn.isChecked(),
                "prefer_popular_first": False,
                "randomize_links": self.rand_btn.isChecked(),
                "watermark_enabled": self.wm_btn.isChecked(),
                "delete_before_download": self.del_dl_btn.isChecked(),
                "yt_content_type": ["all", "shorts", "long"][self.yt_type_cb.currentIndex()],
            }
        )
        self.config.save()
        self._refresh_header()

    def _on_mode(self):
        self._update_edit_vis()
        self._auto_save()
        if self.mode_cb.currentIndex() == 3 and not getattr(self, "_loading_values", False):
            self._open_split_edit_dialog()

    def _update_edit_vis(self):
        m = self.mode_cb.currentIndex()
        self.preset_cb.setVisible(m == 1)
        self.split_sp.setVisible(m in (2, 3))
        self.split_edit_btn.setVisible(m == 3)
        if hasattr(self, "edit_extra_w"):
            self.edit_extra_w.setVisible(m in (1, 2, 3))

    def _refresh_split_edit_button(self):
        settings = self.config.split_edit_settings
        summary = summarize_split_edit_settings(settings)
        self.split_edit_btn.setToolTip(summary)
        self.split_edit_btn.setText("Options")

    def _on_toggle_changed(self):
        self._refresh_toggle_styles()
        self._auto_save()

    def _on_yt_type_changed(self):
        self._auto_save()

    def _set_run_button_state(self, running: bool, paused: bool = False):
        if running:
            self.run_btn.setText("\u23f9 Stop")
            self.run_btn.setEnabled(True)
            self.run_btn.setStyleSheet(_button_ss(
                fg=_RED,
                bg="#161b22",
                border_color="rgba(231,76,60,0.45)",
            ))
            self.pause_btn.setVisible(not paused)
            self.resume_btn.setVisible(paused)
        else:
            self.run_btn.setText("\u25b6 Run")
            self.run_btn.setEnabled(not self._manual_run_locked and not self._queue_active)
            self.run_btn.setStyleSheet(_button_ss(
                fg=_GREEN,
                bg="#161b22",
                border_color="rgba(67,181,129,0.45)",
            ))
            self.pause_btn.setVisible(False)
            self.resume_btn.setVisible(False)

    def _on_run(self):
        # Guard: do not allow manual run while queue is processing this card
        if self._queue_active:
            self.run_finished.emit(self.folder)
            return
        if self._manual_run_locked and not (self.worker and self.worker.isRunning()):
            self.run_finished.emit(self.folder)
            return

        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self._set_state("idle", "Stopping...")
            return

        # Always use creator URL — never fall back to links files
        url = (self.config.creator_url or "").strip()
        if not url:
            inferred = self.config.ensure_creator_url()
            if inferred:
                self.config = CreatorConfig(self.folder)
                self._refresh_header()
                url = inferred
        if not url:
            self._set_state("error", "No creator URL set. Use Edit to add the profile URL.")
            self.run_finished.emit(self.folder)
            return

        self._auto_save()
        self._set_state("running", "Starting...")
        self._set_run_button_state(True)
        self.worker = CreatorDownloadWorker(self.folder, url)
        def _filter_card_progress(m):
            import time
            now = time.time()
            if now - getattr(self, '_last_ui_update_time', 0.0) < 0.1:
                return
            self._last_ui_update_time = now
            try:
                from modules.shared.progress_filter import filter_for_gui
                filtered = filter_for_gui(m)
                if filtered is None:
                    return
                m = filtered
            except Exception:
                pass  # use original message if filter unavailable or raises
            self._set_state("running", m)
        self._progress_cb = _filter_card_progress  # keep ref for disconnect
        self.worker.progress.connect(self._progress_cb)
        self.worker.download_speed.connect(self._on_download_speed)
        self.worker.progress_percent.connect(self._on_progress_percent)
        self.worker.paused.connect(self._on_worker_paused)
        self.worker.finished.connect(self._on_finished)
        self.worker.login_required.connect(self._on_login_required)
        self._manual_run_active = True
        self.run_started.emit(self.folder)
        self.worker.start()

    def _on_pause(self):
        if self.worker and self.worker.isRunning():
            self.worker.pause()
            self._set_state("partial", "Pausing...")
            self._set_run_button_state(True, paused=True)

    def _on_resume(self):
        if self.worker and self.worker.isRunning():
            self.worker.resume()
            self._set_state("running", "Resuming...")
            self._set_run_button_state(True, paused=False)

    def _on_worker_paused(self):
        self._set_state("partial", "Paused.")
        self._set_run_button_state(True, paused=True)

    def _on_login_required(self, platform_key: str):
        """Show popup telling user to login in IXBrowser."""
        QMessageBox.warning(
            self,
            "Login Required",
            f"IXBrowser ki 'onesoul' profile mein {platform_key.upper()} pe login karein.\n\n"
            f"IXBrowser browser window mein jaake login karein,\n"
            f"phir dubara Run dabayein.",
        )

    def _on_finished(self, result: dict):
        # Disconnect all signals to prevent memory leak on repeated runs
        if self.worker:
            for sig, slot in [
                (self.worker.progress,          getattr(self, '_progress_cb', None)),
                (self.worker.download_speed,    self._on_download_speed),
                (self.worker.progress_percent,  self._on_progress_percent),
                (self.worker.paused,            self._on_worker_paused),
                (self.worker.finished,          self._on_finished),
                (self.worker.login_required,    self._on_login_required),
            ]:
                if slot is not None:
                    try:
                        sig.disconnect(slot)
                    except Exception:
                        pass
        self.config = CreatorConfig(self.folder)
        self._refresh_activity()
        self._refresh_header()
        status_code = str(result.get("status_code", "") or "")
        downloaded = int(result.get("downloaded", 0) or 0)
        target = int(result.get("target", 0) or 0)
        if status_code == "success" or result.get("success") and downloaded >= target:
            self._set_state("done", "Done")
            self._set_completion_progress(downloaded, target, "done")
        elif status_code == "stopped":
            self._set_state("idle", "Stopped")
        elif status_code == "partial_download" or (downloaded > 0 and target > 0):
            self._set_state("partial", "Partial")
            self._set_completion_progress(downloaded, target, "partial")
        else:
            label = {
                "failed_auth": "Auth required",
                "link_grab_failed": "No links found",
                "download_failed": "Download failed",
                "runtime_unavailable": "Runtime issue",
            }.get(status_code, "Failed")
            self._set_state("error", label)
        self._set_run_button_state(False)
        if self._manual_run_active:
            self._manual_run_active = False
            self.run_finished.emit(self.folder)

    def _extract_speed(self, msg: str) -> str:
        if not msg:
            return ""
        m = _SPEED_RE.search(msg)
        if not m:
            return ""
        return f"{m.group(1)} {m.group(2).upper()}"

    def _refresh_progress_format(self):
        if self._current_speed:
            self.progress_bar.setFormat(f"%p%  |  {self._current_speed}")
        else:
            self.progress_bar.setFormat("%p%")

    def _set_completion_progress(self, downloaded: int, target: int, state: str) -> None:
        """Set final completion percentage from downloaded vs target."""
        try:
            downloaded_i = max(0, int(downloaded or 0))
            target_i = max(0, int(target or 0))
        except Exception:
            return

        if state == "done":
            pct = 100
        elif target_i > 0:
            pct = int(round((downloaded_i / target_i) * 100))
        else:
            return

        self.progress_bar.setValue(max(0, min(100, pct)))

    def _set_state(self, state: str, msg: str):
        self._state = state
        msg_str = msg or ""
        self.status_lbl.setText(msg_str[:120])

        if state == "running":
            self._active_highlight = True
            self._style(self._mouse_hovered)
            self.progress_bar.setVisible(True)
            self.progress_bar.setRocketVisible(True)
            self.progress_bar.setStyleSheet(_progress_bar_ss(_CYAN))
            speed = self._extract_speed(msg_str)
            if speed:
                self._current_speed = speed
            # Parse percentage from message if available
            pct_match = re.search(r"(\d+(?:\.\d+)?)%", msg_str)
            if pct_match:
                pct = int(float(pct_match.group(1)))
                self.progress_bar.setValue(max(0, min(100, pct)))
            elif "start" in msg_str.lower():
                self.progress_bar.setValue(0)
            self._refresh_progress_format()
        elif state == "done":
            self._active_highlight = False
            self._style(self._mouse_hovered)
            self.progress_bar.setVisible(True)
            self.progress_bar.setRocketVisible(False)
            self.progress_bar.setValue(100)
            self._current_speed = ""
            self.progress_bar.setFormat(f"{_DONE_ICON} %p%")
            self.progress_bar.setStyleSheet(_progress_bar_ss(_GREEN))
        elif state == "error":
            self._active_highlight = False
            self._style(self._mouse_hovered)
            self.progress_bar.setVisible(True)
            self.progress_bar.setRocketVisible(False)
            self._current_speed = ""
            self.progress_bar.setFormat(f"{_ERROR_ICON} %p%")
            self.progress_bar.setStyleSheet(_progress_bar_ss(_RED))
        elif state == "partial":
            self._active_highlight = False
            self._style(self._mouse_hovered)
            self.progress_bar.setVisible(True)
            self.progress_bar.setRocketVisible(False)
            self._current_speed = ""
            self.progress_bar.setFormat(f"{_WARN_ICON} %p%")
            self.progress_bar.setStyleSheet(_progress_bar_ss(_WARN))
        else:
            # idle — hide bar and reset
            self._active_highlight = False
            self._style(self._mouse_hovered)
            self.progress_bar.setVisible(False)
            self.progress_bar.setRocketVisible(False)
            self.progress_bar.setValue(0)
            self._current_speed = ""
            self.progress_bar.setFormat("%p%")

    def _on_progress_percent(self, pct: int):
        """Update progress bar percentage during download."""
        try:  # [UI-Guard] protect against widget-destroyed race
            if self._state != "running":
                return
            import time
            now = time.time()
            if pct < 100 and now - getattr(self, '_last_pct_update_time', 0.0) < 0.05:
                # 20 FPS max for pure progress bar
                return
            self._last_pct_update_time = now
            pct = max(0, min(100, pct))
            self.progress_bar.setValue(pct)
            self.progress_bar.setVisible(True)
            self._refresh_progress_format()
        except RuntimeError:
            pass

    def _on_download_speed(self, speed: str):
        if self._state != "running":
            return
        speed = (speed or "").strip()
        if not speed:
            return
        import time
        now = time.time()
        if now - getattr(self, '_last_speed_update_time', 0.0) < 0.2:
            return
        self._last_speed_update_time = now
        self._current_speed = speed
        self._refresh_progress_format()

    def _refresh_activity(self):
        a = self.config.last_activity
        if not a or not a.get("date"):
            self.act_top_date_lbl.setText("-")
            self.act_top_status_lbl.setText("Status: -")
            self.act_top_status_lbl.setStyleSheet(
                "color:rgba(255,255,255,0.8); font-size:11px; font-weight:bold; background:transparent; border:none;"
            )
            return
        try:
            dt = datetime.fromisoformat(a["date"])
            ds = dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            ds = str(a.get("date", "-"))
        res = a.get("result", "-") or "-"
        icon = {"success": "\u2713", "failed": "\u2717", "partial": "!"}.get(res.lower(), "")
        self.act_top_date_lbl.setText(ds)
        self.act_top_status_lbl.setText(f"Status: {icon} {res.capitalize()}")
        status_color = {
            "success": _GREEN,
            "failed": _RED,
            "partial": _WARN,
        }.get(res.lower(), "rgba(255,255,255,0.8)")
        self.act_top_status_lbl.setStyleSheet(
            f"color:{status_color}; font-size:11px; font-weight:bold; background:transparent; border:none;"
        )

    def _on_edit(self):
        from .edit_dialog import EditCreatorDialog

        dlg = EditCreatorDialog(self.config, self.preset_names, self)
        if dlg.exec_():
            self.config = CreatorConfig(self.folder)
            self._load_values()
            self._refresh_activity()

    def _open_split_edit_dialog(self):
        from .split_edit_dialog import SplitEditDialog

        dlg = SplitEditDialog(self.config.split_edit_settings, self, "Split + Edit Options")
        if dlg.exec_():
            self.config.data["split_edit_settings"] = dlg.get_settings()
            self.config.save()
            self.config = CreatorConfig(self.folder)
            self._refresh_split_edit_button()

    def _on_remove(self):
        r = QMessageBox.question(
            self,
            "Remove Creator",
            f"Delete '{self.folder.name}' permanently?\n\n"
            "This will remove the card and delete the creator folder from disk.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if r == QMessageBox.Yes:
            self.remove_requested.emit(self.folder)

    def trigger_run(self):
        if not (self.worker and self.worker.isRunning()):
            self._on_run()

    def stop_worker(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            finished = self.worker.wait(3000)
            if not finished:
                self.worker.terminate()  # force-kill if still running after 3s
            if self._manual_run_active:
                self._manual_run_active = False
                self.run_finished.emit(self.folder)
        self._set_run_button_state(False)
        if self._state == "running":
            self._set_state("idle", "Stopped.")

    def is_running(self) -> bool:
        return bool(self.worker and self.worker.isRunning())
