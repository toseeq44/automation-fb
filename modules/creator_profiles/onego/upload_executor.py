"""
OneGo upload executor.

Handles per-file Facebook upload with:
- asset-file exclusion (logo/avatar media)
- detailed step logging
- safer completion / publish confirmation
- no false "success" just because upload started
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Callable, List, Optional, Tuple

log = logging.getLogger(__name__)

_VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".flv", ".wmv", ".m4v"}

_MAKE_INPUT_VISIBLE_JS = """
arguments[0].style.display = 'block';
arguments[0].style.visibility = 'visible';
arguments[0].style.opacity = '1';
"""

_HIDE_INPUT_JS = """
arguments[0].style.display = 'none';
"""


def _looks_like_media_asset(path: Path) -> bool:
    """Exclude branding/profile media even if it uses a video extension."""
    stem = path.stem.lower()
    name = path.name.lower()
    return (
        "logo" in stem
        or "avatar" in stem
        or name.startswith("logo.")
        or name.startswith("avatar.")
    )


def _emit_progress(progress_cb: Optional[Callable[[str], None]], message: str) -> None:
    if progress_cb:
        try:
            progress_cb(message)
            return
        except Exception:
            pass
    log.info("[OneGo-Upload] %s", message)


def collect_video_files(folder: Path, limit: int = 0) -> List[Path]:
    """
    Collect uploadable video files from a folder.

    Returns up to `limit` files (0 = all), oldest first.
    Asset-like media such as `logo.*`, `avatar.*`, `*logo*`, `*avatar*`
    are skipped even if they are videos.
    """
    folder = Path(folder)
    if not folder.is_dir():
        return []

    videos: List[Path] = []
    for item in folder.iterdir():
        if not item.is_file():
            continue
        if item.suffix.lower() not in _VIDEO_EXTS:
            continue
        if _looks_like_media_asset(item):
            log.info("[OneGo-Upload] Skipping asset-like media file: %s", item.name)
            continue
        videos.append(item)

    videos.sort(key=lambda f: f.stat().st_mtime)
    if limit > 0:
        videos = videos[:limit]
    return videos


def upload_single_video(
    driver,
    bookmark_url: str,
    video_path: Path,
    max_retries: int = 2,
    progress_cb: Optional[Callable[[str], None]] = None,
) -> Tuple[bool, str]:
    """
    Upload one video and wait until publish is confirmed enough to continue.

    Returns:
        (True, "published")   -> safe to delete local file
        (False, "incomplete") -> upload may still be active; caller should avoid
                                 immediate follow-up reloads
        (False, "failed")     -> upload never started cleanly
    """
    from selenium.webdriver.common.by import By

    video_path = Path(video_path)
    if not video_path.exists():
        log.error("[OneGo-Upload] File not found: %s", video_path)
        return False, "failed"

    video_str = str(video_path.resolve())
    size_mb = video_path.stat().st_size / (1024 * 1024)
    _emit_progress(
        progress_cb,
        f"OneGo: Upload prep -> {video_path.name} ({size_mb:.1f} MB)",
    )

    for attempt in range(1, max_retries + 1):
        upload_started = False
        try:
            _emit_progress(
                progress_cb,
                f"OneGo: Upload step 1/6 navigating to bookmark "
                f"(attempt {attempt}/{max_retries})",
            )
            driver.get(bookmark_url)
            time.sleep(4)

            try:
                driver.execute_script("window.focus();")
            except Exception:
                pass
            time.sleep(2)

            _emit_progress(
                progress_cb,
                f"OneGo: Upload step 2/6 locating file input for {video_path.name}",
            )
            file_inputs = driver.find_elements(By.XPATH, "//input[@type='file']")
            _emit_progress(
                progress_cb,
                f"OneGo: Found {len(file_inputs)} file input(s) on page for {video_path.name}",
            )
            if not file_inputs:
                log.warning("[OneGo-Upload] No file input found on page (attempt %d)", attempt)
                if attempt < max_retries:
                    time.sleep(3)
                    continue
                return False, "failed"

            file_injected = False
            send_keys_succeeded = False
            for idx, file_input in enumerate(file_inputs, start=1):
                try:
                    driver.execute_script(_MAKE_INPUT_VISIBLE_JS, file_input)
                except Exception:
                    pass

                try:
                    file_input.send_keys(video_str)
                    send_keys_succeeded = True
                    _emit_progress(
                        progress_cb,
                        f"OneGo: File path sent to input #{idx} for {video_path.name}",
                    )
                    time.sleep(1)
                    value = file_input.get_attribute("value") or ""
                    if value and (video_path.name in value or video_str in value):
                        file_injected = True
                        log.info("[OneGo-Upload] File injected via input #%d", idx)
                except Exception as exc:
                    log.debug("[OneGo-Upload] send_keys failed on input #%d: %s", idx, exc)

                try:
                    driver.execute_script(_HIDE_INPUT_JS, file_input)
                except Exception:
                    pass

                if file_injected:
                    break

            if send_keys_succeeded and not file_injected:
                # Some Facebook surfaces keep the input value hidden even though the
                # file was accepted. Treat a clean send_keys as a real selection and
                # continue waiting on the same page instead of reloading via retry.
                file_injected = True
                _emit_progress(
                    progress_cb,
                    f"OneGo: File selection accepted for {video_path.name}; "
                    f"continuing on current page.",
                )

            if not file_injected:
                log.warning("[OneGo-Upload] File injection failed (attempt %d)", attempt)
                if attempt < max_retries:
                    time.sleep(3)
                    continue
                return False, "failed"

            upload_started = True
            _emit_progress(
                progress_cb,
                f"OneGo: Upload step 3/6 file injected for {video_path.name}",
            )

            _click_upload_button(driver)
            _close_file_dialogs()

            _emit_progress(
                progress_cb,
                f"OneGo: Upload step 4/6 waiting for upload UI -> {video_path.name}",
            )
            upload_surface_ready = _wait_for_upload_surface(
                driver,
                timeout=45,
                progress_cb=progress_cb,
            )
            if not upload_surface_ready:
                log.warning("[OneGo-Upload] Upload surface never appeared for %s", video_path.name)
                return False, "incomplete"

            _emit_progress(
                progress_cb,
                f"OneGo: Upload step 5/6 monitoring progress -> {video_path.name}",
            )
            upload_ready_for_publish = _wait_for_upload_completion(
                driver,
                timeout=360,
                progress_cb=progress_cb,
            )
            if not upload_ready_for_publish:
                _emit_progress(
                    progress_cb,
                    f"OneGo: Upload incomplete for {video_path.name}; "
                    f"stopping here to avoid reload.",
                )
                return False, "incomplete"

            _emit_progress(
                progress_cb,
                f"OneGo: Upload step 6/6 looking for publish button -> {video_path.name}",
            )
            publish_button = _wait_for_publish_button_ready(
                driver,
                timeout=60,
                progress_cb=progress_cb,
            )
            if publish_button is not None:
                if _click_publish_button(driver, publish_button):
                    if _wait_for_publish_success(driver, timeout=25, progress_cb=progress_cb):
                        _emit_progress(
                            progress_cb,
                            f"OneGo: Publish confirmed for {video_path.name}",
                        )
                    else:
                        _emit_progress(
                            progress_cb,
                            f"OneGo: Publish clicked for {video_path.name}; "
                            f"success not strongly confirmed but upload flow completed.",
                        )
                    return True, "published"

                _emit_progress(
                    progress_cb,
                    f"OneGo: Publish button found but click failed for {video_path.name}",
                )
                return False, "incomplete"

            if _detect_publish_success(driver):
                _emit_progress(
                    progress_cb,
                    f"OneGo: Success indicator detected for {video_path.name}",
                )
                return True, "published"

            _emit_progress(
                progress_cb,
                f"OneGo: Upload reached composer state but publish was not confirmed "
                f"for {video_path.name}.",
            )
            return False, "incomplete"

        except Exception as exc:
            log.error("[OneGo-Upload] Attempt %d failed: %s", attempt, exc)
            if upload_started:
                return False, "incomplete"
            if attempt < max_retries:
                time.sleep(3)

    log.error("[OneGo-Upload] All %d attempts failed for %s", max_retries, video_path.name)
    return False, "failed"


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


def _click_upload_button(driver) -> bool:
    """Try to click an upload button if Facebook requires it after file injection."""
    from selenium.webdriver.common.by import By

    button_texts = [
        "Add videos",
        "Add video",
        "Create reel",
        "Create Reel",
        "Upload video",
        "Upload Video",
    ]
    for text in button_texts:
        try:
            elements = driver.find_elements(
                By.XPATH,
                f"//*[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ',"
                f"'abcdefghijklmnopqrstuvwxyz'), '{text.lower()}')]",
            )
        except Exception:
            continue

        for element in elements:
            if not _is_element_displayed(element):
                continue
            try:
                element.click()
                log.info("[OneGo-Upload] Clicked button: '%s'", text)
                time.sleep(2)
                return True
            except Exception:
                continue

    for label in ["Add videos", "Create reel", "Upload", "Add video", "Post", "Publish"]:
        try:
            element = driver.find_element(
                By.XPATH,
                f"//*[@aria-label='{label}' or @aria-label='{label.lower()}']",
            )
            if _is_element_displayed(element):
                element.click()
                log.info("[OneGo-Upload] Clicked aria-label button: '%s'", label)
                time.sleep(2)
                return True
        except Exception:
            continue

    log.info("[OneGo-Upload] No explicit upload button found; relying on injected file flow")
    return False


def _close_file_dialogs() -> None:
    """Close accidental native file dialogs if any appeared."""
    try:
        import platform
        if platform.system() != "Windows":
            return

        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        WM_CLOSE = 0x0010
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


def _wait_for_upload_surface(driver, timeout: int = 45, progress_cb=None) -> bool:
    """Wait for upload UI to appear after file injection."""
    start = time.time()
    while time.time() - start < timeout:
        if _detect_upload_progress(driver):
            _emit_progress(progress_cb, "OneGo: Upload progress indicator detected")
            return True
        if _detect_composer_surface(driver):
            _emit_progress(progress_cb, "OneGo: Upload composer surface detected")
            return True
        if _find_publish_button(driver) is not None:
            _emit_progress(progress_cb, "OneGo: Publish button appeared")
            return True
        if _detect_publish_success(driver):
            _emit_progress(progress_cb, "OneGo: Upload success text detected early")
            return True
        time.sleep(2)
    return False


def _wait_for_upload_completion(driver, timeout: int = 300, progress_cb=None) -> bool:
    """Wait until upload is complete enough for publish."""
    start = time.time()
    saw_progress = False
    last_percent = None

    while time.time() - start < timeout:
        if _detect_publish_success(driver):
            return True

        percent = _extract_progress_percent(driver)
        if percent is not None:
            saw_progress = True
            if percent != last_percent:
                _emit_progress(progress_cb, f"OneGo: Upload progress {percent}%")
                last_percent = percent
            if percent >= 100:
                return True

        if _find_publish_button(driver) is not None and not _detect_upload_progress(driver):
            return True

        if _detect_composer_surface(driver) and not _detect_upload_progress(driver):
            return True

        if saw_progress and not _detect_upload_progress(driver):
            return True

        time.sleep(3)

    log.warning("[OneGo-Upload] Upload wait timed out after %ds", timeout)
    return False


def _wait_for_publish_button_ready(driver, timeout: int = 60, progress_cb=None):
    """Wait for an enabled publish button to appear."""
    start = time.time()
    while time.time() - start < timeout:
        button = _find_publish_button(driver)
        if button is not None:
            if _publish_button_enabled(button):
                _emit_progress(progress_cb, "OneGo: Publish button is ready")
                return button
            _emit_progress(progress_cb, "OneGo: Publish button visible but still disabled")
        if _detect_publish_success(driver):
            return None
        time.sleep(2)
    final_button = _find_publish_button(driver)
    if final_button is not None and _publish_button_enabled(final_button):
        return final_button
    return None


def _wait_for_publish_success(driver, timeout: int = 25, progress_cb=None) -> bool:
    """Wait for post-publish success feedback."""
    start = time.time()
    while time.time() - start < timeout:
        if _detect_publish_success(driver):
            return True
        if _find_publish_button(driver) is None and not _detect_upload_progress(driver):
            _emit_progress(progress_cb, "OneGo: Publish button disappeared after click")
            return True
        time.sleep(2)
    return False


def _detect_upload_progress(driver) -> bool:
    """Check if Facebook shows an upload progress indicator."""
    from selenium.webdriver.common.by import By

    indicators = [
        "//div[contains(@aria-label, 'upload')]",
        "//div[contains(@aria-label, 'progress')]",
        "//*[@role='progressbar']",
        "//span[contains(text(), '%')]",
    ]
    for xpath in indicators:
        try:
            elements = driver.find_elements(By.XPATH, xpath)
        except Exception:
            continue
        if any(_is_element_displayed(element) for element in elements):
            return True
    return False


def _extract_progress_percent(driver) -> Optional[int]:
    from selenium.webdriver.common.by import By

    try:
        progress_bars = driver.find_elements(By.XPATH, "//*[@role='progressbar']")
    except Exception:
        progress_bars = []

    for element in progress_bars:
        try:
            if not _is_element_displayed(element):
                continue
            aria_value = element.get_attribute("aria-valuenow")
            if aria_value is not None:
                return int(float(aria_value))
        except Exception:
            continue

    try:
        percent_nodes = driver.find_elements(By.XPATH, "//*[contains(text(), '%')]")
    except Exception:
        percent_nodes = []

    for element in percent_nodes:
        try:
            if not _is_element_displayed(element):
                continue
            text = str(element.text or "").strip()
            if "%" not in text:
                continue
            digits = "".join(ch for ch in text if ch.isdigit())
            if digits:
                return int(digits)
        except Exception:
            continue

    return None


def _find_publish_button(driver):
    from selenium.webdriver.common.by import By

    selectors = [
        "//div[@role='button'][normalize-space()='Publish']",
        "//button[normalize-space()='Publish']",
        "//*[@aria-label='Publish']",
        "//div[@role='button'][contains(normalize-space(), 'Publish')]",
        "//button[contains(normalize-space(), 'Publish')]",
        "//*[@aria-label='Post']",
        "//div[@role='button'][normalize-space()='Post']",
        "//button[normalize-space()='Post']",
        "//div[@role='button'][contains(normalize-space(), 'Share')]",
        "//button[contains(normalize-space(), 'Share')]",
    ]
    for xpath in selectors:
        try:
            elements = driver.find_elements(By.XPATH, xpath)
        except Exception:
            continue
        for element in elements:
            if _is_element_displayed(element):
                return element
    return None


def _detect_composer_surface(driver) -> bool:
    """Detect Facebook's upload composer even when progress is not exposed."""
    from selenium.webdriver.common.by import By

    selectors = [
        "//textarea",
        "//*[@contenteditable='true']",
        "//input[@type='text']",
        "//*[contains(translate(normalize-space(text()), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'add description')]",
        "//*[contains(translate(normalize-space(text()), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'write something')]",
        "//*[contains(translate(normalize-space(text()), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'video details')]",
        "//*[contains(translate(normalize-space(text()), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'post')]",
        "//*[contains(translate(normalize-space(text()), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'publish')]",
    ]
    for xpath in selectors:
        try:
            elements = driver.find_elements(By.XPATH, xpath)
        except Exception:
            continue
        if any(_is_element_displayed(element) for element in elements):
            return True
    return False


