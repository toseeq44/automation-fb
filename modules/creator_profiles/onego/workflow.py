"""
OneGo workflow orchestrator — connects download queue + upload phase.
Runs in a QThread to keep the UI responsive.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from PyQt5.QtCore import QThread, pyqtSignal

from .models import OneGoReport, ProfileResult, PageResult, PageStatus, SkipReason
from .name_matcher import normalize_name, build_folder_map, match_bookmark_to_folder
from .upload_executor import collect_video_files, upload_single_video, delete_video_file

log = logging.getLogger(__name__)

MODE_DOWNLOAD_UPLOAD = "download_upload"
MODE_UPLOAD_ONLY = "upload_only"


def _links_root() -> Path:
    """Detect the Links Grabber root directory from creator_profiles behavior."""
    try:
        from modules.creator_profiles.page import _links_root as page_links_root
        return page_links_root()
    except Exception:
        return Path.home() / "Desktop" / "Links Grabber"


def _report_path() -> Path:
    """Stable path to persist the last OneGo report JSON."""
    try:
        from modules.config.paths import get_data_dir
        return get_data_dir() / "onego_last_report.json"
    except ImportError:
        root = Path(__file__).resolve().parents[3]
        data_dir = root / "data_files"
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir / "onego_last_report.json"


class OneGoWorker(QThread):
    """
    Orchestrates a OneGo run in a background thread.

    Signals:
        progress(str)       — status messages for the UI
        finished(dict)      — final report as dict
    """

    progress = pyqtSignal(str)
    finished_signal = pyqtSignal(dict)

    def __init__(
        self,
        mode: str,
        api_url: str,
        email: str,
        password: str,
        profile_hint: str,
        card_folders: List[Path],
        links_root: Path,
        download_trigger: Optional[Callable] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.mode = mode
        self.api_url = api_url
        self.email = email
        self.password = password
        self.profile_hint = profile_hint
        self.card_folders = card_folders
        self.links_root = links_root
        self._download_trigger = download_trigger
        self._stop = False
        self._download_done = False

    def stop(self):
        self._stop = True

    def mark_download_done(self):
        """Called externally when download queue finishes."""
        self._download_done = True

    def run(self):
        report = OneGoReport(mode=self.mode)
        try:
            # Phase 1: Download (optional)
            if self.mode == MODE_DOWNLOAD_UPLOAD:
                self.progress.emit("OneGo: Starting download phase...")
                if self._download_trigger:
                    self._download_trigger()
                    # Wait for download phase to complete
                    while not self._download_done and not self._stop:
                        time.sleep(0.5)
                    if self._stop:
                        self.progress.emit("OneGo: Stopped during download phase.")
                        self._emit_report(report)
                        return
                    self.progress.emit("OneGo: Download phase complete. Starting upload phase...")
                else:
                    self.progress.emit("OneGo: No download trigger — skipping to upload phase.")
            else:
                self.progress.emit("OneGo: Upload-only mode — starting upload phase...")

            # Phase 2: Upload
            self._run_upload_phase(report)

        except Exception as exc:
            log.error("[OneGo] Fatal error: %s", exc, exc_info=True)
            self.progress.emit(f"OneGo: Fatal error — {exc}")
        finally:
            self._emit_report(report)

    def _run_upload_phase(self, report: OneGoReport):
        """Execute the upload phase across all IX profiles."""
        from .ix_api import IXBrowserClient, IXAPIError
        from .ix_session import IXSessionManager

        # 1. Connect to IX API
        try:
            client = IXBrowserClient(self.api_url)
            session_mgr = IXSessionManager(client)
        except IXAPIError as exc:
            log.error("[OneGo] IX API init failed: %s", exc)
            self.progress.emit(f"OneGo: IX API connection failed — {exc}")
            return

        # 2. List IX profiles
        try:
            profiles = client.list_profiles()
        except IXAPIError as exc:
            log.error("[OneGo] Failed to list IX profiles: %s", exc)
            self.progress.emit(f"OneGo: Cannot list IX profiles — {exc}")
            return

        if not profiles:
            self.progress.emit("OneGo: No IX profiles found.")
            return

        # Filter by hint if provided
        if self.profile_hint:
            hint_lower = self.profile_hint.strip().lower()
            profiles = [p for p in profiles if hint_lower in p.profile_name.lower()]
            if not profiles:
                self.progress.emit(f"OneGo: No profiles matching hint '{self.profile_hint}'")
                return

        # 3. Build folder map from creator card folders
        folder_names = [f.name for f in self.card_folders if f.is_dir()]
        folder_map = build_folder_map(folder_names)
        # Also keep a name -> Path mapping
        name_to_path: Dict[str, Path] = {}
        for f in self.card_folders:
            norm = normalize_name(f.name)
            if norm:
                name_to_path[norm] = f

        self.progress.emit(f"OneGo: {len(profiles)} profile(s), {len(folder_names)} creator folder(s)")

        # 4. Process each profile
        for pi, profile in enumerate(profiles):
            if self._stop:
                self.progress.emit("OneGo: Stopped.")
                return

            profile_result = ProfileResult(profile_name=profile.profile_name)
            self.progress.emit(
                f"OneGo: Profile {pi+1}/{len(profiles)} — {profile.profile_name}"
            )

            # Open profile and attach
            ps = session_mgr.open_and_attach(profile)
            if not ps:
                # Profile open failed — record all folders as failed for this profile
                log.warning("[OneGo] Cannot open profile '%s'", profile.profile_name)
                profile_result.pages.append(PageResult(
                    page_name=profile.profile_name,
                    status=PageStatus.FAILED,
                    reason=SkipReason.PROFILE_OPEN_FAILED.value,
                ))
                report.profiles.append(profile_result)
                continue

            try:
                # Extract bookmarks
                bookmarks = session_mgr.extract_bookmarks(ps, facebook_only=True)
                if not bookmarks:
                    log.info("[OneGo] No Facebook bookmarks in profile '%s'", profile.profile_name)
                    profile_result.pages.append(PageResult(
                        page_name=profile.profile_name,
                        status=PageStatus.SKIPPED,
                        reason=SkipReason.BOOKMARK_NOT_FOUND.value,
                    ))
                    report.profiles.append(profile_result)
                    continue

                # Process each bookmark
                for bm in bookmarks:
                    if self._stop:
                        break

                    page_result = self._process_bookmark(
                        bm, folder_map, name_to_path, ps.driver
                    )
                    profile_result.pages.append(page_result)

            except Exception as exc:
                log.error("[OneGo] Error processing profile '%s': %s",
                          profile.profile_name, exc)
            finally:
                session_mgr.close(ps)

            report.profiles.append(profile_result)

            # Cooldown between profiles
            if pi < len(profiles) - 1 and not self._stop:
                self.progress.emit("OneGo: Cooldown between profiles...")
                time.sleep(3)

    def _process_bookmark(
        self, bm, folder_map, name_to_path, driver
    ) -> PageResult:
        """Process a single bookmark: match to folder, upload videos."""
        from .ix_session import Bookmark
        from .config_manager_helper import load_uploading_target

        bm_name = bm.title
        bm_url = bm.url

        # Match bookmark to folder
        matched_folder_name = match_bookmark_to_folder(bm_name, folder_map)
        if not matched_folder_name:
            return PageResult(
                page_name=bm_name,
                status=PageStatus.SKIPPED,
                reason=SkipReason.FOLDER_NOT_FOUND.value,
            )

        norm = normalize_name(matched_folder_name)
        folder_path = name_to_path.get(norm)
        if not folder_path or not folder_path.is_dir():
            return PageResult(
                page_name=bm_name,
                status=PageStatus.SKIPPED,
                reason=SkipReason.FOLDER_NOT_FOUND.value,
            )

        # Load uploading_target from config
        target = load_uploading_target(folder_path)
        if target <= 0:
            return PageResult(
                page_name=bm_name,
                target=0,
                status=PageStatus.SKIPPED,
                reason=SkipReason.TARGET_ZERO.value,
            )

        # Collect videos
        videos = collect_video_files(folder_path, limit=target)
        available = len(videos)

        if available == 0:
            return PageResult(
                page_name=bm_name,
                target=target,
                available=0,
                status=PageStatus.SKIPPED,
                reason=SkipReason.NO_VIDEOS.value,
            )

        # Upload videos one by one
        uploaded = 0
        for vi, video_path in enumerate(videos):
            if self._stop:
                break

            self.progress.emit(
                f"OneGo: Uploading {vi+1}/{len(videos)} for {bm_name}..."
            )

            success = upload_single_video(driver, bm_url, video_path)
            if success:
                uploaded += 1
                delete_video_file(video_path)
            else:
                log.warning("[OneGo] Upload failed for %s -> %s", bm_name, video_path.name)
                # Continue to next video (don't stop whole page)

            # Brief pause between uploads
            if vi < len(videos) - 1:
                time.sleep(3)

        # Determine status
        if uploaded == 0:
            status = PageStatus.FAILED
            reason = SkipReason.UPLOAD_ACTION_FAILED.value
        elif uploaded < target and available >= target:
            status = PageStatus.PARTIAL
            reason = SkipReason.UPLOAD_ACTION_FAILED.value
        elif available < target:
            status = PageStatus.PARTIAL
            reason = SkipReason.INSUFFICIENT_VIDEOS_PARTIAL.value
        else:
            status = PageStatus.SUCCESS
            reason = None

        return PageResult(
            page_name=bm_name,
            target=target,
            available=available,
            uploaded=uploaded,
            status=status,
            reason=reason,
        )

    def _emit_report(self, report: OneGoReport):
        """Persist report JSON and emit finished signal."""
        report_dict = report.to_dict()
        report_dict["completed_at"] = datetime.now().isoformat()

        # Persist to file
        try:
            rp = _report_path()
            rp.parent.mkdir(parents=True, exist_ok=True)
            with open(rp, "w", encoding="utf-8") as f:
                json.dump(report_dict, f, indent=2, ensure_ascii=False)
            log.info("[OneGo] Report saved to %s", rp)
        except Exception as exc:
            log.warning("[OneGo] Failed to save report: %s", exc)

        self.progress.emit(
            f"OneGo: Complete — uploaded {report.total_uploaded}, "
            f"skipped {report.total_skipped}, failed {report.total_failed}"
        )
        self.finished_signal.emit(report_dict)
