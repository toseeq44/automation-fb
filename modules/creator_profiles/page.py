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
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from PyQt5.QtCore import Qt, QFileSystemWatcher, QTimer
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtWidgets import (
    QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QFrame,
    QGraphicsDropShadowEffect, QGridLayout,
    QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMenu, QMessageBox, QPushButton,
    QScrollArea, QSizePolicy,
    QTableWidget, QTableWidgetItem, QTextEdit,
    QVBoxLayout, QWidget,
)

from .creator_card import CreatorCard
from .config_manager import CreatorConfig

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
_MIN_CARD  = 390     # minimum card width for column calculation
_MAX_COLS  = 3


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


# ── Single Add Dialog ────────────────────────────────────────────────────────

class AddCreatorDialog(QDialog):

    _SS = """
        QDialog  { background:#0d1117; color:white; }
        QLabel   { color:rgba(255,255,255,0.82); background:transparent; border:none; }
        QLineEdit {
            background:#161b22; color:white;
            border:1px solid rgba(0,212,255,0.28);
            border-radius:4px; padding:7px;
        }
        QLineEdit:focus { border-color:#00d4ff; }
        QPushButton {
            background:#161b22; color:white;
            border:1px solid rgba(0,212,255,0.3);
            border-radius:5px; padding:7px 18px; font-weight:bold;
        }
        QPushButton:hover { background:#1c2128; border-color:#00d4ff; }
    """

    def __init__(self, root: Path, parent=None):
        super().__init__(parent)
        self.root = root
        self.created_folder: Path = None
        self.setWindowTitle("Add Creator")
        self.setMinimumWidth(520)
        self.setStyleSheet(self._SS)
        self._build()

    def _build(self):
        v = QVBoxLayout(self)
        v.setContentsMargins(24, 22, 24, 20)
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
        v.addLayout(form)

        note = QLabel(
            "Folder created at:  Desktop / Links Grabber / <name>\n"
            "Then click ✏ Edit on the card to configure settings."
        )
        note.setStyleSheet("color:rgba(255,255,255,0.35); font-size:11px;"
                           " background:transparent; border:none;")
        v.addWidget(note)

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
        v.addWidget(btns)

    def _suggest(self, url: str):
        import re
        for pat in [r"@([\w.]+)", r"/([^/?#]+)/?$"]:
            m = re.search(pat, url.rstrip("/"))
            if m:
                self.name_edit.setText(m.group(1))
                return

    def _create(self):
        url  = self.url_edit.text().strip()
        name = self.name_edit.text().strip()
        if not url:
            QMessageBox.warning(self, "Required", "Please enter the Creator URL.")
            return
        if not name:
            QMessageBox.warning(self, "Required", "Please enter a Folder Name.")
            return
        folder = self.root / name
        try:
            folder.mkdir(parents=True, exist_ok=True)
            cfg = CreatorConfig(folder)
            cfg.data["creator_url"] = url
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
        QHeaderView::section {
            background:#0a0e1a; color:#00d4ff;
            border:1px solid rgba(0,212,255,0.2);
            padding:5px; font-weight:bold;
        }
        QTableWidget::item { padding:4px; border: none; }
        QTableWidget::item:selected { background:rgba(0,212,255,0.15); }
        QPushButton {
            background:#161b22; color:white;
            border:1px solid rgba(0,212,255,0.3);
            border-radius:5px; padding:7px 18px; font-weight:bold;
        }
        QPushButton:hover { background:#1c2128; border-color:#00d4ff; }
    """

    def __init__(self, root: Path, parent=None):
        super().__init__(parent)
        self.root = root
        self.created_count = 0
        self.setWindowTitle("Bulk Add Creators")
        self.setMinimumSize(680, 540)
        self.setStyleSheet(self._SS)
        self._build()

    def _build(self):
        v = QVBoxLayout(self)
        v.setContentsMargins(22, 20, 22, 18)
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
        self.url_box.setMaximumHeight(110)
        v.addWidget(self.url_box)

        parse_btn = QPushButton("Parse URLs  →")
        parse_btn.setStyleSheet(
            f"background:#0a1628; color:{_CYAN};"
            f" border:1px solid rgba(0,212,255,0.4); border-radius:5px;"
            " padding:6px 16px; font-weight:bold;"
        )
        parse_btn.clicked.connect(self._parse)
        v.addWidget(parse_btn, alignment=Qt.AlignLeft)

        preview_lbl = QLabel("Preview  (edit Folder Name if needed):")
        preview_lbl.setStyleSheet(
            "color:rgba(255,255,255,0.6); font-size:12px; font-weight:bold;"
            " background:transparent; border:none;"
        )
        v.addWidget(preview_lbl)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Creator URL", "Folder Name"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.DoubleClicked | QTableWidget.SelectedClicked)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        v.addWidget(self.table, 1)

        # Buttons
        btn_row = QHBoxLayout()
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
        v.addLayout(btn_row)

    def _parse(self):
        import re
        text = self.url_box.toPlainText()
        urls = [l.strip() for l in text.splitlines() if l.strip().startswith("http")]
        self.table.setRowCount(0)
        for url in urls:
            row = self.table.rowCount()
            self.table.insertRow(row)
            url_item = QTableWidgetItem(url)
            url_item.setFlags(url_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 0, url_item)

            # Suggest folder name
            name = ""
            for pat in [r"@([\w.]+)", r"/([^/?#]+)/?$"]:
                m = re.search(pat, url.rstrip("/"))
                if m:
                    name = m.group(1)
                    break
            self.table.setItem(row, 1, QTableWidgetItem(name or "creator"))

    def _create_all(self):
        count = 0
        for row in range(self.table.rowCount()):
            url  = self.table.item(row, 0).text().strip()
            name = (self.table.item(row, 1).text() or "").strip()
            if not url or not name:
                continue
            folder = self.root / name
            try:
                folder.mkdir(parents=True, exist_ok=True)
                cfg = CreatorConfig(folder)
                cfg.data["creator_url"] = url
                cfg.save()
                count += 1
            except Exception:
                pass
        self.created_count = count
        if count:
            self.accept()
        else:
            QMessageBox.warning(self, "Nothing Created",
                                "Parse URLs first, then click Create All.")


# ─────────────────────────── main page ──────────────────────────────────────

class CreatorProfilesPage(QWidget):
    """Downloading + Editing main page — self-contained layout, top action bar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.root         = _links_root()
        self.presets      = _preset_names()
        self.cards: Dict[Path, CreatorCard] = {}
        self.daily_guard_enabled = False
        self.daily_guard_interval_minutes = 30
        self._cols        = 2
        self._col_timer   = QTimer(self)
        self._col_timer.setSingleShot(True)
        self._col_timer.setInterval(100)
        self._col_timer.timeout.connect(self._update_cols)
        self._daily_guard_timer = QTimer(self)
        self._daily_guard_timer.timeout.connect(self._daily_guard_cycle)

        self.setStyleSheet(f"QWidget {{ background:{_BG}; color:white; }}")
        self._build_ui()
        self._setup_watcher()
        self._refresh_cards()

    # ── UI ────────────────────────────────────────────────────────────────

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 14, 18, 12)
        outer.setSpacing(10)

        # ── Header ────────────────────────────────────────────────────────
        hdr = QFrame()
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

        # ── Action bar (TOP) ──────────────────────────────────────────────
        action_panel = QFrame()
        action_panel.setStyleSheet(f"""
            QFrame {{
                background:{_BG_PANEL};
                border:1px solid rgba(0,212,255,0.12);
                border-radius:8px;
            }}
        """)
        al = QHBoxLayout(action_panel)
        al.setContentsMargins(12, 8, 12, 8)
        al.setSpacing(7)

        # ── Add Creator (dropdown menu) ───────────────────────────────────
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
        al.addWidget(self.add_btn)

        # Import / Export
        imp_btn = _abtn("⬆  Import", _CYAN, "#161b22")
        imp_btn.setToolTip("Import creator settings from JSON file")
        imp_btn.clicked.connect(self._on_import)
        al.addWidget(imp_btn)

        exp_btn = _abtn("⬇  Export", _CYAN, "#161b22")
        exp_btn.setToolTip("Export all creator settings to JSON file")
        exp_btn.clicked.connect(self._on_export)
        al.addWidget(exp_btn)

        al.addWidget(_vsep())

        # Run controls
        run_all = _abtn("▶  Run All",       _GREEN, "#161b22")
        stop_b  = _abtn("⏹  Stop",          _RED,   "#161b22")
        self.guard_b = _abtn("🛡  Start Daily Guard", _GREEN, "#161b22")
        ref_b   = _abtn("↺  Reset App",     "rgba(255,255,255,0.7)", _BG_CARD,
                         "rgba(255,255,255,0.12)")
        clr_b   = _abtn("🗑  Clear History", _CYAN,  "#161b22")
        sav_b   = _abtn("💾  Save All",      "rgba(255,255,255,0.7)", _BG_CARD,
                         "rgba(255,255,255,0.12)")

        run_all.clicked.connect(self._on_run_all)
        stop_b.clicked.connect(self._on_stop_all)
        self.guard_b.clicked.connect(self._on_toggle_daily_guard)
        ref_b.clicked.connect(self._on_reset_app)
        clr_b.clicked.connect(self._on_clear_history)
        sav_b.clicked.connect(self._on_save_all)

        for b in (run_all, stop_b, self.guard_b, ref_b, clr_b, sav_b):
            al.addWidget(b)

        al.addStretch()
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
        self.cards_grid = QGridLayout(self.cards_w)
        self.cards_grid.setSpacing(12)
        self.cards_grid.setContentsMargins(0, 0, 0, 0)

        sv.addWidget(self.cards_w)
        sv.addStretch()

        self.scroll.setWidget(self.scroll_content)
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
        # Remove all widgets from layout (don't delete them)
        while self.cards_grid.count():
            self.cards_grid.takeAt(0)
        # Re-insert
        for i, (fp, card) in enumerate(self.cards.items()):
            r, c = divmod(i, self._cols)
            self.cards_grid.addWidget(card, r, c)

    def _toggle_empty(self, empty: bool):
        self.empty.setVisible(empty)
        self.scroll.setVisible(not empty)

    def _on_remove_card(self, folder: Path):
        if folder in self.cards:
            card = self.cards.pop(folder)
            card.stop_worker()
            card.deleteLater()
        self._rebuild_grid()
        self._toggle_empty(len(self.cards) == 0)

    # ── responsive columns ────────────────────────────────────────────────

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._col_timer.start()

    def _update_cols(self):
        vp_w = self.scroll.viewport().width() if self.scroll.isVisible() else self.width()
        new_cols = max(1, min(_MAX_COLS, vp_w // _MIN_CARD))
        if new_cols != self._cols:
            self._cols = new_cols
            self._rebuild_grid()

    # ── action bar slots ──────────────────────────────────────────────────

    def _on_add_single(self):
        self.root.mkdir(parents=True, exist_ok=True)
        dlg = AddCreatorDialog(self.root, self)
        if dlg.exec_() and dlg.created_folder:
            self._refresh_cards()

    def _on_add_bulk(self):
        self.root.mkdir(parents=True, exist_ok=True)
        dlg = BulkAddDialog(self.root, self)
        if dlg.exec_() and dlg.created_count:
            self._refresh_cards()
            QMessageBox.information(
                self, "Done",
                f"{dlg.created_count} creator(s) added successfully."
            )

    def _on_run_all(self):
        for card in self.cards.values():
            card.trigger_run()

    def _on_stop_all(self):
        for card in self.cards.values():
            card.stop_worker()

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
                            "popular_fallback", "prefer_popular_first", "randomize_links"):
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
