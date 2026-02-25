"""
modules/creator_profiles/creator_card.py
Creator card widget for Downloading+Editing page.
"""

import os
import re
from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QPixmap
from PyQt5.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .config_manager import CreatorConfig
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
    fg, border_c, bg = specs.get(color, (_CYAN, _BORDER, _BG_INPUT))
    b = QPushButton(text)
    b.setStyleSheet(
        f"QPushButton {{"
        f"  color:{fg}; background:{bg};"
        f"  border:1px solid {border_c};"
        f"  border-radius:5px; padding:5px 13px;"
        f"  font-weight:bold; font-size:12px;"
        f"}}"
        f"QPushButton:hover {{ background:rgba(255,255,255,0.05); border-color:{fg}; }}"
        f"QPushButton:pressed {{ background:rgba(255,255,255,0.1); }}"
    )
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


# ── Platform icon assets ──────────────────────────────────────────────────────
_ASSET_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 "..", "..", "gui-redesign", "assets")
)

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
    "twitter": ("⊛", "#1DA1F2"),
    "x.com":   ("⊛", "#1DA1F2"),
    "twitch":  ("◈", "#9146FF"),
}


_GENERIC_NAME_SEGMENTS = {
    "reel", "reels", "video", "videos", "featured", "watch", "shorts",
    "posts", "post", "p", "tv", "stories", "story", "about", "photos",
    "photo", "live", "clips",
}


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


def _div() -> QFrame:
    d = QFrame()
    d.setFrameShape(QFrame.HLine)
    d.setStyleSheet("background:rgba(0,212,255,0.1); border:none; max-height:1px;")
    return d