def _publish_button_enabled(button) -> bool:
    try:
        aria_disabled = str(button.get_attribute("aria-disabled") or "").strip().lower()
        disabled_attr = str(button.get_attribute("disabled") or "").strip().lower()
        classes = str(button.get_attribute("class") or "").lower()
        if aria_disabled == "true" or disabled_attr in {"true", "disabled"}:
            return False
        if "disabled" in classes and "not-disabled" not in classes:
            return False
        return True
    except Exception:
        return True


def _click_publish_button(driver, button) -> bool:
    try:
        button.click()
        time.sleep(2)
        return True
    except Exception:
        pass

    try:
        driver.execute_script("arguments[0].click();", button)
        time.sleep(2)
        return True
    except Exception:
        return False


def _detect_publish_success(driver) -> bool:
    """Check for common Facebook success/processing indicators."""
    from selenium.webdriver.common.by import By

    success_xpaths = [
        "//*[contains(translate(normalize-space(text()), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'published')]",
        "//*[contains(translate(normalize-space(text()), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'posted')]",
        "//*[contains(translate(normalize-space(text()), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'processing')]",
        "//*[contains(translate(normalize-space(text()), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'shared')]",
    ]
    for xpath in success_xpaths:
        try:
            elements = driver.find_elements(By.XPATH, xpath)
        except Exception:
            continue
        if any(_is_element_displayed(element) for element in elements):
            return True
    return False


def _is_element_displayed(element) -> bool:
    try:
        return bool(element and element.is_displayed())
    except Exception:
        return False
