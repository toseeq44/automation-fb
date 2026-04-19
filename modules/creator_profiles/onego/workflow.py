"""
OneGo workflow orchestrator â€” connects download queue + upload phase.
Runs in a QThread to keep the UI responsive.
"""

from __future__ import annotations

import hashlib
import json
import logging
import random
import time
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PyQt5.QtCore import QThread, pyqtSignal

from .models import OneGoReport, ProfileResult, PageResult, PageStatus, SkipReason
from .name_matcher import normalize_name, build_folder_map, match_bookmark_to_folder
from .upload_executor import collect_video_files, upload_single_video, delete_video_file

log = logging.getLogger(__name__)

MODE_DOWNLOAD_UPLOAD = "download_upload"
MODE_UPLOAD_ONLY = "upload_only"

try:
    import pyautogui
    pyautogui.FAILSAFE = False
except ImportError:
    pyautogui = None


def _mouse_jitter():
    """Small random mouse movement to simulate human behavior."""
    if pyautogui is None:
        return
    try:
        x, y = pyautogui.position()
        dx = random.randint(-30, 30)
        dy = random.randint(-20, 20)
        pyautogui.moveTo(x + dx, y + dy, duration=random.uniform(0.2, 0.5))
    except Exception:
        pass


def _map_ix_error_to_session_reason(exc) -> str:
    """Map an IXAPIError (or generic exception) to a precise session_error reason."""
    code = getattr(exc, "code", None)
    if code == 2013:
        return SkipReason.KERNEL_MISSING.value
    msg = str(exc).lower()
    if ("connection refused" in msg) or (
        ("connect" in msg) and (("refused" in msg) or ("unreachable" in msg))
    ):
        return SkipReason.API_UNREACHABLE.value
    if any(kw in msg for kw in ("login", "auth", "unauthorized", "401", "credential")):
        return SkipReason.IX_LOGIN_FAILED.value
    return SkipReason.API_UNREACHABLE.value


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


def _resume_path() -> Path:
    """Stable path for OneGo resume checkpoints."""
    try:
        from modules.config.paths import get_data_dir
        return get_data_dir() / "onego_resume_state.json"
    except ImportError:
        root = Path(__file__).resolve().parents[3]
        data_dir = root / "data_files"
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir / "onego_resume_state.json"


