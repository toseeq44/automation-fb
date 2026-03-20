"""
OneGo upload executor — handles per-file upload to Facebook via Selenium,
with delete-on-success and partial handling.
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import List, Optional

log = logging.getLogger(__name__)

_VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".flv", ".wmv", ".m4v"}

# JS to inject a file into an input element and make it visible
_MAKE_INPUT_VISIBLE_JS = """
arguments[0].style.display = 'block';
arguments[0].style.visibility = 'visible';
arguments[0].style.opacity = '1';
"""

_HIDE_INPUT_JS = """
arguments[0].style.display = 'none';
"""


def collect_video_files(folder: Path, limit: int = 0) -> List[Path]:
    """
    Collect video files from a folder. Returns up to `limit` files (0 = all).
    Sorted by modification time (oldest first).
    """
    folder = Path(folder)
    if not folder.is_dir():
        return []
    videos = [
        f for f in folder.iterdir()
        if f.is_file() and f.suffix.lower() in _VIDEO_EXTS
    ]
    videos.sort(key=lambda f: f.stat().st_mtime)
    if limit > 0:
        videos = videos[:limit]
    return videos


def upload_single_video(driver, bookmark_url: str, video_path: Path, max_retries: int = 2) -> bool:
    """
    Upload a single video to a Facebook page via Selenium.

    Steps:
    1. Navigate to the bookmark URL (Facebook page).
    2. Wait for page load.
    3. Find file input, inject video path.
    4. Click "Add Videos"/"Create Reel" button.
    5. Wait for upload progress.
    6. Return True if upload initiated, False on failure.

    Parameters
    ----------
    driver : selenium WebDriver
    bookmark_url : str
        The Facebook page URL from bookmarks.
    video_path : Path
        Absolute path to the video file.
    max_retries : int

    Returns
    -------
    bool
        True if upload was successful.
    """
    from selenium.webdriver.common.by import By

    video_path = Path(video_path)
    if not video_path.exists():
        log.error("[OneGo-Upload] File not found: %s", video_path)
        return False

    video_str = str(video_path.resolve())
    size_mb = video_path.stat().st_size / (1024 * 1024)
    log.info("[OneGo-Upload] Uploading: %s (%.1f MB)", video_path.name, size_mb)

    for attempt in range(1, max_retries + 1):
        try:
            log.info("[OneGo-Upload] Attempt %d/%d — navigating to %s",
                     attempt, max_retries, bookmark_url[:80])

            # 1. Navigate to bookmark
            driver.get(bookmark_url)
            time.sleep(4)

            # 2. Wait for page stabilization
            try:
                driver.execute_script("window.focus();")
            except Exception:
                pass
            time.sleep(2)

            # 3. Find file inputs and inject file path
            file_inputs = driver.find_elements(By.XPATH, "//input[@type='file']")
            if not file_inputs:
                log.warning("[OneGo-Upload] No file input found on page (attempt %d)", attempt)
                if attempt < max_retries:
                    time.sleep(3)
                    continue
                return False

            file_injected = False
            for idx, fi in enumerate(file_inputs):
                try:
                    driver.execute_script(_MAKE_INPUT_VISIBLE_JS, fi)
                except Exception:
                    pass
                try:
                    fi.send_keys(video_str)
                    time.sleep(1)
                    value = fi.get_attribute("value")
                    if value and (video_path.name in value or video_str in value):
                        file_injected = True
                        log.info("[OneGo-Upload] File injected via input #%d", idx + 1)
                except Exception as exc:
                    log.debug("[OneGo-Upload] send_keys failed on input #%d: %s", idx + 1, exc)
                try:
                    driver.execute_script(_HIDE_INPUT_JS, fi)
                except Exception:
                    pass
                if file_injected:
                    break

            if not file_injected:
                log.warning("[OneGo-Upload] File injection failed (attempt %d)", attempt)
                if attempt < max_retries:
                    time.sleep(3)
                    continue
                return False

            # 4. Try to click "Add Videos" / "Create Reel" button
            _click_upload_button(driver)

            # 5. Close any file-dialog windows (Windows only)
            _close_file_dialogs()

            # 6. Wait for upload to settle
            time.sleep(5)

            # 7. Check for upload progress indicators
            if _detect_upload_progress(driver):
                log.info("[OneGo-Upload] Upload progress detected, waiting for completion...")
                _wait_for_upload_completion(driver, timeout=300)
                log.info("[OneGo-Upload] Upload complete: %s", video_path.name)
                return True
            else:
                # Even without explicit progress detection, if file was injected
                # and button clicked, consider it initiated
                log.info("[OneGo-Upload] Upload initiated (no explicit progress bar): %s",
                         video_path.name)
                time.sleep(10)
                return True

        except Exception as exc:
            log.error("[OneGo-Upload] Attempt %d failed: %s", attempt, exc)
            if attempt < max_retries:
                time.sleep(3)

    log.error("[OneGo-Upload] All %d attempts failed for %s", max_retries, video_path.name)
    return False


def delete_video_file(video_path: Path) -> bool:
    """Delete a video file after successful upload."""
    try:
        video_path = Path(video_path)
        if video_path.exists():
            video_path.unlink()
            log.info("[OneGo-Upload] Deleted: %s", video_path.name)
            return True
        return False
    except Exception as exc:
        log.warning("[OneGo-Upload] Failed to delete %s: %s", video_path, exc)
        return False


# -- Internal helpers ------------------------------------------------------

def _click_upload_button(driver) -> bool:
    """Try to find and click an 'Add Videos' / 'Create Reel' style button."""
    from selenium.webdriver.common.by import By

    # Strategy 1: Look for common Facebook upload button text patterns
    button_texts = [
        "Add videos", "Add video", "Create reel", "Create Reel",
        "Upload video", "Add Videos", "Upload Video",
    ]
    for text in button_texts:
        try:
            elements = driver.find_elements(
                By.XPATH,
                f"//*[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ',"
                f"'abcdefghijklmnopqrstuvwxyz'), '{text.lower()}')]"
            )
            for el in elements:
                if el.is_displayed():
                    el.click()
                    log.info("[OneGo-Upload] Clicked button: '%s'", text)
                    time.sleep(2)
                    return True
        except Exception:
            continue

    # Strategy 2: aria-label based
    for label in ["Add videos", "Create reel", "Upload", "Add video"]:
        try:
            el = driver.find_element(
                By.XPATH, f"//*[@aria-label='{label}' or @aria-label='{label.lower()}']"
            )
            if el.is_displayed():
                el.click()
                log.info("[OneGo-Upload] Clicked aria-label button: '%s'", label)
                time.sleep(2)
                return True
        except Exception:
            continue

    log.warning("[OneGo-Upload] No upload button found — file may still upload via input injection")
    return False


def _close_file_dialogs():
    """Close any Windows file dialog windows that may have opened."""
    try:
        import platform
        if platform.system() != "Windows":
            return

        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        WM_CLOSE = 0x0010

        # Wait briefly for dialog to appear
        time.sleep(1)

        def callback(hwnd, _):
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buf = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buf, length + 1)
                    title = buf.value.lower()
                    if any(kw in title for kw in ("open", "upload", "file", "choose")):
                        user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
                        log.debug("[OneGo-Upload] Closed dialog: %s", buf.value)
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        user32.EnumWindows(WNDENUMPROC(callback), 0)
    except Exception as exc:
        log.debug("[OneGo-Upload] Dialog close error: %s", exc)


def _detect_upload_progress(driver) -> bool:
    """Check if Facebook shows an upload progress indicator."""
    from selenium.webdriver.common.by import By

    indicators = [
        "//div[contains(@aria-label, 'upload')]",
        "//div[contains(@aria-label, 'progress')]",
        "//*[contains(@role, 'progressbar')]",
        "//span[contains(text(), '%')]",
    ]
    for xpath in indicators:
        try:
            elements = driver.find_elements(By.XPATH, xpath)
            if elements:
                return True
        except Exception:
            continue
    return False


def _wait_for_upload_completion(driver, timeout: int = 300):
    """Wait for upload progress to complete or timeout."""
    start = time.time()
    while time.time() - start < timeout:
        time.sleep(5)
        # Check if progress bar disappeared (upload done)
        if not _detect_upload_progress(driver):
            return
        # Check for success indicators
        try:
            from selenium.webdriver.common.by import By
            success = driver.find_elements(
                By.XPATH,
                "//*[contains(text(), 'shared') or contains(text(), 'published') "
                "or contains(text(), 'Posted')]"
            )
            if success:
                return
        except Exception:
            pass
    log.warning("[OneGo-Upload] Upload wait timed out after %ds", timeout)
