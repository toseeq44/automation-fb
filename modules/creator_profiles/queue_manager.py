"""
modules/creator_profiles/queue_manager.py
Sequential queue manager for processing creator profiles one at a time.

Features:
- Run All: always starts fresh from index 0 (card display order)
- One creator at a time (no parallel processing)
- Pause: stops after current download finishes, saves state
- Resume: continues from exactly where stopped
- State persisted to Desktop/Links Grabber/.queue_state.json (atomic write)
- Crash recovery: on app start, loads saved state and offers resume
"""

import json
import random
import socket
import time
import uuid
import threading
from pathlib import Path
from typing import List, Optional

from PyQt5.QtCore import QThread, pyqtSignal

from .download_engine import CreatorDownloadWorker
from modules.shared.pacing import get_delay_multiplier, resolve_user_plan


def _is_network_available() -> bool:
    """Quick check if internet is reachable (DNS lookup to Google)."""
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=3)
        return True
    except OSError:
        return False


def _state_file() -> Path:
    return Path.home() / "Desktop" / "Links Grabber" / ".queue_state.json"


class CreatorQueueManager(QThread):
    """
    Manages sequential downloading for multiple creator folders.

    Signals:
        queue_progress(str)          — status message for the queue status label
        creator_started(str)         — folder name of the creator being processed
        creator_finished(str, bool)  — folder name + success flag
        queue_finished()             — all creators done (or stopped)
        paused()                     — queue is now paused and waiting
    """

    queue_progress       = pyqtSignal(str)
    creator_started      = pyqtSignal(str)
    creator_finished     = pyqtSignal(str, bool)
    creator_progress_pct = pyqtSignal(str, int)   # folder_name, percent (0-100)
    queue_finished       = pyqtSignal()
    paused               = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self._queue: List[Path] = []
        self._current_index: int = 0
        self._session_id: str = ""

        self._pause_flag = False
        self._stop_flag = False
        self._resume_event = threading.Event()
        self._resume_event.set()   # not paused initially

        self._current_worker: Optional[CreatorDownloadWorker] = None
        self._worker_done_event = threading.Event()
        self._total_videos_downloaded: int = 0

    # ── Public API ────────────────────────────────────────────────────────

    def start_queue(self, folders: List[Path]):
        """Run All — always starts fresh from index 0."""
        self._queue = list(folders)
        self._current_index = 0
        self._session_id = str(uuid.uuid4())
        self._pause_flag = False
        self._stop_flag = False
        self._total_videos_downloaded = 0
        self._resume_event.set()
        self._delete_state()
        if not self.isRunning():
            self.start()

    def pause(self):
        """Pause after current video download finishes."""
        if not self.isRunning():
            return
        self._pause_flag = True
        self._resume_event.clear()
        # Also pause the active worker (between videos)
        if self._current_worker:
            self._current_worker.pause()
        self.queue_progress.emit("Queue: Pausing after current video...")

    def resume(self):
        """Resume from exactly where paused."""
        self._pause_flag = False
        self._resume_event.set()
        # Resume active worker if it's waiting
        if self._current_worker:
            self._current_worker.resume()
        if not self.isRunning():
            # Thread exited while paused — restart from saved index
            self.start()

    def stop(self):
        """Hard stop — cancel current download and exit queue."""
        self._stop_flag = True
        self._pause_flag = False
        self._resume_event.set()
        if self._current_worker:
            self._current_worker.stop()
        self._delete_state()

    def reset(self):
        """Hard reset — stop everything, clear state."""
        self.stop()
        self._queue = []
        self._current_index = 0

    # ── State persistence ─────────────────────────────────────────────────

    def load_saved_state(self) -> Optional[dict]:
        """Load crash-recovery state. Returns dict or None."""
        sf = _state_file()
        try:
            if sf.exists():
                with open(sf, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("queue") and data.get("status") in ("running", "paused"):
                    return data
        except Exception:
            pass
        return None

    def restore_from_state(self, state: dict):
        """Restore queue from saved state (for crash recovery). Does NOT start running."""
        self._queue = [Path(p) for p in state.get("queue", [])]
        self._current_index = int(state.get("current_index", 0))
        self._session_id = state.get("session_id", str(uuid.uuid4()))
        self._pause_flag = True
        self._resume_event.clear()

    def _save_state(self):
        """Atomically write queue state to .queue_state.json."""
        sf = _state_file()
        try:
            sf.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "status": "paused" if self._pause_flag else "running",
                "queue": [str(p) for p in self._queue],
                "current_index": self._current_index,
                "paused_at": str(self._queue[self._current_index]) if self._current_index < len(self._queue) else "",
                "session_id": self._session_id,
            }
            tmp = sf.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            tmp.replace(sf)
        except Exception:
            pass

    def _delete_state(self):
        try:
            _state_file().unlink(missing_ok=True)
        except Exception:
            pass

    # ── Thread run loop ───────────────────────────────────────────────────

    def run(self):
        total = len(self._queue)
        delay_multiplier = get_delay_multiplier()
        user_plan = resolve_user_plan()

        self.queue_progress.emit(
            f"Queue: pacing profile {user_plan.upper()} ({delay_multiplier:.1f}x delays)"
        )

        while self._current_index < total:
            # Check pause at top of each creator iteration
            if self._pause_flag:
                self._save_state()
                self.paused.emit()
                self.queue_progress.emit(
                    f"Queue: Paused at {self._current_index + 1}/{total}"
                )
                self._resume_event.wait()   # block until resume()

            if self._stop_flag:
                break

            # Network check before starting next creator
            if not _is_network_available():
                self._save_state()
                self.queue_progress.emit("Queue: Network unavailable — waiting for reconnection...")
                self.paused.emit()
                while not _is_network_available():
                    if self._stop_flag:
                        break
                    time.sleep(5)
                if self._stop_flag:
                    break
                self.queue_progress.emit("Queue: Network restored — resuming...")
                time.sleep(2)  # brief stabilization delay

            folder = self._queue[self._current_index]
            creator_name = folder.name

            self.queue_progress.emit(
                f"Queue: {self._current_index + 1}/{total} — @{creator_name}"
            )
            self.creator_started.emit(creator_name)
            self._save_state()

            success = self._run_one(folder)
            if self._stop_flag:
                break

            # If failed, check if it was due to network loss
            if not success and not _is_network_available():
                self._save_state()
                self.queue_progress.emit("Queue: Network lost during download — waiting...")
                self.paused.emit()
                while not _is_network_available():
                    if self._stop_flag:
                        break
                    time.sleep(5)
                if self._stop_flag:
                    break
                self.queue_progress.emit("Queue: Network restored — retrying last creator...")
                time.sleep(2)
                # Retry the same creator (don't increment index)
                continue

            self.creator_finished.emit(creator_name, success)
            self._current_index += 1

            # Random cooldown between creators (1-4s) for browser stability + anti-spam
            if self._current_index < total and not self._stop_flag:
                delay = random.uniform(1.0, 4.0) * delay_multiplier
                self.queue_progress.emit(f"Queue: Cooldown {delay:.1f}s before next creator...")
                time.sleep(delay)

        # Queue complete (or stopped)
        self._delete_state()
        if not self._stop_flag:
            self.queue_progress.emit(f"Queue: Done — {total} creator(s) processed")
            self.queue_finished.emit()
        else:
            self.queue_progress.emit("Queue: Stopped")
            self.queue_finished.emit()

    def _run_one(self, folder: Path) -> bool:
        """
        Run CreatorDownloadWorker for a single creator folder.
        Blocks until the worker finishes or is stopped.
        Returns True on success.
        """
        from .config_manager import CreatorConfig

        config = CreatorConfig(folder)
        creator_url = (config.creator_url or "").strip()

        if not creator_url:
            inferred = config.ensure_creator_url()
            creator_url = inferred or ""

        if not creator_url:
            self.queue_progress.emit(f"Skipped {folder.name}: no URL configured")
            return False

        self._worker_done_event.clear()
        result_holder = [{"success": False}]
        
        # Local state for combined status display
        status_state = {"msg": "", "speed": "", "eta": ""}

        worker = CreatorDownloadWorker(folder, creator_url)
        self._current_worker = worker

        # Forward pause/resume to worker
        if self._pause_flag:
            worker.pause()

        def _update_combined_status():
            txt = f"@{folder.name}: {status_state['msg']}"
            if status_state['speed']:
                txt += f" | {status_state['speed']}"
            if status_state['eta']:
                txt += f" | ETA: {status_state['eta']}"
            self.queue_progress.emit(txt)

        def _on_progress(msg: str):
            status_state["msg"] = msg
            _update_combined_status()

        def _on_speed(speed: str):
            status_state["speed"] = speed
            _update_combined_status()

        def _on_eta(eta: str):
            status_state["eta"] = eta
            _update_combined_status()

        def _on_finished(res: dict):
            result_holder[0] = res
            self._worker_done_event.set()

        def _on_pct(pct: int):
            self.creator_progress_pct.emit(folder.name, pct)

        worker.progress.connect(_on_progress)
        worker.download_speed.connect(_on_speed)
        worker.eta.connect(_on_eta)
        worker.progress_percent.connect(_on_pct)
        worker.finished.connect(_on_finished)
        worker.paused.connect(self._on_worker_paused)
        worker.start()

        # Wait for worker to finish (blocking, with stop checks).
        while not self._worker_done_event.wait(0.25):
            if self._stop_flag or (not worker.isRunning()):
                # Worker died or we stopped — either way, don't hang the queue.
                break

        # Ensure worker thread is fully done
        worker.wait(3000)

        # Read result directly from worker attribute (avoids cross-thread signal issues)
        final_result = getattr(worker, '_result', None) or result_holder[0]
        result_holder[0] = final_result

        # Cleanup
        try:
            worker.progress.disconnect(_on_progress)
            worker.finished.disconnect(_on_finished)
        except Exception:
            pass
        self._current_worker = None

        # Track total videos downloaded across entire queue for anti-spam
        downloaded_count = int(result_holder[0].get("downloaded", 0) or 0)
        prev_total = self._total_videos_downloaded
        self._total_videos_downloaded += downloaded_count

        # Anti-spam: extra delay every 20 videos (3-7s)
        if downloaded_count > 0:
            crossed_20 = (prev_total // 20) != (self._total_videos_downloaded // 20)
            if crossed_20:
                delay = random.uniform(3.0, 7.0) * get_delay_multiplier()
                self.queue_progress.emit(
                    f"Queue: Anti-spam cooldown {delay:.1f}s ({self._total_videos_downloaded} videos total)..."
                )
                time.sleep(delay)

        success = result_holder[0].get("success", False)
        print(f"[CreatorProfile] _run_one '{folder.name}' -> success={success}, downloaded={result_holder[0].get('downloaded', 0)}")
        return success

    def _on_worker_paused(self):
        """Worker emitted paused signal — propagate to queue level."""
        self._save_state()
        self.paused.emit()
