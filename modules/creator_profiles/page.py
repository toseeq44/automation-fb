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
    QScrollArea, QSizePolicy,
    QSpinBox,
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
_MIN_CARD  = 260     # minimum card width for column calculation
_MAX_COLS  = 4


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

    def __init__(self, root: Path, preset_names: List[str], parent=None):
        super().__init__(parent)
        self.root = root
        self.preset_names = preset_names
        self.created_folder: Path = None
        self.setWindowTitle("Add Creator")
        self.setMinimumWidth(620)
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

        self._on_mode_change()
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
        self.name_edit.setText(_suggest_folder_name_from_url(url))

    def _on_mode_change(self):
        idx = self.mode_combo.currentIndex()
        self.preset_combo.setVisible(idx == 1)
        self.split_spin.setVisible(idx == 2)

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
            background:#0ea5e9;
            color:#ffffff;
        }
        QTableWidget QLineEdit {
            background:#0a0f18;
            color:#ffffff;
            border:1px solid #00d4ff;
            border-radius:4px;
            padding:4px 6px;
            selection-background-color:#0ea5e9;
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
            spacing:8px;
        }
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
        self.table.setColumnWidth(1, 200)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(34)
        self.table.setEditTriggers(
            QTableWidget.DoubleClicked
            | QTableWidget.SelectedClicked
            | QTableWidget.EditKeyPressed
            | QTableWidget.AnyKeyPressed
        )
        self.table.setWordWrap(False)
        self.table.setTextElideMode(Qt.ElideMiddle)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        v.addWidget(self.table, 1)

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
        v.addLayout(settings_form)
        self._on_mode_change()

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
        self._col_timer.setInterval(50)
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
        for i, (fp, card) in enumerate(self.cards.items()):
            r, c = divmod(i, self._cols)
            self.cards_grid.addWidget(card, r, c)

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
                "keep_original_after_edit": cfg.keep_original_after_edit,
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
                            "keep_original_after_edit"):
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
