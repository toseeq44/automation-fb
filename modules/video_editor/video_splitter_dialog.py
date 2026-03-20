"""
Video splitter dialog for single/bulk splitting workflows.
"""

from __future__ import annotations

import math
import os
import random
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
)

from modules.logging.logger import get_logger
from modules.video_editor.utils import get_ffmpeg_path, get_video_info, format_duration

logger = get_logger(__name__)

VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".flv", ".wmv", ".m4v"}
RANDOM_MIN_MS = 5000
RANDOM_MAX_MS = 16000


@dataclass
class VideoSplitEntry:
    source_path: str
    duration_seconds: float
    folder_detail: str


class VideoSplitWorker(QThread):
    progress_row = pyqtSignal(int, str)
    log_message = pyqtSignal(str)
    finished_summary = pyqtSignal(dict)

    def __init__(self, entries: List[Dict], delete_originals: bool, parent=None):
        super().__init__(parent)
        self.entries = entries
        self.delete_originals = delete_originals
        self.cancel_requested = False
        self.ffmpeg_path = get_ffmpeg_path()

    def cancel(self):
        self.cancel_requested = True

    def run(self):
        total = len(self.entries)
        success_count = 0
        skipped_count = 0
        failed_count = 0

        for idx, entry in enumerate(self.entries):
            if self.cancel_requested:
                self.log_message.emit("Split cancelled by user.")
                break

            row = int(entry.get("row", idx))
            source_path = entry["source_path"]
            duration = float(entry["duration_seconds"])
            parts = int(entry["parts"])
            strategy = str(entry.get("strategy", "exact")).lower()

            if parts < 2:
                skipped_count += 1
                self.progress_row.emit(row, "Skipped (parts < 2)")
                self.log_message.emit(f"Skipped: {Path(source_path).name} (parts < 2)")
                continue

            ok, message = self._split_single_video(source_path, duration, parts, strategy)
            if ok:
                success_count += 1
                self.progress_row.emit(row, "Done")
                self.log_message.emit(f"Done: {Path(source_path).name} -> {parts} part(s)")

                if self.delete_originals:
                    try:
                        os.remove(source_path)
                        self.log_message.emit(f"Deleted original: {Path(source_path).name}")
                    except Exception as exc:
                        self.log_message.emit(
                            f"Warning: could not delete original {Path(source_path).name}: {exc}"
                        )
            else:
                failed_count += 1
                self.progress_row.emit(row, "Failed")
                self.log_message.emit(f"Failed: {Path(source_path).name} ({message})")

        self.finished_summary.emit(
            {
                "total": total,
                "success": success_count,
                "skipped": skipped_count,
                "failed": failed_count,
                "cancelled": self.cancel_requested,
            }
        )

    def _split_single_video(
        self, source_path: str, duration: float, parts: int, strategy: str = "exact"
    ):
        source = Path(source_path)
        base_name = source.stem
        ext = source.suffix
        segments = self._build_segments(duration, parts, strategy)
        if not segments:
            return False, "no valid segments"

        for part_index, (start, segment_duration) in enumerate(segments):
            if segment_duration <= 0:
                continue

            output_name = f"{base_name}(part{part_index + 1}){ext}"
            output_path = self._unique_path(source.parent / output_name)

            cmd_candidates = self._build_ffmpeg_commands(source, start, segment_duration, output_path)
            split_ok = False
            for cmd in cmd_candidates:
                ok, err = self._run_ffmpeg(cmd)
                if ok:
                    split_ok = True
                    break
                self.log_message.emit(
                    f"ffmpeg attempt failed for {Path(source_path).name} part {part_index + 1}: {err[:180]}"
                )

            if not split_ok:
                try:
                    if output_path.exists():
                        output_path.unlink()
                except Exception:
                    pass
                return False, f"ffmpeg failed for part {part_index + 1}"

        return True, "ok"

    def _build_ffmpeg_commands(
        self, source: Path, start: float, segment_duration: float, output_path: Path
    ) -> List[List[str]]:
        common = [
            self.ffmpeg_path,
            "-y",
            "-i",
            str(source),
            "-ss",
            f"{start:.3f}",
            "-t",
            f"{segment_duration:.3f}",
            "-fflags",
            "+genpts",
            "-avoid_negative_ts",
            "make_zero",
            "-reset_timestamps",
            "1",
            "-map_metadata",
            "-1",
            "-map_chapters",
            "-1",
            "-sn",
        ]

        ext = output_path.suffix.lower()
        cmds: List[List[str]] = []

        # Sync-safe container-aware re-encode (primary path).
        if ext == ".webm":
            cmds.append(
                common
                + [
                    "-c:v",
                    "libvpx-vp9",
                    "-crf",
                    "32",
                    "-b:v",
                    "0",
                    "-c:a",
                    "libopus",
                    "-b:a",
                    "128k",
                    "-af",
                    "aresample=async=1:first_pts=0",
                    str(output_path),
                ]
            )
        else:
            cmds.append(
                common
                + [
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "20",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "192k",
                    "-af",
                    "aresample=async=1:first_pts=0",
                    "-movflags",
                    "+faststart",
                    str(output_path),
                ]
            )

        # Last fallback: stream copy (kept for edge-cases; may be less accurate).
        cmds.append(
            [
                self.ffmpeg_path,
                "-y",
                "-ss",
                f"{start:.3f}",
                "-i",
                str(source),
                "-t",
                f"{segment_duration:.3f}",
                "-c",
                "copy",
                "-avoid_negative_ts",
                "make_zero",
                "-reset_timestamps",
                "1",
                str(output_path),
            ]
        )

        return cmds

    def _build_segments(self, duration: float, parts: int, strategy: str) -> List[tuple]:
        total_ms = max(1, int(round(duration * 1000)))
        parts = max(1, min(parts, total_ms))

        if parts == 1:
            return [(0.0, total_ms / 1000.0)]

        if strategy == "random":
            boundaries = self._build_random_boundaries_with_limits(total_ms, parts)
        else:
            base = total_ms // parts
            remainder = total_ms % parts
            boundaries = [0]
            running = 0
            for i in range(parts):
                chunk = base + (1 if i < remainder else 0)
                running += chunk
                boundaries.append(running)
            boundaries[-1] = total_ms

        segments: List[tuple] = []
        for i in range(len(boundaries) - 1):
            start_ms = boundaries[i]
            end_ms = boundaries[i + 1]
            seg_ms = max(1, end_ms - start_ms)
            segments.append((start_ms / 1000.0, seg_ms / 1000.0))
        return segments

    def _build_random_boundaries_with_limits(self, total_ms: int, requested_parts: int) -> List[int]:
        """
        Build random boundaries while enforcing per-part duration limits.
        Auto-adjust parts when requested value is not feasible.
        """
        min_parts = max(1, math.ceil(total_ms / RANDOM_MAX_MS))
        max_parts = max(1, total_ms // RANDOM_MIN_MS)

        if max_parts < min_parts:
            # Very short clip fallback
            return [0, total_ms]

        parts = min(max(requested_parts, min_parts), max_parts)
        if parts != requested_parts:
            self.log_message.emit(
                f"Random auto-adjust: requested parts {requested_parts} -> {parts} "
                f"(to keep each part between {RANDOM_MIN_MS // 1000}s and {RANDOM_MAX_MS // 1000}s)"
            )

        if parts == 1:
            return [0, total_ms]

        # Start from minimum duration for each part.
        durations = [RANDOM_MIN_MS] * parts
        remainder = total_ms - (RANDOM_MIN_MS * parts)

        # Distribute remainder randomly without exceeding max duration.
        while remainder > 0:
            candidates = [i for i, d in enumerate(durations) if d < RANDOM_MAX_MS]
            if not candidates:
                break
            idx = random.choice(candidates)
            capacity = RANDOM_MAX_MS - durations[idx]
            add = min(remainder, capacity)
            if add <= 0:
                continue
            delta = random.randint(1, add)
            durations[idx] += delta
            remainder -= delta

        # Safety normalization if 1-2 ms drift remains.
        drift = total_ms - sum(durations)
        if drift != 0:
            for i in range(parts):
                if drift == 0:
                    break
                if drift > 0 and durations[i] < RANDOM_MAX_MS:
                    step = min(drift, RANDOM_MAX_MS - durations[i])
                    durations[i] += step
                    drift -= step
                elif drift < 0 and durations[i] > RANDOM_MIN_MS:
                    step = min(-drift, durations[i] - RANDOM_MIN_MS)
                    durations[i] -= step
                    drift += step

        # Deterministic boundary order from randomized durations.
        boundaries = [0]
        running = 0
        for d in durations:
            running += d
            boundaries.append(running)
        boundaries[-1] = total_ms
        return boundaries

    def _run_ffmpeg(self, cmd: List[str]):
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=600,
            )
            return result.returncode == 0, (result.stderr or result.stdout or "")
        except Exception as exc:
            return False, str(exc)

    @staticmethod
    def _unique_path(path: Path) -> Path:
        if not path.exists():
            return path
        stem = path.stem
        suffix = path.suffix
        parent = path.parent
        counter = 1
        while True:
            candidate = parent / f"{stem}_{counter}{suffix}"
            if not candidate.exists():
                return candidate
            counter += 1


class VideoSplitterDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.entries: List[VideoSplitEntry] = []
        self.worker: Optional[VideoSplitWorker] = None
        self._build_ui()

    def _build_ui(self):
        self.setWindowTitle("Video Splitter")
        self.setWindowFlags(Qt.Window)
        self.resize(1250, 820)
        self.setMinimumSize(1000, 700)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        self.summary_label = QLabel("No source selected.")
        self.summary_label.setMinimumHeight(24)
        main_layout.addWidget(self.summary_label)

        top_controls = QHBoxLayout()
        top_controls.setSpacing(10)
        top_controls.addWidget(QLabel("Mode:"))
        self.strategy_combo = QComboBox()
        self.strategy_combo.addItems(["Random", "Exact Length"])
        self.strategy_combo.setMinimumHeight(32)
        self.strategy_combo.setMaximumWidth(170)
        top_controls.addWidget(self.strategy_combo)

        top_controls.addWidget(QLabel("Global Split Parts:"))
        self.global_parts_combo = QComboBox()
        self.global_parts_combo.addItem("Auto", 0)
        for count in range(2, 100):
            self.global_parts_combo.addItem(str(count), count)
        self.global_parts_combo.setMinimumHeight(32)
        self.global_parts_combo.setMaximumWidth(140)
        top_controls.addWidget(self.global_parts_combo)

        apply_btn = QPushButton("Apply to Checked")
        apply_btn.setMinimumHeight(32)
        apply_btn.clicked.connect(self.apply_global_parts_to_checked)
        top_controls.addWidget(apply_btn)
        top_controls.addStretch()

        self.start_btn = QPushButton("Start Split")
        self.start_btn.setMinimumHeight(32)
        self.start_btn.clicked.connect(self.start_split)
        top_controls.addWidget(self.start_btn)

        self.cancel_btn = QPushButton("Cancel Running")
        self.cancel_btn.setMinimumHeight(32)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.cancel_split)
        top_controls.addWidget(self.cancel_btn)

        close_btn = QPushButton("Close")
        close_btn.setMinimumHeight(32)
        close_btn.clicked.connect(self.close)
        top_controls.addWidget(close_btn)

        main_layout.addLayout(top_controls)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Select", "Folder Detail", "Video Length", "Split Parts", "Status"]
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 80)
        self.table.setColumnWidth(1, 500)
        self.table.setColumnWidth(2, 150)
        self.table.setColumnWidth(3, 150)
        self.table.setColumnWidth(4, 220)
        self.table.setAlternatingRowColors(False)
        self.table.setWordWrap(False)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.setHorizontalScrollMode(QTableWidget.ScrollPerPixel)
        self.table.setVerticalScrollMode(QTableWidget.ScrollPerPixel)
        self.table.verticalHeader().setDefaultSectionSize(34)
        main_layout.addWidget(self.table, 1)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMinimumHeight(170)
        main_layout.addWidget(self.log_output)

        self.setStyleSheet(
            """
            QDialog {
                background-color: #1a1a1a;
                color: #e0e0e0;
                font-family: 'Segoe UI', 'Arial', sans-serif;
                font-size: 13px;
            }
            QLabel {
                color: #e0e0e0;
            }
            QPushButton {
                background-color: #2a2a2a;
                color: #e0e0e0;
                border: none;
                border-radius: 8px;
                padding: 8px 14px;
            }
            QPushButton:hover {
                background-color: #353535;
            }
            QComboBox {
                background-color: #202020;
                color: #e0e0e0;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                padding: 6px 10px;
                min-width: 100px;
            }
            QComboBox QAbstractItemView {
                background-color: #1f1f1f;
                color: #e0e0e0;
                border: 1px solid #3a3a3a;
                selection-background-color: #00bcd4;
                selection-color: #101010;
            }
            QSpinBox {
                background-color: #202020;
                color: #e0e0e0;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                padding: 4px 6px;
            }
            QTableWidget {
                background-color: #1f1f1f;
                border: 1px solid #3a3a3a;
                gridline-color: #2a2a2a;
            }
            QTableWidget::item {
                padding: 4px;
            }
            QHeaderView::section {
                background-color: #2a2a2a;
                color: #e0e0e0;
                border: none;
                padding: 8px;
                font-weight: bold;
            }
            QAbstractSpinBox {
                background-color: #202020;
                color: #e0e0e0;
                border: 1px solid #3a3a3a;
                border-radius: 4px;
                padding: 2px 4px;
            }
            QTextEdit {
                background-color: #151515;
                border: 1px solid #3a3a3a;
                color: #e0e0e0;
            }
            """
        )

    def load_single_video(self, video_path: str):
        self.entries = []
        info = get_video_info(video_path)
        duration = float(info.get("duration", 0.0) or 0.0)

        folder_detail = f"Single file | {Path(video_path).parent}"
        self.entries.append(
            VideoSplitEntry(
                source_path=video_path,
                duration_seconds=duration,
                folder_detail=folder_detail,
            )
        )
        self._populate_table()

    def load_bulk_folder(self, folder_path: str):
        self.entries = []
        source_root = Path(folder_path)
        folder_counts: Dict[str, int] = {}
        candidate_files: List[Path] = []

        for root, _, files in os.walk(source_root):
            root_path = Path(root)
            for name in files:
                path = root_path / name
                if path.suffix.lower() in VIDEO_EXTENSIONS:
                    candidate_files.append(path)
                    rel_folder = str(root_path.relative_to(source_root))
                    folder_counts[rel_folder] = folder_counts.get(rel_folder, 0) + 1

        for path in sorted(candidate_files):
            info = get_video_info(str(path))
            duration = float(info.get("duration", 0.0) or 0.0)
            rel_folder = str(path.parent.relative_to(source_root))
            folder_count = folder_counts.get(rel_folder, 0)
            folder_detail = (
                f"Folder: {rel_folder} ({folder_count} video(s)) | Root: {source_root}"
            )
            self.entries.append(
                VideoSplitEntry(
                    source_path=str(path),
                    duration_seconds=duration,
                    folder_detail=folder_detail,
                )
            )

        self._populate_table()

    def _populate_table(self):
        self.table.setRowCount(0)

        total_videos = len(self.entries)
        unique_folders = len({str(Path(e.source_path).parent) for e in self.entries})
        self.summary_label.setText(
            f"Total videos: {total_videos} | Total subfolders: {max(0, unique_folders - 1)}"
        )

        for row, entry in enumerate(self.entries):
            self.table.insertRow(row)

            select_item = QTableWidgetItem()
            select_item.setFlags(
                Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable
            )
            select_item.setCheckState(Qt.Checked)
            self.table.setItem(row, 0, select_item)

            detail_text = f"{entry.folder_detail}\nVideo: {Path(entry.source_path).name}"
            self.table.setItem(row, 1, QTableWidgetItem(detail_text))
            self.table.setItem(row, 2, QTableWidgetItem(format_duration(entry.duration_seconds)))

            row_parts_combo = QComboBox()
            row_parts_combo.addItem("Auto", 0)
            for count in range(2, 100):
                row_parts_combo.addItem(str(count), count)
            row_parts_combo.setMinimumHeight(26)
            self.table.setCellWidget(row, 3, row_parts_combo)

            self.table.setItem(row, 4, QTableWidgetItem("Ready"))

        self.log_output.clear()
        self.log_output.append("Scan completed. Configure selections and split parts.")

    def apply_global_parts_to_checked(self):
        value = int(self.global_parts_combo.currentData() or 0)
        for row in range(self.table.rowCount()):
            select_item = self.table.item(row, 0)
            if not select_item or select_item.checkState() != Qt.Checked:
                continue
            combo = self.table.cellWidget(row, 3)
            if isinstance(combo, QComboBox):
                index = combo.findData(value)
                if index >= 0:
                    combo.setCurrentIndex(index)

    def start_split(self):
        if self.worker and self.worker.isRunning():
            QMessageBox.warning(self, "Busy", "Splitting is already running.")
            return
        if not self.entries:
            QMessageBox.warning(self, "No Data", "Please select video(s) first.")
            return

        delete_reply = QMessageBox.question(
            self,
            "Delete Originals?",
            "After splitting, delete original videos?",
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
            QMessageBox.No,
        )
        if delete_reply == QMessageBox.Cancel:
            return
        delete_originals = delete_reply == QMessageBox.Yes

        jobs = []
        for row, entry in enumerate(self.entries):
            select_item = self.table.item(row, 0)
            if not select_item or select_item.checkState() != Qt.Checked:
                self._update_row_status(row, "Skipped (unchecked)")
                continue

            combo = self.table.cellWidget(row, 3)
            manual_parts = int(combo.currentData() or 0) if isinstance(combo, QComboBox) else 0
            parts = manual_parts if manual_parts > 0 else self._default_parts(entry.duration_seconds)

            jobs.append(
                {
                    "row": row,
                    "source_path": entry.source_path,
                    "duration_seconds": entry.duration_seconds,
                    "parts": parts,
                    "strategy": "random"
                    if self.strategy_combo.currentText() == "Random"
                    else "exact",
                }
            )
            self._update_row_status(row, f"Queued ({parts} part(s))")

        if not jobs:
            QMessageBox.information(self, "Nothing to Process", "No checked rows found.")
            return

        self.log_output.append(
            f"Starting split: {len(jobs)} video(s), delete originals = {delete_originals}"
        )

        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)

        self.worker = VideoSplitWorker(jobs, delete_originals, self)
        self.worker.progress_row.connect(self._on_worker_row_update)
        self.worker.log_message.connect(self._on_worker_log)
        self.worker.finished_summary.connect(self._on_worker_finished)
        self.worker.start()

    def cancel_split(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.log_output.append("Cancel requested...")

    def _on_worker_row_update(self, row: int, status: str):
        self._update_row_status(row, status)

    def _on_worker_log(self, message: str):
        self.log_output.append(message)

    def _on_worker_finished(self, summary: dict):
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)

        msg = (
            f"Done.\n\nTotal: {summary.get('total', 0)}\n"
            f"Success: {summary.get('success', 0)}\n"
            f"Skipped: {summary.get('skipped', 0)}\n"
            f"Failed: {summary.get('failed', 0)}"
        )
        if summary.get("cancelled"):
            msg += "\nStatus: Cancelled by user"
        QMessageBox.information(self, "Video Splitter", msg)

    def _update_row_status(self, row: int, status: str):
        item = self.table.item(row, 4)
        if item is None:
            item = QTableWidgetItem(status)
            self.table.setItem(row, 4, item)
        else:
            item.setText(status)

    @staticmethod
    def _default_parts(duration: float) -> int:
        if duration > 30:
            min_parts = math.floor(duration / 16.0) + 1
            max_parts = math.ceil(duration / 8.0) - 1
            if min_parts <= max_parts:
                return max(2, min_parts)
            # Fallback around midpoint of the target window
            return max(2, int(round(duration / 12.0)))
        if 10 < duration < 30:
            return 2
        return 1
