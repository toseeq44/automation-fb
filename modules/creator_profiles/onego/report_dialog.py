"""
OneGo report dialog — shows final per-session report with profile/page details.
"""

from typing import Dict, Any, List

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

_BG = "#0d1117"
_BG_CARD = "#161b22"
_CYAN = "#00d4ff"
_GREEN = "#43B581"
_RED = "#E74C3C"
_WARN = "#F39C12"


def _status_color(status: str) -> str:
    return {
        "success": _GREEN,
        "partial": _WARN,
        "skipped": "rgba(255,255,255,0.5)",
        "failed": _RED,
    }.get(status, "white")


class OneGoReportDialog(QDialog):
    """Dialog showing OneGo run results."""

    def __init__(self, report: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.setWindowTitle("OneGo Report")
        self.setMinimumSize(700, 500)
        self.setStyleSheet(f"""
            QDialog {{ background:{_BG}; color:white; }}
            QLabel {{ color:white; background:transparent; border:none; }}
        """)
        self._report = report
        self._build()

    def _build(self):
        vbox = QVBoxLayout(self)
        vbox.setSpacing(10)

        # Title
        title = QLabel("OneGo Run Report")
        title.setStyleSheet(f"color:{_CYAN}; font-size:18px; font-weight:bold;")
        title.setAlignment(Qt.AlignCenter)
        vbox.addWidget(title)

        # Summary row
        summary = self._build_summary()
        vbox.addWidget(summary)

        # Profile details table
        profiles = self._report.get("profiles", [])
        if profiles:
            for prof in profiles:
                vbox.addWidget(self._build_profile_section(prof))

        # Close button
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(
            f"QPushButton {{ color:{_CYAN}; background:#161b22; border:1px solid {_CYAN};"
            " border-radius:5px; padding:8px 24px; font-weight:bold; font-size:13px; }}"
            f"QPushButton:hover {{ background:#1c2128; }}"
        )
        close_btn.setFixedHeight(36)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        btn_row.addStretch()
        vbox.addLayout(btn_row)

    def _build_summary(self) -> QLabel:
        r = self._report
        mode = r.get("mode", "?")
        profiles = r.get("profiles_processed", 0)
        pages = r.get("total_pages", 0)
        uploaded = r.get("total_uploaded", 0)
        skipped = r.get("total_skipped", 0)
        partial = r.get("total_partial", 0)
        failed = r.get("total_failed", 0)
        completed = r.get("completed_at", "")

        text = (
            f"<div style='padding:8px; background:{_BG_CARD}; border-radius:6px;'>"
            f"<b>Mode:</b> {mode} &nbsp; | &nbsp; "
            f"<b>Profiles:</b> {profiles} &nbsp; | &nbsp; "
            f"<b>Pages:</b> {pages}<br>"
            f"<span style='color:{_GREEN};'>Uploaded: {uploaded}</span> &nbsp; | &nbsp; "
            f"<span style='color:rgba(255,255,255,0.5);'>Skipped: {skipped}</span> &nbsp; | &nbsp; "
            f"<span style='color:{_WARN};'>Partial: {partial}</span> &nbsp; | &nbsp; "
            f"<span style='color:{_RED};'>Failed: {failed}</span>"
        )
        if completed:
            text += f"<br><span style='color:rgba(255,255,255,0.4); font-size:11px;'>Completed: {completed}</span>"
        text += "</div>"

        lbl = QLabel(text)
        lbl.setTextFormat(Qt.RichText)
        lbl.setWordWrap(True)
        lbl.setStyleSheet("font-size:12px;")
        return lbl

    def _build_profile_section(self, prof: dict) -> QLabel:
        name = prof.get("profile_name", "?")
        pages: List[dict] = prof.get("pages", [])
        total_uploaded = prof.get("total_uploaded", 0)

        rows_html = ""
        for pg in pages:
            pg_name = pg.get("page_name", "?")
            target = pg.get("target", 0)
            available = pg.get("available", 0)
            uploaded = pg.get("uploaded", 0)
            status = pg.get("status", "?")
            reason = pg.get("reason", "")
            color = _status_color(status)

            rows_html += (
                f"<tr>"
                f"<td style='padding:3px 6px;'>{pg_name}</td>"
                f"<td style='padding:3px 6px; text-align:center;'>{target}</td>"
                f"<td style='padding:3px 6px; text-align:center;'>{available}</td>"
                f"<td style='padding:3px 6px; text-align:center;'>{uploaded}</td>"
                f"<td style='padding:3px 6px; color:{color}; text-align:center;'>{status}</td>"
                f"<td style='padding:3px 6px; color:rgba(255,255,255,0.5); font-size:11px;'>{reason}</td>"
                f"</tr>"
            )

        html = (
            f"<div style='padding:8px; margin-top:6px; background:{_BG_CARD}; border-radius:6px;'>"
            f"<b style='color:{_CYAN};'>{name}</b>"
            f" &nbsp; <span style='color:rgba(255,255,255,0.5);'>({len(pages)} page(s), "
            f"{total_uploaded} uploaded)</span>"
            f"<table style='width:100%; margin-top:4px; color:white; font-size:11px;'>"
            f"<tr style='color:rgba(255,255,255,0.6);'>"
            f"<th style='text-align:left; padding:2px 6px;'>Page</th>"
            f"<th style='padding:2px 6px;'>Target</th>"
            f"<th style='padding:2px 6px;'>Available</th>"
            f"<th style='padding:2px 6px;'>Uploaded</th>"
            f"<th style='padding:2px 6px;'>Status</th>"
            f"<th style='text-align:left; padding:2px 6px;'>Reason</th>"
            f"</tr>"
            f"{rows_html}"
            f"</table></div>"
        )

        lbl = QLabel(html)
        lbl.setTextFormat(Qt.RichText)
        lbl.setWordWrap(True)
        return lbl