class OneGoWorker(QThread):
    """
    Orchestrates a OneGo run in a background thread.

    Signals:
        progress(str)       â€” status messages for the UI
        finished(dict)      â€” final report as dict
    """

    progress = pyqtSignal(str)
    finished_signal = pyqtSignal(dict)
    download_requested = pyqtSignal(object)

    def __init__(
        self,
        mode: str,
        activity_enabled: bool,
        api_url: str,
        email: str,
        password: str,
        profile_hint: str,
        card_folders: List[Path],
        links_root: Path,
        download_folders: Optional[List[Path]] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.mode = mode
        self.activity_enabled = bool(activity_enabled)
        self.api_url = api_url
        self.email = email
        self.password = password
        self.profile_hint = profile_hint
        self.card_folders = card_folders
        self.links_root = links_root
        self._download_folders = list(download_folders or [])
        self._stop = False
        self._download_done = False
        self._download_stopped = False
        self._report_emitted = False

    def stop(self):
        self._stop = True

    def mark_download_done(self, stopped: bool = False):
        """Called externally when download queue finishes or is stopped."""
        self._download_done = True
        self._download_stopped = bool(stopped)

    def _build_resume_key(self, profiles: List[Any]) -> str:
        ids = "|".join(str(p.profile_id) for p in profiles)
        raw = (
            f"{self.api_url.strip().lower()}|"
            f"{self.mode}|"
            f"{self.profile_hint.strip().lower()}|"
            f"{ids}"
        )
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    def _load_resume_index(self, resume_key: str, total_profiles: int) -> int:
        """Load resume index for current profile list/key."""
        rp = _resume_path()
        if not rp.exists():
            return 0
        try:
            data = json.loads(rp.read_text(encoding="utf-8"))
        except Exception:
            return 0

        if data.get("resume_key") != resume_key:
            return 0

        idx = data.get("next_index", 0)
        try:
            idx = int(idx)
        except Exception:
            return 0

        if idx < 0 or idx >= total_profiles:
            return 0
        return idx

    def _save_resume_index(
        self,
        resume_key: str,
        next_index: int,
        total_profiles: int,
        last_profile_name: str = "",
    ) -> None:
        """Persist resume checkpoint after each processed profile."""
        try:
            rp = _resume_path()
            rp.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "resume_key": resume_key,
                "next_index": int(next_index),
                "total_profiles": int(total_profiles),
                "last_profile_name": last_profile_name or "",
                "updated_at": datetime.now().isoformat(),
            }
            rp.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as exc:
            log.debug("[OneGo] Could not save resume checkpoint: %s", exc)

    def _clear_resume_state(self) -> None:
        try:
            rp = _resume_path()
            if rp.exists():
                rp.unlink()
        except Exception as exc:
            log.debug("[OneGo] Could not clear resume checkpoint: %s", exc)

    def _safe_current_url(self, driver) -> str:
        try:
            return str(driver.current_url or "").strip()
        except Exception:
            return ""

    def _user_is_interacting(self, *, sample_seconds: float = 0.18, threshold: float = 10.0) -> bool:
        """Detect short bursts of real user mouse movement and yield immediately."""
        if pyautogui is None:
            return False
        try:
            start_pos = pyautogui.position()
            time.sleep(sample_seconds)
            end_pos = pyautogui.position()
            dx = end_pos[0] - start_pos[0]
            dy = end_pos[1] - start_pos[1]
            return ((dx * dx) + (dy * dy)) ** 0.5 >= threshold
        except Exception:
            return False

    def _move_mouse_naturally(self, *, duration: float) -> bool:
        """Slow, irregular mouse drift that yields if the user takes control."""
        if pyautogui is None:
            return False
        if self._user_is_interacting():
            return False

        tween = getattr(pyautogui, "easeInOutQuad", None)
        deadline = time.monotonic() + max(0.0, duration)
        try:
            screen_w, screen_h = pyautogui.size()
        except Exception:
            return False

        while time.monotonic() < deadline and not self._stop:
            if self._user_is_interacting():
                return False
            try:
                current_x, current_y = pyautogui.position()
                offset_x = random.randint(-140, 140)
                offset_y = random.randint(-90, 90)
                target_x = max(20, min(screen_w - 20, current_x + offset_x))
                target_y = max(20, min(screen_h - 20, current_y + offset_y))
                move_duration = min(
                    random.uniform(0.45, 1.35),
                    max(0.15, deadline - time.monotonic()),
                )
                pyautogui.moveTo(
                    target_x,
                    target_y,
                    duration=move_duration,
                    tween=tween,
                )
            except Exception:
                return False

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            if not self._sleep_with_stop(min(remaining, random.uniform(0.3, 1.2))):
                return False
        return True

    def _discover_creator_folders(self) -> List[Path]:
        """Combine loaded cards with a fresh scan of the Links Grabber root."""
        discovered: Dict[str, Path] = {}

        for folder in self.card_folders:
            try:
                if folder and folder.is_dir():
                    discovered[str(folder.resolve()).lower()] = folder
            except Exception:
                continue

        try:
            root = Path(self.links_root)
            if root.is_dir():
                for item in sorted(root.iterdir()):
                    if not item.is_dir() or item.name.startswith("."):
                        continue

                    child_dirs = [
                        child
                        for child in item.iterdir()
                        if child.is_dir() and not child.name.startswith(".")
                    ]
                    has_links = any(item.glob("*links*.txt")) or any(item.glob("*.txt"))
                    has_config = (item / "creator_config.json").exists()

                    candidates = [item] if (has_links or has_config or not child_dirs) else child_dirs
                    for candidate in candidates:
                        try:
                            discovered[str(candidate.resolve()).lower()] = candidate
                        except Exception:
                            continue
        except Exception as exc:
            log.debug("[OneGo] Creator folder scan fallback failed: %s", exc)

        return list(discovered.values())

    def _count_visible_matches(self, driver, by, selector: str, *, limit: int = 8) -> int:
        try:
            elements = driver.find_elements(by, selector)
        except Exception:
            return 0

        visible = 0
        for element in elements[:limit]:
            try:
                if element.is_displayed():
                    visible += 1
            except Exception:
                continue
        return visible

    def _sleep_with_stop(self, total_seconds: float, *, step: float = 0.5) -> bool:
        """Sleep in small steps so stop requests are honored quickly."""
        deadline = time.monotonic() + max(0.0, float(total_seconds))
        while not self._stop:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return True
            time.sleep(min(step, remaining))
        return False

    def _switch_to_existing_facebook_tab(self, driver) -> bool:
        try:
            original_handle = driver.current_window_handle
            handles = list(driver.window_handles)
        except Exception:
            return False

        for handle in handles:
            try:
                driver.switch_to.window(handle)
                time.sleep(0.4)
                current_url = self._safe_current_url(driver).lower()
                current_title = str(getattr(driver, "title", "") or "").lower()
                if "facebook.com" in current_url or "facebook" in current_title:
                    return True
            except Exception:
                continue

        try:
            driver.switch_to.window(original_handle)
        except Exception:
            pass
        return False

    def _verify_facebook_environment(self, driver) -> Tuple[bool, str]:
        try:
            from selenium.webdriver.common.by import By
        except Exception as exc:
            return False, f"selenium_unavailable:{exc}"

        current_url = self._safe_current_url(driver).lower()
        if not current_url or "facebook.com" not in current_url:
            return False, "not_facebook_url"

        negative_url_tokens = (
            "login", "checkpoint", "recover", "suspended", "disabled",
            "appeal", "two_step_verification", "security", "auth"
        )
        if any(token in current_url for token in negative_url_tokens):
            return False, "facebook_auth_wall_url"

        try:
            cookies = {
                str(cookie.get("name") or "").strip()
                for cookie in (driver.get_cookies() or [])
                if cookie.get("name")
            }
        except Exception:
            cookies = set()

        has_login_cookies = "c_user" in cookies and "xs" in cookies

        # Strong negative checks: login/auth walls and obvious non-home states.
        negative_selectors = [
            (By.NAME, "login"),
            (By.NAME, "email"),
            (By.NAME, "pass"),
            (By.CSS_SELECTOR, "input[type='password']"),
            (
                By.XPATH,
                "//*[contains(translate(normalize-space(text()),"
                " 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'log in')]",
            ),
        ]
        for by, selector in negative_selectors:
            if self._count_visible_matches(driver, by, selector, limit=4):
                return False, "facebook_login_form_detected"

        body_text = ""
        try:
            body = driver.find_element(By.TAG_NAME, "body")
            body_text = str(body.text or "").lower()
        except Exception:
            body_text = ""

        negative_text_tokens = (
            "forgot password",
            "forgotten password",
            "account suspended",
            "your account has been suspended",
            "account disabled",
            "session expired",
            "security check",
            "confirm your identity",
            "review recent login",
        )
        if any(token in body_text for token in negative_text_tokens):
            return False, "facebook_negative_text_state"

        account_checks = [
            (By.CSS_SELECTOR, "div[aria-label*='Account']"),
            (By.CSS_SELECTOR, "div[aria-label*='Your profile']"),
            (By.CSS_SELECTOR, "a[aria-label*='Profile']"),
            (By.CSS_SELECTOR, "div[role='banner']"),
        ]
        feed_checks = [
            (By.CSS_SELECTOR, "[role='feed']"),
            (By.CSS_SELECTOR, "div[role='main']"),
            (By.CSS_SELECTOR, "div[role='article']"),
        ]
        engagement_checks = [
            (
                By.XPATH,
                "//*[@aria-label and contains(translate(@aria-label,"
                " 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'comment')]",
            ),
            (
                By.XPATH,
                "//*[@aria-label and contains(translate(@aria-label,"
                " 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'share')]",
            ),
            (
                By.XPATH,
                "//*[contains(translate(normalize-space(text()),"
                " 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'comment')]",
            ),
            (
                By.XPATH,
                "//*[contains(translate(normalize-space(text()),"
                " 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'share')]",
            ),
        ]

        account_score = sum(
            1 for by, selector in account_checks
            if self._count_visible_matches(driver, by, selector, limit=4)
        )
        feed_score = sum(
            1 for by, selector in feed_checks
            if self._count_visible_matches(driver, by, selector, limit=6)
        )
        engagement_score = sum(
            1 for by, selector in engagement_checks
            if self._count_visible_matches(driver, by, selector, limit=6)
        )

        if has_login_cookies and account_score and feed_score:
            return True, "dom_account_feed_verified"
        if has_login_cookies and (feed_score + engagement_score) >= 2:
            return True, "dom_feed_engagement_verified"

        try:
            from modules.auto_uploader.auth.session_validator import SessionValidator

            validator = SessionValidator(driver=driver)
            if validator.is_logged_in() and (account_score or feed_score or has_login_cookies):
                return True, "session_validator_verified"
        except Exception:
            pass

        try:
            from modules.auto_uploader.approaches.ixbrowser.login_manager import LoginManager

            login_manager = LoginManager(driver, self.email or "", self.password or "")
            is_logged_in, _ = login_manager.check_login_status()
            if is_logged_in and (has_login_cookies or account_score or feed_score):
                return True, "login_manager_verified"
        except Exception:
            pass

        try:
            from PIL import Image
            from modules.auto_uploader.browser.advanced_screen_analyzer import AdvancedScreenAnalyzer

            analyzer = AdvancedScreenAnalyzer()
            screenshot = driver.get_screenshot_as_png()
            image = Image.open(BytesIO(screenshot))
            analysis = analyzer.detect_page_type(image)
            if (
                analysis.page_type in {"feed_page", "profile_page"}
                and analysis.confidence >= 0.35
                and (has_login_cookies or account_score or feed_score)
            ):
                return True, f"visual_{analysis.page_type}"
        except Exception:
            pass

        if has_login_cookies and account_score:
            return True, "cookie_account_verified"
        return False, "facebook_state_unverified"

    def _prepare_facebook_context(self, driver, profile_name: str, *, phase_label: str) -> bool:
        self.progress.emit(
            f"OneGo: {phase_label} checking existing Facebook tab for {profile_name}..."
        )
        if not self._switch_to_existing_facebook_tab(driver):
            self.progress.emit(
                f"OneGo: {phase_label} no existing Facebook tab for {profile_name}."
            )
            return False

        ok, reason = self._verify_facebook_environment(driver)
        if ok:
            self.progress.emit(
                f"OneGo: {phase_label} Facebook session verified for {profile_name} ({reason})."
            )
        else:
            self.progress.emit(
                f"OneGo: {phase_label} Facebook session not ready for {profile_name} ({reason})."
            )
        return ok

    def _dwell_on_facebook(self, driver, profile_name: str, *, phase_label: str) -> None:
        """Spend a short, stop-safe session on a verified Facebook tab."""
        if not self.activity_enabled:
            return

        dwell_seconds = random.uniform(10.0, 120.0)
        self.progress.emit(
            f"OneGo: {phase_label} browsing verified Facebook tab for "
            f"{profile_name} ({dwell_seconds:.0f}s)."
        )

        start = time.monotonic()
        loop_index = 0
        while not self._stop:
            elapsed = time.monotonic() - start
            remaining = dwell_seconds - elapsed
            if remaining <= 0:
                break

            if self._user_is_interacting():
                self.progress.emit(
                    f"OneGo: {phase_label} user activity detected for "
                    f"{profile_name}; skipping bot activity."
                )
                return

            ok, reason = self._verify_facebook_environment(driver)
            if not ok:
                self.progress.emit(
                    f"OneGo: {phase_label} Facebook dwell ended early for "
                    f"{profile_name} ({reason})."
                )
                return

            try:
                driver.execute_script("window.focus();")
            except Exception:
                pass

            action_roll = random.random()
            try:
                if action_roll < 0.26:
                    distance = random.randint(90, 260)
                    if random.random() < 0.28:
                        distance *= -1
                    driver.execute_script(
                        "window.scrollBy({top: arguments[0], behavior: 'smooth'});",
                        distance,
                    )
                elif action_roll < 0.50:
                    distance = random.randint(260, 720)
                    if random.random() < 0.18:
                        distance *= -1
                    driver.execute_script(
                        "window.scrollBy({top: arguments[0], behavior: 'smooth'});",
                        distance,
                    )
                elif action_roll < 0.66:
                    distance = random.randint(720, 1500)
                    if random.random() < 0.12:
                        distance *= -1
                    driver.execute_script(
                        "window.scrollBy({top: arguments[0], behavior: 'smooth'});",
                        distance,
                    )
                elif action_roll < 0.83:
                    mouse_duration = min(remaining, random.uniform(1.2, 4.0))
                    if not self._move_mouse_naturally(duration=mouse_duration):
                        self.progress.emit(
                            f"OneGo: {phase_label} user activity detected for "
                            f"{profile_name}; skipping bot activity."
                        )
                        return
                else:
                    # Reading pause; sometimes add a tiny reverse scroll first.
                    if random.random() < 0.35:
                        driver.execute_script(
                            "window.scrollBy({top: arguments[0], behavior: 'smooth'});",
                            random.randint(-220, 120),
                        )
            except Exception:
                pass

            loop_index += 1
            pause_seconds = min(
                remaining,
                random.uniform(2.5, 11.5) if loop_index > 1 else random.uniform(1.0, 6.5),
            )
            if not self._sleep_with_stop(pause_seconds):
                return

        if not self._stop:
            self.progress.emit(
                f"OneGo: {phase_label} Facebook dwell finished for {profile_name}."
            )

    def _process_profile_bookmarks(
        self,
        session_mgr,
        ps,
        folder_map,
        name_to_path,
        profile_result: ProfileResult,
    ) -> None:
        bookmarks = session_mgr.extract_bookmarks(ps, facebook_only=True)
        if not bookmarks:
            log.info("[OneGo] No Facebook bookmarks in profile '%s'", ps.profile.profile_name)
            profile_result.status = PageStatus.SKIPPED
            profile_result.reason = SkipReason.BOOKMARK_NOT_FOUND.value
            return

        if not self._sleep_with_stop(random.uniform(1.0, 3.0)):
            return

        for bi, bm in enumerate(bookmarks):
            if self._stop:
                break

            if bi > 0:
                if not self._sleep_with_stop(random.uniform(2.0, 5.0)):
                    return
                _mouse_jitter()

            page_result = self._process_bookmark(
                bm, folder_map, name_to_path, ps.driver
            )
            profile_result.pages.append(page_result)

    def _run_profile_behavior(
        self,
        session_mgr,
        ps,
        folder_map,
        name_to_path,
        profile_result: ProfileResult,
    ) -> None:
        if not self.activity_enabled:
            self.progress.emit(
                f"OneGo: Profile activity disabled for {ps.profile.profile_name}; upload-only flow."
            )
            self._process_profile_bookmarks(
                session_mgr, ps, folder_map, name_to_path, profile_result
            )
            return

        behavior = random.choice((1, 2))
        self.progress.emit(
            f"OneGo: Using behavior {behavior} for {ps.profile.profile_name}."
        )

        if behavior == 1:
            fb_ok = self._prepare_facebook_context(
                ps.driver,
                ps.profile.profile_name,
                phase_label="Behavior 1",
            )
            if fb_ok and not self._stop:
                self._dwell_on_facebook(
                    ps.driver,
                    ps.profile.profile_name,
                    phase_label="Behavior 1",
                )
            if self._stop:
                return
            if not fb_ok:
                self.progress.emit(
                    f"OneGo: Behavior 1 fallback -> bookmarks upload for {ps.profile.profile_name}."
                )
            self._process_profile_bookmarks(
                session_mgr, ps, folder_map, name_to_path, profile_result
            )
            return

        self._process_profile_bookmarks(
            session_mgr, ps, folder_map, name_to_path, profile_result
        )
        if not self._stop:
            fb_ok = self._prepare_facebook_context(
                ps.driver,
                ps.profile.profile_name,
                phase_label="Behavior 2",
            )
            if fb_ok and not self._stop:
                self._dwell_on_facebook(
                    ps.driver,
                    ps.profile.profile_name,
                    phase_label="Behavior 2",
                )

    def run(self):
        report = OneGoReport(mode=self.mode)
        try:
            # Phase 1: Download (optional)
            if self.mode == MODE_DOWNLOAD_UPLOAD:
                self.progress.emit("OneGo: Starting download phase...")
                if self._download_folders:
                    self.download_requested.emit(list(self._download_folders))
                    # Wait for download phase to complete
                    while not self._download_done and not self._stop:
                        time.sleep(0.5)
                    if self._stop or self._download_stopped:
                        report.session_error = "stopped"
                        self.progress.emit("OneGo: Stopped during download phase.")
                        return
                    self.progress.emit("OneGo: Download phase complete. Starting upload phase...")
                else:
                    self.progress.emit("OneGo: No download folders resolved â€” skipping to upload phase.")
            else:
                self.progress.emit("OneGo: Upload-only mode â€” starting upload phase...")

            # Phase 2: Upload
            self._run_upload_phase(report)

        except Exception as exc:
            log.error("[OneGo] Fatal error: %s", exc, exc_info=True)
            self.progress.emit(f"OneGo: Fatal error â€” {exc}")
        finally:
            if self._stop and not report.session_error:
                report.session_error = "stopped"
            self._emit_report(report)

    def _run_upload_phase(self, report: OneGoReport):
        """Execute the upload phase across all IX profiles."""
        from .ix_api import IXBrowserClient, IXAPIError
        from .ix_bootstrap import bootstrap_ix
        from .ix_session import IXSessionManager

        # 0. Bootstrap â€” ensure IX API is reachable (launch/login if needed)
        bs = bootstrap_ix(
            api_url=self.api_url,
            email=self.email,
            password=self.password,
            progress_cb=lambda msg: self.progress.emit(msg),
            timeout=60,
        )
        if not bs.success:
            reason = bs.reason or SkipReason.API_UNREACHABLE.value
            log.error("[OneGo] IX bootstrap failed: %s", reason)
            self.progress.emit(f"OneGo: IX bootstrap failed â€” {reason}")
            report.session_error = reason
            return

        if self._stop:
            return

        # 1. Connect to IX API
        try:
            client = IXBrowserClient(self.api_url)
            session_mgr = IXSessionManager(client)
        except (IXAPIError, Exception) as exc:
            reason = _map_ix_error_to_session_reason(exc)
            log.error("[OneGo] IX API init failed: %s", exc)
            self.progress.emit(f"OneGo: IX API connection failed â€” {exc}")
            report.session_error = reason
            return

        # 2. List IX profiles
        try:
            profiles = client.list_profiles()
        except (IXAPIError, Exception) as exc:
            reason = _map_ix_error_to_session_reason(exc)
            log.error("[OneGo] Failed to list IX profiles: %s", exc)
            self.progress.emit(f"OneGo: Cannot list IX profiles â€” {exc}")
            report.session_error = reason
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

        resume_key = self._build_resume_key(profiles)
        start_index = self._load_resume_index(resume_key, len(profiles))
        if start_index > 0:
            self.progress.emit(
                f"OneGo: Resuming from profile {start_index+1}/{len(profiles)}..."
            )

        # 3. Build folder map from creator card folders
        creator_folders = self._discover_creator_folders()
        folder_names = [f.name for f in creator_folders if f.is_dir()]
        folder_map = build_folder_map(folder_names)
        # Also keep a name -> Path mapping
        name_to_path: Dict[str, Path] = {}
        for f in creator_folders:
            norm = normalize_name(f.name)
            if norm:
                name_to_path[norm] = f

        self.progress.emit(f"OneGo: {len(profiles)} profile(s), {len(folder_names)} creator folder(s)")

        # 4. Process each profile one-by-one with human pacing
        for pi in range(start_index, len(profiles)):
            profile = profiles[pi]
            if self._stop:
                self.progress.emit("OneGo: Stopped.")
                return

            # Save current pointer first; if interruption happens mid-profile,
            # next run resumes from this same profile index.
            self._save_resume_index(resume_key, pi, len(profiles), profile.profile_name)

            # Cooldown between profiles (even after failures, skip before first)
            if pi > start_index and not self._stop:
                delay = random.uniform(3.0, 8.0)
                self.progress.emit(f"OneGo: Cooldown {delay:.1f}s between profiles...")
                if not self._sleep_with_stop(delay):
                    self.progress.emit("OneGo: Stopped.")
                    return

            profile_result = ProfileResult(profile_name=profile.profile_name)
            self.progress.emit(
                f"OneGo: Profile {pi+1}/{len(profiles)} â€” {profile.profile_name}"
            )

            # Open profile and attach
            ps = session_mgr.open_and_attach(profile)
            if not ps:
                reason = getattr(session_mgr, "last_failure_reason", None)
                reason = reason or SkipReason.PROFILE_OPEN_FAILED.value
                if reason == SkipReason.KERNEL_MISSING.value and not self._stop:
                    self.progress.emit(
                        f"OneGo: Kernel not ready for '{profile.profile_name}' — retrying once..."
                    )
                    retry_bs = bootstrap_ix(
                        api_url=self.api_url,
                        email=self.email,
                        password=self.password,
                        progress_cb=lambda msg: self.progress.emit(msg),
                        timeout=30,
                    )
                    if retry_bs.success:
                        time.sleep(random.uniform(2.0, 4.0))
                        ps = session_mgr.open_and_attach(profile)

                if not ps:
                    reason = getattr(session_mgr, "last_failure_reason", None) or reason
                    log.warning("[OneGo] Cannot open profile '%s': %s",
                                profile.profile_name, reason)
                    profile_result.status = PageStatus.FAILED
                    profile_result.reason = reason
                    report.profiles.append(profile_result)
                    self._save_resume_index(resume_key, pi + 1, len(profiles), profile.profile_name)
                    continue
            # Bring profile browser visible (maximize + foreground)
            from .ix_session import _bring_profile_visible
            self.progress.emit(
                f"OneGo: Bringing profile window to front â€” {profile.profile_name}"
            )
            _bring_profile_visible(ps.driver)

            # Human settle: visible random 2-8s with mouse movement
            settle = random.uniform(2.0, 8.0)
            self.progress.emit(f"OneGo: Visible settle {settle:.1f}s...")
            half = settle / 2
            if not self._sleep_with_stop(half):
                session_mgr.close(ps)
                self.progress.emit("OneGo: Stopped.")
                return
            _mouse_jitter()
            if not self._sleep_with_stop(settle - half):
                session_mgr.close(ps)
                self.progress.emit("OneGo: Stopped.")
                return
            _mouse_jitter()

            try:
                self._run_profile_behavior(
                    session_mgr, ps, folder_map, name_to_path, profile_result
                )

            except Exception as exc:
                log.error("[OneGo] Error processing profile '%s': %s",
                          profile.profile_name, exc)
            finally:
                session_mgr.close(ps)

            report.profiles.append(profile_result)

            # If interrupted during profile processing, keep pointer on same profile.
            if self._stop:
                self._save_resume_index(resume_key, pi, len(profiles), profile.profile_name)
                self.progress.emit("OneGo: Stopped.")
                return

            # Profile completed; move checkpoint to next profile index.
            self._save_resume_index(resume_key, pi + 1, len(profiles), profile.profile_name)

        # Full loop complete.
        self._clear_resume_state()

    def _process_bookmark(
        self, bm, folder_map, name_to_path, driver
    ) -> PageResult:
        """Process a single bookmark: match to folder, upload videos."""
        from .ix_session import Bookmark
        from .config_manager_helper import load_uploading_target

        bm_name = bm.title
        bm_url = bm.url

        self.progress.emit(f"OneGo: Matching bookmark '{bm_name}'...")

        # Match bookmark to folder
        matched_folder_name = match_bookmark_to_folder(bm_name, folder_map)
        if not matched_folder_name:
            self.progress.emit(f"OneGo: No creator folder match for bookmark '{bm_name}'.")
            return PageResult(
                page_name=bm_name,
                status=PageStatus.SKIPPED,
                reason=SkipReason.FOLDER_NOT_FOUND.value,
            )

        norm = normalize_name(matched_folder_name)
        folder_path = name_to_path.get(norm)
        if not folder_path or not folder_path.is_dir():
            self.progress.emit(
                f"OneGo: Matched folder '{matched_folder_name}' is not available on disk."
            )
            return PageResult(
                page_name=bm_name,
                status=PageStatus.SKIPPED,
                reason=SkipReason.FOLDER_NOT_FOUND.value,
            )

        self.progress.emit(
            f"OneGo: Bookmark '{bm_name}' matched folder '{folder_path.name}'."
        )

        # Collect uploadable videos first so config fallback can use them
        all_videos = collect_video_files(folder_path, limit=0)
        available = len(all_videos)

        if available == 0:
            self.progress.emit(
                f"OneGo: No uploadable videos found in '{folder_path.name}'."
            )
            return PageResult(
                page_name=bm_name,
                available=0,
                status=PageStatus.SKIPPED,
                reason=SkipReason.NO_VIDEOS.value,
            )

        # Load uploading_target from config
        target = load_uploading_target(folder_path)
        if target <= 0:
            config_path = folder_path / "creator_config.json"
            if not config_path.exists():
                target = available
                self.progress.emit(
                    f"OneGo: No creator_config for '{folder_path.name}' -> "
                    f"using all {available} uploadable video(s)."
                )
            else:
                self.progress.emit(
                    f"OneGo: Upload target is 0 for '{folder_path.name}' -> skipping."
                )
                return PageResult(
                    page_name=bm_name,
                    target=0,
                    available=available,
                    status=PageStatus.SKIPPED,
                    reason=SkipReason.TARGET_ZERO.value,
                )

        videos = all_videos[:target]
        self.progress.emit(
            f"OneGo: '{bm_name}' target={target}, available={available}, "
            f"selected_for_upload={len(videos)}."
        )

        # Upload videos one by one
        uploaded = 0
        encountered_incomplete = False
        for vi, video_path in enumerate(videos):
            if self._stop:
                break

            self.progress.emit(
                f"OneGo: Uploading {vi+1}/{len(videos)} for {bm_name}..."
            )

            success, upload_state = upload_single_video(
                driver,
                bm_url,
                video_path,
                progress_cb=self.progress.emit,
            )
            if success:
                uploaded += 1
                delete_video_file(video_path)
                self.progress.emit(
                    f"OneGo: Uploaded and deleted local file '{video_path.name}'."
                )
            else:
                log.warning(
                    "[OneGo] Upload failed for %s -> %s (%s)",
                    bm_name,
                    video_path.name,
                    upload_state,
                )
                self.progress.emit(
                    f"OneGo: Upload result for '{video_path.name}' -> {upload_state}."
                )
                if upload_state == "incomplete":
                    encountered_incomplete = True
                    self.progress.emit(
                        f"OneGo: Stopping further uploads for '{bm_name}' to avoid "
                        f"reloading while Facebook may still be processing."
                    )
                    break

            # Brief pause between uploads
            if vi < len(videos) - 1:
                if not self._sleep_with_stop(3):
                    break

        # Determine status
        if encountered_incomplete:
            status = PageStatus.PARTIAL
            reason = SkipReason.UPLOAD_ACTION_FAILED.value
        elif uploaded == 0:
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
        if self._report_emitted:
            return
        self._report_emitted = True

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

        if report.session_error == "stopped":
            self.progress.emit(
                f"OneGo: Stopped â€” uploaded {report.total_uploaded}, "
                f"skipped {report.total_skipped}, failed {report.total_failed}"
            )
        else:
            self.progress.emit(
                f"OneGo: Complete â€” uploaded {report.total_uploaded}, "
                f"skipped {report.total_skipped}, failed {report.total_failed}"
            )
        self.finished_signal.emit(report_dict)