class CreatorCard(QFrame):
    remove_requested = pyqtSignal(Path)

    _DOT = {
        "idle": "#3a3a3a",
        "running": _CYAN,
        "done": _GREEN,
        "error": _RED,
    }

    def __init__(self, folder: Path, root: Path, preset_names: list, parent=None):
        super().__init__(parent)
        self.folder = Path(folder)
        self.root = Path(root)
        self.preset_names = preset_names
        self.config = CreatorConfig(folder)
        self.worker = None
        self._state = "idle"

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.setObjectName("creatorCard")
        self._style(False)
        self._build()
        self._load_values()
        self._refresh_activity()

    def _style(self, hovered: bool):
        bg = _BG_HOVER if hovered else _BG_CARD
        border = _CARD_BORDER_HI if hovered else _CARD_BORDER
        self.setStyleSheet(
            f"""
            QFrame#creatorCard {{
                background: {bg};
                border: 1px solid {border};
                border-radius: 12px;
            }}
            """
        )

    def enterEvent(self, e):
        self._style(True)

    def leaveEvent(self, e):
        self._style(False)

    def _build(self):
        v = QVBoxLayout(self)
        v.setContentsMargins(11, 7, 11, 7)
        v.setSpacing(6)

        # ── Header: platform icon + creator name (H1 style) + status dot ──
        hrow = QHBoxLayout()
        hrow.setSpacing(6)

        self.platform_lbl = QLabel("◈")
        self.platform_lbl.setFixedWidth(22)
        self.platform_lbl.setAlignment(Qt.AlignCenter)
        self.platform_lbl.setStyleSheet(
            f"color:{_CYAN}; font-size:15px; font-weight:bold; background:transparent; border:none;"
        )
        hrow.addWidget(self.platform_lbl)

        self.title_lbl = QLabel("")
        _f = QFont("Segoe UI", 13)
        _f.setWeight(80)
        self.title_lbl.setFont(_f)
        self.title_lbl.setStyleSheet("color:#1ABC9C; background:transparent; border:none;")
        self.title_lbl.setWordWrap(False)
        hrow.addWidget(self.title_lbl, 1)

        self.dot = QLabel("●")
        self.dot.setStyleSheet(
            f"color:{self._DOT['idle']}; font-size:13px; background:transparent; border:none;"
        )
        hrow.addWidget(self.dot)
        v.addLayout(hrow)

        # ── Path + compact flags info ──
        self.path_lbl = QLabel(str(self.folder))
        self.path_lbl.setStyleSheet(
            "color:white; font-size:10px; background:transparent; border:none;"
        )
        self.path_lbl.setWordWrap(True)
        v.addSpacing(2)
        v.addWidget(self.path_lbl)

        self.flags_lbl = QLabel("")
        self.flags_lbl.setStyleSheet(
            "color:white; font-size:10px; font-weight:bold; background:transparent; border:none;"
        )
        v.addSpacing(2)
        v.addWidget(self.flags_lbl)
        v.addWidget(_div())

        # ── Grid: Videos + Editing Mode (Flags row removed) ──
        g = QGridLayout()
        g.setHorizontalSpacing(8)
        g.setVerticalSpacing(6)
        g.setColumnStretch(1, 1)
        g.setColumnMinimumWidth(0, 120)

        g.addWidget(_lbl("Videos to Download:"), 0, 0)
        self.n_spin = QSpinBox()
        self.n_spin.setRange(1, 500)
        self.n_spin.setFixedWidth(72)
        self.n_spin.setStyleSheet(_input_ss())
        self.n_spin.valueChanged.connect(self._auto_save)
        g.addWidget(self.n_spin, 0, 1, Qt.AlignLeft)

        g.addWidget(_lbl("Editing Mode:"), 1, 0)
        edit_row = QHBoxLayout()
        edit_row.setSpacing(6)
        edit_row.setContentsMargins(0, 0, 0, 0)

        self.mode_cb = QComboBox()
        self.mode_cb.addItems(["None", "Preset", "Split"])
        self.mode_cb.setFixedWidth(72)
        self.mode_cb.setStyleSheet(_input_ss())
        self.mode_cb.currentIndexChanged.connect(self._on_mode)
        edit_row.addWidget(self.mode_cb)

        self.preset_cb = QComboBox()
        self.preset_cb.addItems(self.preset_names or ["- no presets -"])
        self.preset_cb.setStyleSheet(_input_ss())
        self.preset_cb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.preset_cb.currentTextChanged.connect(self._auto_save)
        edit_row.addWidget(self.preset_cb, 1)

        self.split_sp = QDoubleSpinBox()
        self.split_sp.setRange(1.0, 3600.0)
        self.split_sp.setSuffix(" s")
        self.split_sp.setFixedWidth(82)
        self.split_sp.setStyleSheet(_input_ss())
        self.split_sp.valueChanged.connect(self._auto_save)
        edit_row.addWidget(self.split_sp)

        ew = QWidget()
        ew.setStyleSheet("background:transparent; border:none;")
        ew.setLayout(edit_row)
        g.addWidget(ew, 1, 1)

        v.addLayout(g)

        # ── Toggle buttons — left-aligned, no "Flags:" label ──
        toggles = QHBoxLayout()
        toggles.setSpacing(6)
        toggles.setContentsMargins(0, 2, 0, 0)

        self.dup_btn = card_btn("Skip Seen", "green")
        self.dup_btn.setCheckable(True)
        self.dup_btn.clicked.connect(self._on_toggle_changed)
        toggles.addWidget(self.dup_btn)

        self.pop_btn = card_btn("Popular", "warn")
        self.pop_btn.setCheckable(True)
        self.pop_btn.clicked.connect(self._on_toggle_changed)
        toggles.addWidget(self.pop_btn)

        self.rand_btn = card_btn("Random", "cyan")
        self.rand_btn.setCheckable(True)
        self.rand_btn.clicked.connect(self._on_toggle_changed)
        toggles.addWidget(self.rand_btn)

        self.wm_btn = card_btn("WaterMark", "cyan")
        self.wm_btn.setCheckable(True)
        self.wm_btn.clicked.connect(self._on_toggle_changed)
        toggles.addWidget(self.wm_btn)
        toggles.addStretch()

        v.addLayout(toggles)
        v.addWidget(_div())

        # ── Last Activity — single wrappable label ──
        act_hdr = QLabel("Last Activity")
        act_hdr.setStyleSheet(
            "color:white; font-size:11px; font-weight:bold; background:transparent; border:none;"
        )
        v.addWidget(act_hdr)

        self.act_info_lbl = QLabel("<b>Date:</b> -  |  <b>Result:</b> -  |  <b>Tier:</b> -")
        self.act_info_lbl.setStyleSheet(
            "color:white; font-size:11px; font-weight:bold; background:transparent; border:none;"
        )
        self.act_info_lbl.setTextFormat(Qt.RichText)
        self.act_info_lbl.setWordWrap(True)
        v.addWidget(self.act_info_lbl)
        v.addWidget(_div())

        # ── Action row: Run / Edit / Remove + status ──
        ar = QHBoxLayout()
        ar.setSpacing(7)
        self.run_btn = card_btn("▶ Run", "green")
        self.run_btn.clicked.connect(self._on_run)
        ar.addWidget(self.run_btn)

        edit_b = card_btn("✏ Edit", "cyan")
        edit_b.clicked.connect(self._on_edit)
        ar.addWidget(edit_b)

        rm_b = card_btn("✕", "red", 36)
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
                    pm = QPixmap(icon_path).scaled(
                        18, 18, Qt.KeepAspectRatio, Qt.SmoothTransformation
                    )
                    self.platform_lbl.clear()
                    self.platform_lbl.setPixmap(pm)
                else:
                    char, color = next((v for k, v in _ICON_FALLBACK.items() if k in u), ("◈", "#00d4ff"))
                    self.platform_lbl.clear()
                    self.platform_lbl.setText(char)
                    self.platform_lbl.setStyleSheet(
                        f"color:{color}; font-size:15px; font-weight:bold; background:transparent; border:none;"
                    )
            else:
                char, color = next((v for k, v in _ICON_FALLBACK.items() if k in u), ("◈", "#00d4ff"))
                self.platform_lbl.clear()
                self.platform_lbl.setText(char)
                self.platform_lbl.setStyleSheet(
                    f"color:{color}; font-size:15px; font-weight:bold; background:transparent; border:none;"
                )
        else:
            name = folder_name
            self.platform_lbl.clear()
            self.platform_lbl.setText("◈")
            self.platform_lbl.setStyleSheet(
                "color:rgba(255,255,255,0.4); font-size:15px; font-weight:bold; background:transparent; border:none;"
            )
        self.title_lbl.setText(name)
        flags = []
        flags.append(f"✂ {self.split_sp.value():.1f}s")
        flags.append(f"👤 Max: {self.n_spin.value()}")
        flags.append("Skip" if self.dup_btn.isChecked() else "Dup")
        if self.pop_btn.isChecked():
            flags.append("Pop")
        if self.rand_btn.isChecked():
            flags.append("Rand")
        flags.append("Orig:K" if self.config.keep_original_after_edit else "Orig:D")
        self.flags_lbl.setText(" | ".join(flags))
        self.flags_lbl.setToolTip(
            "Orig:K = Keep original after editing\n"
            "Orig:D = Delete original after editing"
        )

    def _load_values(self):
        c = self.config
        c.ensure_creator_url()
        mode_value = str(c.editing_mode).strip().lower()
        mode_map = {"none": 0, "preset": 1, "split": 2, "0": 0, "1": 1, "2": 2}
        mode_index = mode_map.get(mode_value, 0)

        # Prevent accidental autosave/overwrite while loading values into UI.
        widgets_to_block = [
            self.n_spin,
            self.split_sp,
            self.mode_cb,
            self.preset_cb,
            self.dup_btn,
            self.pop_btn,
            self.rand_btn,
            self.wm_btn,
        ]
        for w in widgets_to_block:
            w.blockSignals(True)
        try:
            self.n_spin.setValue(c.n_videos)
            self.split_sp.setValue(c.split_duration)
            self.mode_cb.setCurrentIndex(mode_index)
            if c.preset_name and c.preset_name in self.preset_names:
                self.preset_cb.setCurrentText(c.preset_name)

            self.dup_btn.setChecked(c.duplication_control)
            self.pop_btn.setChecked(c.popular_fallback)
            self.rand_btn.setChecked(c.randomize_links)
            self.wm_btn.setChecked(c.watermark_enabled)
        finally:
            for w in widgets_to_block:
                w.blockSignals(False)

        self._refresh_toggle_styles()
        self._update_edit_vis()
        self._refresh_header()

    def _refresh_toggle_styles(self):
        for btn, on_color, off_bg in (
            (self.dup_btn, "#1a5c1a", "#222"),
            (self.pop_btn, "#6a4a0a", "#222"),
            (self.rand_btn, "#0a3f4b", "#222"),
            (self.wm_btn,  "#1a3a5c", "#222"),
        ):
            if btn.isChecked():
                btn.setStyleSheet(
                    f"QPushButton {{ background:{on_color}; color:white; border:1px solid rgba(0,212,255,0.25); border-radius:5px; padding:5px 10px; font-weight:bold; }}"
                    "QPushButton:hover { background:rgba(255,255,255,0.12); border-color: #00d4ff; }"
                )
            else:
                btn.setStyleSheet(
                    f"QPushButton {{ background:{off_bg}; color:#9aa; border:1px solid rgba(255,255,255,0.08); border-radius:5px; padding:5px 10px; font-weight:bold; }}"
                    "QPushButton:hover { background:#2a2a2a; border-color: rgba(0,212,255,0.35); }"
                )

    def _auto_save(self):
        mode = ["none", "preset", "split"][self.mode_cb.currentIndex()]
        self.config.data.update(
            {
                "n_videos": self.n_spin.value(),
                "editing_mode": mode,
                "preset_name": self.preset_cb.currentText(),
                "split_duration": self.split_sp.value(),
                "duplication_control": self.dup_btn.isChecked(),
                "popular_fallback": self.pop_btn.isChecked(),
                "prefer_popular_first": False,
                "randomize_links": self.rand_btn.isChecked(),
                "watermark_enabled": self.wm_btn.isChecked(),
            }
        )
        self.config.save()
        self._refresh_header()

    def _on_mode(self):
        self._update_edit_vis()
        self._auto_save()

    def _update_edit_vis(self):
        m = self.mode_cb.currentIndex()
        self.preset_cb.setVisible(m == 1)
        self.split_sp.setVisible(m == 2)

    def _on_toggle_changed(self):
        self._refresh_toggle_styles()
        self._auto_save()

    def _set_run_button_state(self, running: bool):
        if running:
            self.run_btn.setText("⏹ Stop")
            self.run_btn.setStyleSheet(
                f"QPushButton {{ color:{_RED}; background:#2a1414; border:1px solid rgba(231,76,60,0.4); border-radius:5px; padding:5px 13px; font-weight:bold; font-size:12px; }}"
                "QPushButton:hover { background:rgba(231,76,60,0.1); }"
            )
        else:
            self.run_btn.setText("▶ Run")
            self.run_btn.setStyleSheet(
                f"QPushButton {{ color:{_GREEN}; background:#0d2a1a; border:1px solid rgba(67,181,129,0.3); border-radius:5px; padding:5px 13px; font-weight:bold; font-size:12px; }}"
                "QPushButton:hover { background:rgba(67,181,129,0.08); }"
            )

    def _on_run(self):
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
            return

        self._auto_save()
        self._set_state("running", "Starting...")
        self._set_run_button_state(True)
        self.worker = CreatorDownloadWorker(self.folder, url)
        self.worker.progress.connect(lambda m: self._set_state("running", m))
        self.worker.finished.connect(self._on_finished)
        self.worker.start()

    def _on_finished(self, result: dict):
        self.config = CreatorConfig(self.folder)
        self._refresh_activity()
        self._refresh_header()
        if result.get("success"):
            self._set_state("done", f"Done: {result.get('downloaded', 0)} | {result.get('tier_used') or 'N/A'}")
        else:
            self._set_state("error", f"Failed: {(result.get('error') or 'unknown')[:70]}")
        self._set_run_button_state(False)

    def _set_state(self, state: str, msg: str):
        self._state = state
        self.status_lbl.setText((msg or "")[:120])
        self.dot.setStyleSheet(
            f"color:{self._DOT.get(state, '#3a3a3a')}; font-size:13px; background:transparent; border:none;"
        )

    def _refresh_activity(self):
        a = self.config.last_activity
        if not a or not a.get("date"):
            self.act_info_lbl.setText("<b>Date:</b> -  |  <b>Result:</b> -  |  <b>Tier:</b> -")
            return
        try:
            dt = datetime.fromisoformat(a["date"])
            ds = dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            ds = str(a.get("date", "-"))
        res = a.get("result", "-") or "-"
        icon = {"success": "✓", "failed": "✗", "partial": "!"}.get(res, "")
        tier = a.get("tier_used") or "-"
        self.act_info_lbl.setText(
            f"<b>Date:</b> {ds}  |  <b>Result:</b> {icon} {res.capitalize()}  |  <b>Tier:</b> {tier}"
        )

    def _on_edit(self):
        from .edit_dialog import EditCreatorDialog

        dlg = EditCreatorDialog(self.config, self.preset_names, self)
        if dlg.exec_():
            self.config = CreatorConfig(self.folder)
            self._load_values()
            self._refresh_activity()

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
            self.worker.wait(3000)
        self._set_run_button_state(False)
        if self._state == "running":
            self._set_state("idle", "Stopped.")

    def is_running(self) -> bool:
        return bool(self.worker and self.worker.isRunning())
