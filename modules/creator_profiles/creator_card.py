"""
modules/creator_profiles/creator_card.py
Creator card widget for Downloading+Editing page.
"""

from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
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
from .download_engine import CreatorDownloadWorker, has_links_in_creator_folder

_BG_CARD = "#161b22"
_BG_HOVER = "#1c2128"
_BG_INPUT = "#0a0e1a"
_CYAN = "#00d4ff"
_GREEN = "#43B581"
_RED = "#E74C3C"
_WARN = "#F39C12"
_BORDER = "rgba(0,212,255,0.2)"
_BORDER_HI = "rgba(0,212,255,0.5)"


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
        f"color:rgba(255,255,255,{alpha}); font-size:{size}px;"
        " background:transparent; border:none;"
    )
    return l


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
        border = _BORDER_HI if hovered else _BORDER
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
        v.setContentsMargins(16, 13, 16, 13)
        v.setSpacing(9)

        hrow = QHBoxLayout()
        ico = QLabel("📁")
        ico.setFont(QFont("Segoe UI", 13))
        ico.setStyleSheet("background:transparent; border:none;")
        hrow.addWidget(ico)

        self.title_lbl = QLabel("")
        self.title_lbl.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.title_lbl.setStyleSheet(f"color:{_CYAN}; background:transparent; border:none;")
        self.title_lbl.setWordWrap(True)
        hrow.addWidget(self.title_lbl, 1)

        self.dot = QLabel("●")
        self.dot.setStyleSheet(f"color:{self._DOT['idle']}; font-size:13px; background:transparent; border:none;")
        hrow.addWidget(self.dot)
        v.addLayout(hrow)

        self.path_lbl = QLabel(str(self.folder))
        self.path_lbl.setStyleSheet(
            "color:rgba(255,255,255,0.22); font-size:10px; background:transparent; border:none;"
        )
        self.path_lbl.setWordWrap(True)
        v.addWidget(self.path_lbl)

        self.flags_lbl = QLabel("")
        self.flags_lbl.setStyleSheet(
            "color:rgba(255,255,255,0.52); font-size:10px; background:transparent; border:none;"
        )
        v.addWidget(self.flags_lbl)
        v.addWidget(_div())

        g = QGridLayout()
        g.setSpacing(7)
        g.setColumnStretch(1, 1)

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

        self.mode_cb = QComboBox()
        self.mode_cb.addItems(["None", "Preset", "Split"])
        self.mode_cb.setFixedWidth(84)
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

        toggles = QHBoxLayout()
        toggles.setSpacing(6)
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
        toggles.addStretch()

        tw = QWidget()
        tw.setStyleSheet("background:transparent; border:none;")
        tw.setLayout(toggles)
        g.addWidget(_lbl("Flags:"), 2, 0)
        g.addWidget(tw, 2, 1)

        v.addLayout(g)
        v.addWidget(_div())

        act_hdr = QLabel("Last Activity")
        act_hdr.setStyleSheet(
            "color:rgba(255,255,255,0.5); font-size:11px; font-weight:bold; background:transparent; border:none;"
        )
        v.addWidget(act_hdr)

        act_row = QHBoxLayout()
        act_row.setSpacing(14)
        self.act_date = _lbl("Date: -", 11, 0.38)
        self.act_result = _lbl("Result: -", 11, 0.38)
        self.act_tier = _lbl("Tier: -", 11, 0.38)
        for l in (self.act_date, self.act_result, self.act_tier):
            act_row.addWidget(l)
        act_row.addStretch()
        v.addLayout(act_row)
        v.addWidget(_div())

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
            "color:rgba(255,255,255,0.32); font-size:11px; background:transparent; border:none;"
        )
        self.status_lbl.setWordWrap(True)
        self.status_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        ar.addWidget(self.status_lbl, 1)
        v.addLayout(ar)

    def _refresh_header(self):
        creator_url = (self.config.creator_url or "").strip()
        self.title_lbl.setText(creator_url if creator_url else f"{self.folder.name} (URL missing)")
        flags = []
        flags.append(f"✂ {self.split_sp.value():.1f}s")
        flags.append(f"👤 Max: {self.n_spin.value()}")
        flags.append("Skip" if self.dup_btn.isChecked() else "Dup")
        if self.pop_btn.isChecked():
            flags.append("Pop")
        if self.rand_btn.isChecked():
            flags.append("Rand")
        self.flags_lbl.setText(" | ".join(flags))

    def _load_values(self):
        c = self.config
        c.ensure_creator_url()
        self.n_spin.setValue(c.n_videos)
        self.split_sp.setValue(c.split_duration)
        self.mode_cb.setCurrentIndex({"none": 0, "preset": 1, "split": 2}.get(c.editing_mode, 0))
        if c.preset_name and c.preset_name in self.preset_names:
            self.preset_cb.setCurrentText(c.preset_name)

        self.dup_btn.setChecked(c.duplication_control)
        self.pop_btn.setChecked(c.popular_fallback)
        self.rand_btn.setChecked(c.randomize_links)
        self._refresh_toggle_styles()
        self._update_edit_vis()
        self._refresh_header()

    def _refresh_toggle_styles(self):
        for btn, on_color, off_bg in (
            (self.dup_btn, "#1a5c1a", "#222"),
            (self.pop_btn, "#6a4a0a", "#222"),
            (self.rand_btn, "#0a3f4b", "#222"),
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

        # Strict behavior requested:
        # 1) If links file exists in creator folder -> use local links mode only.
        # 2) If links file missing -> show simple error.
        use_local_links = has_links_in_creator_folder(self.folder)
        if use_local_links:
            url = ""
        else:
            url = (self.config.creator_url or "").strip()
            if not url:
                inferred = self.config.ensure_creator_url()
                if inferred:
                    self.config = CreatorConfig(self.folder)
                    self._refresh_header()
                    url = inferred
            if not url:
                self._set_state("error", "No links file found in this folder.")
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
            return
        try:
            dt = datetime.fromisoformat(a["date"])
            ds = dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            ds = str(a.get("date", "-"))
        res = a.get("result", "-") or "-"
        icon = {"success": "✓", "failed": "✗", "partial": "!"}.get(res, "")
        self.act_date.setText(f"Date: {ds}")
        self.act_result.setText(f"Result: {icon} {res.capitalize()}")
        self.act_tier.setText(f"Tier: {a.get('tier_used') or '-'}")

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
            f"Remove '{self.folder.name}' from list?\nFolder will not be deleted.",
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
