"""
Video Upload Helper for ixBrowser Approach
Handles bulk video upload to Facebook bookmarks
"""

import logging
import os
import time
import glob
import pyautogui
import random
import shutil
import pyperclip
import math
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Phase 2: Import core modules for robustness
from .core.state_manager import StateManager
from .core.network_monitor import NetworkMonitor
from .utils.file_handler import FileHandler

logger = logging.getLogger(__name__)

# Image paths for buttons
ADD_VIDEOS_BUTTON_IMAGE = "/home/user/automation-fb/modules/auto_uploader/helper_images/add_videos_button.png"
PUBLISH_BUTTON_ENABLED_IMAGE = "/home/user/automation-fb/modules/auto_uploader/helper_images/publish_button_after_data.png"
PUBLISH_BUTTON_DISABLED_IMAGE = "/home/user/automation-fb/modules/auto_uploader/helper_images/publish_button_befor_data.png"


class VideoUploadHelper:
    """Helper class for uploading videos to Facebook via bookmarks."""

    def __init__(self, driver: Any, state_manager: StateManager = None,
                 network_monitor: NetworkMonitor = None):
        """
        Initialize upload helper.

        Args:
            driver: Selenium WebDriver instance
            state_manager: Optional StateManager for persistence (Phase 2)
            network_monitor: Optional NetworkMonitor for resilience (Phase 2)
        """
        self.driver = driver
        self.upload_timeout = 600  # 10 minutes max per video

        # Phase 2: Robustness components
        self.state_manager = state_manager or StateManager()
        self.network_monitor = network_monitor or NetworkMonitor(check_interval=10)
        self.file_handler = FileHandler()

        # Track current upload session
        self.current_video = None
        self.current_bookmark = None
        self.current_attempt = 0

        logger.info("[Upload] ✓ VideoUploadHelper initialized with Phase 2 robustness")

    def ensure_window_ready(self, operation_name: str = "operation") -> bool:
        """
        **DEFENSIVE CHECK** - Ensure browser window is ready before any critical operation.

        This method performs 3 checks before proceeding:
        1. Activate browser window (bring to foreground)
        2. Dismiss any visible notifications/popups
        3. Verify window is responsive

        Call this before EVERY critical step to prevent failures.

        Args:
            operation_name: Name of operation (for logging)

        Returns:
            True if window is ready, False if issues detected
        """
        try:
            logger.info("[Upload] ═══════════════════════════════════════════")
            logger.info("[Upload] DEFENSIVE CHECK: Preparing for %s", operation_name)
            logger.info("[Upload] ═══════════════════════════════════════════")

            # Step 1: Activate browser window (bring to foreground)
            try:
                logger.info("[Upload] Step 1/3: Activating browser window...")

                # Maximize window
                self.driver.maximize_window()

                # Bring to front using JavaScript
                self.driver.execute_script("window.focus();")

                # Switch to window (ensure it's active)
                self.driver.switch_to.window(self.driver.current_window_handle)

                logger.info("[Upload] ✓ Browser window activated")

            except Exception as e:
                logger.warning("[Upload] ⚠ Window activation failed: %s", str(e))
                # Continue anyway - not critical

            # Step 2: Dismiss any notifications/popups
            logger.info("[Upload] Step 2/3: Checking for notifications/popups...")

            dismissed_count = self.dismiss_notifications()

            if dismissed_count > 0:
                logger.info("[Upload] ✓ Dismissed %d notification(s)", dismissed_count)
            else:
                logger.info("[Upload] ✓ No notifications found (clear)")

            # Step 3: Verify window is responsive
            try:
                logger.info("[Upload] Step 3/3: Verifying window responsiveness...")

                # Try to get current URL (simple check for responsiveness)
                current_url = self.driver.current_url

                if current_url:
                    logger.info("[Upload] ✓ Window is responsive")
                else:
                    logger.warning("[Upload] ⚠ Window may not be responsive")
                    return False

            except Exception as e:
                logger.error("[Upload] ✗ Window responsiveness check failed: %s", str(e))
                return False

            logger.info("[Upload] ═══════════════════════════════════════════")
            logger.info("[Upload] ✓ WINDOW READY - Proceeding with %s", operation_name)
            logger.info("[Upload] ═══════════════════════════════════════════")

            return True

        except Exception as e:
            logger.error("[Upload] ensure_window_ready() failed: %s", str(e))
            return False

    def navigate_to_bookmark(self, bookmark: Dict[str, str]) -> bool:
        """
        Navigate to bookmark URL.

        Args:
            bookmark: Dict with 'title' and 'url' keys

        Returns:
            True if navigation successful
        """
        try:
            url = bookmark['url']
            title = bookmark['title']

            logger.info("[Upload] ═══════════════════════════════════════════")
            logger.info("[Upload] Opening bookmark: %s", title)
            logger.info("[Upload]   URL: %s", url)

            self.driver.get(url)
            time.sleep(5)  # Wait for page load (increased to 5 seconds)

            # Verify loaded
            if "facebook.com" not in self.driver.current_url:
                logger.error("[Upload] ✗ Failed to load Facebook page")
                return False

            logger.info("[Upload] ✓ Page loaded successfully")

            # IMPORTANT: Bring browser to front after navigation (keep visible)
            try:
                self.driver.maximize_window()
                self.driver.execute_script("window.focus(); window.scrollTo(0, 0);")
                logger.info("[Upload] ✓ Browser window focused and maximized")
            except:
                pass

            # Debug: See what's on the page
            self.debug_page_content(title)

            # Priority 2: Dismiss any notifications/popups after page load
            self.dismiss_notifications()

            return True

        except Exception as e:
            logger.error("[Upload] Navigation failed: %s", str(e))
            return False

    def debug_page_content(self, bookmark_name: str) -> None:
        """Debug helper to see what's on the page."""
        try:
            # Get all clickable elements (buttons, divs with role=button, etc)
            all_buttons = self.driver.find_elements(By.XPATH, "//button")
            all_divs_button = self.driver.find_elements(By.XPATH, "//div[@role='button']")
            all_clickable = self.driver.find_elements(By.XPATH, "//*[@onclick or @role='button']")

            logger.info("[Upload] DEBUG: Found %d <button> tags", len(all_buttons))
            logger.info("[Upload] DEBUG: Found %d <div role='button'> elements", len(all_divs_button))
            logger.info("[Upload] DEBUG: Found %d total clickable elements", len(all_clickable))

            # Show first 15 clickable elements
            for idx, elem in enumerate(all_clickable[:15], 1):
                try:
                    tag = elem.tag_name
                    text = elem.text[:50] if elem.text else "(no text)"
                    aria_label = elem.get_attribute("aria-label")
                    aria_label = aria_label[:50] if aria_label else "(no aria-label)"
                    role = elem.get_attribute("role") or "(no role)"
                    logger.info("[Upload] DEBUG: Element %d - Tag: %s, Role: %s, Text: '%s', Aria: '%s'",
                               idx, tag, role, text, aria_label)
                except:
                    pass

            # Take screenshot
            screenshot_path = f"/tmp/debug_{bookmark_name.replace(' ', '_')}.png"
            self.driver.save_screenshot(screenshot_path)
            logger.info("[Upload] DEBUG: Screenshot saved to %s", screenshot_path)

            # Save page source
            source_path = f"/tmp/debug_{bookmark_name.replace(' ', '_')}.html"
            with open(source_path, 'w', encoding='utf-8') as f:
                f.write(self.driver.page_source)
            logger.info("[Upload] DEBUG: Page source saved to %s", source_path)

        except Exception as e:
            logger.error("[Upload] DEBUG: Failed - %s", str(e))

    def dismiss_notifications(self) -> int:
        """
        Priority 2: Detect and dismiss any Facebook notifications/popups.

        Returns:
            Number of notifications/popups dismissed
        """
        try:
            from .config.upload_config import NOTIFICATION_CONFIG

            # Check if active dismissal is enabled
            if not NOTIFICATION_CONFIG.get('active_dismissal_enabled', True):
                return 0

            dismiss_patterns = NOTIFICATION_CONFIG.get('dismiss_patterns', [])
            dismissed_count = 0

            for pattern in dismiss_patterns:
                try:
                    elements = self.driver.find_elements(By.XPATH, pattern)
                    for elem in elements:
                        try:
                            # Check if element is visible
                            if elem.is_displayed():
                                # Try to click it
                                elem.click()
                                dismissed_count += 1
                                logger.info("[Upload] ✓ Dismissed notification/popup (pattern: %s...)", pattern[:50])
                                time.sleep(0.3)  # Brief pause after dismissal
                        except:
                            # Element might have disappeared or not clickable
                            pass
                except:
                    # Pattern might not match anything - that's OK
                    pass

            if dismissed_count > 0:
                logger.info("[Upload] ✓ Total notifications dismissed: %d", dismissed_count)

            return dismissed_count

        except Exception as e:
            logger.debug("[Upload] Notification dismissal error: %s", str(e))
            return 0

    def find_add_videos_button_text(self, retries: int = 3) -> Optional[Any]:
        """
        Find 'Add Videos' button using text-based detection.
        Checks buttons, divs, spans, and all clickable elements.

        Args:
            retries: Number of retry attempts

        Returns:
            WebElement or None
        """
        logger.info("[Upload] Looking for 'Add Videos' button (text-based detection)...")

        for attempt in range(1, retries + 1):
            try:
                if attempt > 1:
                    logger.info("[Upload] Retry %d/%d (searching with star animation...)", attempt, retries)
                    self.idle_mouse_activity(duration=2.0, base_radius=90)

                # Method 1: ANY element containing "Add Videos" text (divs, spans, buttons, etc)
                try:
                    elements = self.driver.find_elements(By.XPATH,
                        "//*[contains(text(), 'Add Videos') or contains(text(), 'Add videos')]")
                    if elements:
                        logger.info("[Upload] ✓ Found button (broad text search) - %d match(es)", len(elements))
                        # Return the first visible element
                        for elem in elements:
                            if elem.is_displayed():
                                logger.info("[Upload]   Using element: tag=%s", elem.tag_name)
                                return elem
                except Exception as e:
                    logger.debug("[Upload] Broad text search failed: %s", str(e))

                # Method 2: Divs with role=button containing text
                try:
                    elements = self.driver.find_elements(By.XPATH,
                        "//div[@role='button' and contains(., 'Add Videos')]")
                    if elements:
                        logger.info("[Upload] ✓ Found button (div role=button)")
                        return elements[0]
                except Exception as e:
                    logger.debug("[Upload] Div role=button search failed: %s", str(e))

                # Method 3: Spans containing text
                try:
                    elements = self.driver.find_elements(By.XPATH,
                        "//span[contains(text(), 'Add Videos')]")
                    if elements:
                        # Get the parent element (likely the clickable container)
                        parent = elements[0].find_element(By.XPATH, "..")
                        logger.info("[Upload] ✓ Found button (span parent)")
                        return parent
                except Exception as e:
                    logger.debug("[Upload] Span search failed: %s", str(e))

                # Method 4: Case-insensitive search
                try:
                    elements = self.driver.find_elements(By.XPATH,
                        "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'add videos')]")
                    if elements:
                        logger.info("[Upload] ✓ Found button (case-insensitive)")
                        for elem in elements:
                            if elem.is_displayed():
                                return elem
                except Exception as e:
                    logger.debug("[Upload] Case-insensitive search failed: %s", str(e))

                # Method 5: Aria-label search
                try:
                    elements = self.driver.find_elements(By.XPATH,
                        "//*[contains(@aria-label, 'Add Videos') or contains(@aria-label, 'Add videos')]")
                    if elements:
                        logger.info("[Upload] ✓ Found button (aria-label)")
                        return elements[0]
                except Exception as e:
                    logger.debug("[Upload] Aria-label search failed: %s", str(e))

                logger.warning("[Upload] Button not found in attempt %d", attempt)

            except Exception as e:
                logger.debug("[Upload] Search error: %s", str(e))

        logger.warning("[Upload] ✗ Text-based detection failed after %d retries", retries)
        return None

    def find_add_videos_button_image(self, retries: int = 3) -> Optional[Tuple[int, int]]:
        """
        Find 'Add Videos' button using image recognition.
        Prioritizes middle-screen button (90% important).

        Args:
            retries: Number of retry attempts

        Returns:
            (x, y) coordinates of button center or None
        """
        logger.info("[Upload] Looking for 'Add Videos' button (image recognition)...")

        # Check if image file exists
        if not os.path.exists(ADD_VIDEOS_BUTTON_IMAGE):
            logger.error("[Upload] ✗ Button image not found: %s", ADD_VIDEOS_BUTTON_IMAGE)
            return None

        # Get screen dimensions
        screen_width, screen_height = pyautogui.size()
        middle_y_min = int(screen_height * 0.30)  # 30% from top
        middle_y_max = int(screen_height * 0.70)  # 70% from top

        logger.info("[Upload] Screen size: %dx%d", screen_width, screen_height)
        logger.info("[Upload] Middle screen range: y=%d to y=%d", middle_y_min, middle_y_max)

        for attempt in range(1, retries + 1):
            try:
                if attempt > 1:
                    logger.info("[Upload] Retry %d/%d (searching with star animation...)", attempt, retries)
                    self.idle_mouse_activity(duration=2.0, base_radius=90)

                # Find all matches on screen
                logger.info("[Upload] Searching for button image...")
                matches = list(pyautogui.locateAllOnScreen(
                    ADD_VIDEOS_BUTTON_IMAGE,
                    confidence=0.8
                ))

                if not matches:
                    logger.warning("[Upload] No button matches found in attempt %d", attempt)
                    continue

                logger.info("[Upload] Found %d button match(es)", len(matches))

                # Filter for middle-screen buttons
                middle_buttons = []
                for idx, match in enumerate(matches, 1):
                    center_x = match.left + match.width // 2
                    center_y = match.top + match.height // 2

                    is_middle = middle_y_min <= center_y <= middle_y_max
                    logger.info("[Upload]   Match %d: x=%d, y=%d (middle=%s)",
                               idx, center_x, center_y, "YES" if is_middle else "NO")

                    if is_middle:
                        middle_buttons.append((center_x, center_y))

                # Prioritize middle-screen button (90% important)
                if middle_buttons:
                    button_x, button_y = middle_buttons[0]
                    logger.info("[Upload] ✓ Found middle-screen button at (%d, %d)", button_x, button_y)
                    return (button_x, button_y)

                # Fallback: use first match if no middle button found
                if matches:
                    match = matches[0]
                    button_x = match.left + match.width // 2
                    button_y = match.top + match.height // 2
                    logger.warning("[Upload] ⚠ No middle button, using first match at (%d, %d)",
                                 button_x, button_y)
                    return (button_x, button_y)

            except Exception as e:
                logger.error("[Upload] Image search error: %s", str(e))

        logger.error("[Upload] ✗ Add Videos button not found after %d retries", retries)
        return None

    def find_add_videos_button(self, retries: int = 3):
        """
        Find 'Add Videos' button using multiple detection methods.
        Tries text-based detection first, then falls back to image recognition.

        Args:
            retries: Number of retry attempts

        Returns:
            WebElement (text-based) or (x, y) coordinates tuple (image-based) or None
        """
        # Try text-based detection first (faster and more reliable if it works)
        logger.info("[Upload] Attempting text-based button detection...")
        text_result = self.find_add_videos_button_text(retries=2)
        if text_result:
            logger.info("[Upload] ✓ Text-based detection successful")
            return text_result

        # Fallback to image recognition
        logger.info("[Upload] Text-based detection failed, trying image recognition...")
        image_result = self.find_add_videos_button_image(retries=retries)
        if image_result:
            logger.info("[Upload] ✓ Image recognition successful")
            return image_result

        logger.error("[Upload] ✗ All detection methods failed")
        return None

    def get_first_video_from_folder(self, folder_path: str) -> Optional[str]:
        """
        Get first video file from folder.

        Args:
            folder_path: Path to creator folder

        Returns:
            Full path to video file or None
        """
        try:
            logger.info("[Upload] Searching for videos in: %s", folder_path)

            if not os.path.exists(folder_path):
                logger.error("[Upload] ✗ Folder not found: %s", folder_path)
                return None

            # Supported video formats
            video_extensions = ['*.mp4', '*.mov', '*.avi', '*.mkv', '*.wmv', '*.MP4', '*.MOV']

            videos = []
            for ext in video_extensions:
                pattern = os.path.join(folder_path, ext)
                videos.extend(glob.glob(pattern))

            if not videos:
                logger.error("[Upload] ✗ No videos found in folder")
                return None

            # Sort and get first
            videos.sort()
            first_video = videos[0]

            logger.info("[Upload] ✓ Found video: %s", os.path.basename(first_video))
            logger.info("[Upload]   Size: %.2f MB", os.path.getsize(first_video) / (1024 * 1024))

            return first_video

        except Exception as e:
            logger.error("[Upload] Error finding video: %s", str(e))
            return None

    def move_video_to_uploaded_folder(self, video_file: str, creator_folder: str) -> bool:
        """
        Move uploaded video to 'uploaded videos' subfolder to prevent duplicate uploads.

        Args:
            video_file: Full path to the uploaded video file
            creator_folder: Path to the creator's main folder

        Returns:
            True if moved successfully, False otherwise
        """
        try:
            logger.info("[Upload] ═══════════════════════════════════════════")
            logger.info("[Upload] Moving Video to 'Uploaded' Folder")
            logger.info("[Upload] ═══════════════════════════════════════════")

            # Check if video file exists
            if not os.path.exists(video_file):
                logger.error("[Upload] ✗ Video file not found: %s", video_file)
                return False

            # Create 'uploaded videos' subfolder path
            uploaded_folder = os.path.join(creator_folder, "uploaded videos")

            # Create folder if it doesn't exist
            if not os.path.exists(uploaded_folder):
                os.makedirs(uploaded_folder)
                logger.info("[Upload] ✓ Created 'uploaded videos' folder: %s", uploaded_folder)
            else:
                logger.info("[Upload] 'uploaded videos' folder exists: %s", uploaded_folder)

            # Get video filename
            video_filename = os.path.basename(video_file)

            # Destination path
            destination = os.path.join(uploaded_folder, video_filename)

            # Check if file already exists at destination
            if os.path.exists(destination):
                logger.warning("[Upload] ⚠ File already exists at destination, adding timestamp")
                # Add timestamp to avoid overwrite
                name, ext = os.path.splitext(video_filename)
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                video_filename = f"{name}_{timestamp}{ext}"
                destination = os.path.join(uploaded_folder, video_filename)

            # Move the file (cut operation)
            shutil.move(video_file, destination)

            logger.info("[Upload] ✓ Video moved successfully!")
            logger.info("[Upload]   From: %s", video_file)
            logger.info("[Upload]   To: %s", destination)
            logger.info("[Upload] ═══════════════════════════════════════════")

            return True

        except Exception as e:
            logger.error("[Upload] ✗ Failed to move video: %s", str(e))
            logger.error("[Upload]   Video: %s", video_file)
            logger.error("[Upload]   Destination: %s", creator_folder)
            return False

    def upload_video_file(self, video_path: str) -> bool:
        """
        Upload video via file input element WITHOUT opening file dialog.
        Uses direct file path injection to avoid UI dialog.

        Args:
            video_path: Full path to video file

        Returns:
            True if upload initiated
        """
        try:
            logger.info("[Upload] ═══════════════════════════════════════════")
            logger.info("[Upload] Uploading Video File (NO DIALOG)")
            logger.info("[Upload] ═══════════════════════════════════════════")
            logger.info("[Upload] File: %s", video_path)

            # Verify file exists
            if not os.path.exists(video_path):
                logger.error("[Upload] ✗ File not found: %s", video_path)
                return False

            logger.info("[Upload] ✓ File exists (%.2f MB)",
                       os.path.getsize(video_path) / (1024 * 1024))

            # Find file input elements (usually hidden)
            file_inputs = self.driver.find_elements(By.XPATH, "//input[@type='file']")

            if not file_inputs:
                logger.error("[Upload] ✗ File input element not found")
                return False

            logger.info("[Upload] ✓ Found %d file input(s)", len(file_inputs))

            # Use first visible or first available input
            file_input = None
            for idx, inp in enumerate(file_inputs, 1):
                try:
                    # Don't check visibility - file inputs are often hidden
                    file_input = inp
                    logger.info("[Upload] Using file input #%d", idx)
                    break
                except:
                    continue

            if not file_input:
                logger.error("[Upload] ✗ No usable file input found")
                return False

            # CRITICAL: Send file path DIRECTLY without clicking (avoids dialog)
            logger.info("[Upload] Injecting file path directly (bypassing dialog)...")

            # Method 1: Direct send_keys (should NOT open dialog)
            try:
                # Make sure element is NOT clicked first
                logger.info("[Upload] Method 1: Using send_keys (direct injection)...")
                file_input.send_keys(video_path)
                logger.info("[Upload] ✓ File path injected successfully")
            except Exception as e:
                logger.warning("[Upload] Direct send_keys failed: %s", str(e))

                # Method 2: JavaScript injection (absolutely no dialog)
                logger.info("[Upload] Method 2: Using JavaScript injection...")
                try:
                    # Create a DataTransfer object with the file
                    js_script = """
                    var input = arguments[0];
                    var filePath = arguments[1];

                    // Set the value directly (some browsers allow this)
                    try {
                        input.value = filePath;
                    } catch(e) {
                        console.log('Could not set value directly:', e);
                    }

                    // Trigger change event
                    var event = new Event('change', { bubbles: true });
                    input.dispatchEvent(event);

                    return true;
                    """

                    self.driver.execute_script(js_script, file_input, video_path)
                    logger.info("[Upload] ✓ JavaScript injection completed")
                except Exception as js_error:
                    logger.error("[Upload] JavaScript injection failed: %s", str(js_error))
                    raise

            # Keep browser window focused (prevent any popups from stealing focus)
            try:
                self.driver.execute_script("window.focus();")
            except:
                pass

            # Wait for upload to start with star animation
            logger.info("[Upload] Waiting for upload to initialize (with star animation)...")
            self.idle_mouse_activity(duration=3.0, base_radius=85)

            logger.info("[Upload] ═══════════════════════════════════════════")
            logger.info("[Upload] ✓ File Upload Initiated (No Dialog Shown)")
            logger.info("[Upload] ═══════════════════════════════════════════")
            return True

        except Exception as e:
            logger.error("[Upload] ═══════════════════════════════════════════")
            logger.error("[Upload] ✗ File Upload FAILED")
            logger.error("[Upload]   Error: %s", str(e))
            logger.error("[Upload] ═══════════════════════════════════════════")
            import traceback
            logger.error("[Upload] Traceback: %s", traceback.format_exc())
            return False

    def _clear_field_with_human_behavior(self, field) -> bool:
        """
        Clear field using human-like behavior.
        Tries multiple methods: click + select all + delete.

        Args:
            field: WebElement to clear

        Returns:
            True if cleared successfully
        """
        try:
            # Method 1: Triple click to select all text (human-like)
            logger.info("[Upload] Clearing field with triple-click...")
            actions = ActionChains(self.driver)

            # Move to field and triple-click
            actions.move_to_element(field).click().click().click().perform()
            time.sleep(0.3)  # Brief pause

            # Press Delete
            field.send_keys(Keys.DELETE)
            time.sleep(0.2)

            # Verify cleared
            remaining = field.get_attribute("value") or ""
            if not remaining:
                logger.info("[Upload] ✓ Field cleared successfully (triple-click)")
                return True

        except Exception as e:
            logger.debug("[Upload] Triple-click clear failed: %s", str(e))

        try:
            # Method 2: Click + Ctrl+A + Delete
            logger.info("[Upload] Trying Ctrl+A method...")
            field.click()
            time.sleep(0.2)

            # Select all
            field.send_keys(Keys.CONTROL + "a")
            time.sleep(0.2)

            # Delete
            field.send_keys(Keys.DELETE)
            time.sleep(0.2)

            # Verify cleared
            remaining = field.get_attribute("value") or ""
            if not remaining:
                logger.info("[Upload] ✓ Field cleared successfully (Ctrl+A)")
                return True

        except Exception as e:
            logger.debug("[Upload] Ctrl+A clear failed: %s", str(e))

        try:
            # Method 3: Selenium's clear() as last resort
            logger.info("[Upload] Trying Selenium clear()...")
            field.clear()
            time.sleep(0.2)

            remaining = field.get_attribute("value") or ""
            if not remaining:
                logger.info("[Upload] ✓ Field cleared successfully (Selenium)")
                return True

        except Exception as e:
            logger.debug("[Upload] Selenium clear failed: %s", str(e))

        logger.warning("[Upload] ⚠ Could not clear field completely")
        return False

    def _type_with_human_behavior(self, field, text: str) -> bool:
        """
        Type text with human-like behavior (random delays between keystrokes).
        Supports emojis and special characters via clipboard paste fallback.

        Args:
            field: WebElement to type into
            text: Text to type

        Returns:
            True if typed successfully
        """
        try:
            logger.info("[Upload] Typing with human behavior: '%s'", text)

            # Method 1: Try character-by-character typing (works for ASCII)
            typing_success = False
            try:
                for char in text:
                    field.send_keys(char)
                    # Random delay between 50-150ms (realistic typing speed)
                    delay = random.uniform(0.05, 0.15)
                    time.sleep(delay)

                # Brief pause after typing
                time.sleep(0.3)

                # Verify text was entered
                entered_text = field.get_attribute("value") or ""
                if text in entered_text:
                    logger.info("[Upload] ✓ Text typed successfully (character-by-character)")
                    typing_success = True
                else:
                    logger.warning("[Upload] ⚠ Character typing verification failed")
                    typing_success = False

            except Exception as e:
                logger.warning("[Upload] Character typing failed (probably emojis/unicode): %s", str(e))
                typing_success = False

            # Method 2: Fallback to clipboard paste (works for emojis/special characters)
            if not typing_success:
                logger.info("[Upload] Attempting clipboard paste fallback...")
                try:
                    # Copy text to clipboard
                    pyperclip.copy(text)
                    time.sleep(0.2)

                    # Click field to focus
                    field.click()
                    time.sleep(0.2)

                    # Paste using Ctrl+V
                    field.send_keys(Keys.CONTROL + 'v')
                    time.sleep(0.5)

                    # Verify pasted text
                    entered_text = field.get_attribute("value") or ""
                    if text in entered_text:
                        logger.info("[Upload] ✓ Text pasted successfully (clipboard method)")
                        return True
                    else:
                        logger.warning("[Upload] ⚠ Paste verification failed. Expected: '%s', Got: '%s'",
                                     text, entered_text)
                        return False

                except Exception as paste_error:
                    logger.error("[Upload] Clipboard paste failed: %s", str(paste_error))
                    return False
            else:
                return True

        except Exception as e:
            logger.error("[Upload] All typing methods failed: %s", str(e))
            return False

    def set_video_title(self, title: str, retries: int = 3) -> bool:
        """
        Set video title in appropriate field with improved detection and human-like behavior.
        Uses proper Selenium syntax with explicit waits.

        Args:
            title: Video title to set
            retries: Number of retry attempts

        Returns:
            True if title was set
        """
        logger.info("[Upload] ═══════════════════════════════════════════")
        logger.info("[Upload] Setting Video Title")
        logger.info("[Upload] ═══════════════════════════════════════════")
        logger.info("[Upload] Title: %s", title)

        for attempt in range(1, retries + 1):
            try:
                if attempt > 1:
                    logger.info("[Upload] Retry attempt %d/%d", attempt, retries)
                    time.sleep(1)

                # Minimal wait - upload interface should be ready
                logger.info("[Upload] Looking for title field...")
                time.sleep(0.5)  # Just 0.5 seconds - field should be visible now

                # Enhanced title field selectors (prioritized order) - PROPER SELENIUM SYNTAX
                title_selectors = [
                    # Method 1: Specific Reel title placeholder (EXACT match from inspect element)
                    ("//input[@placeholder='Add a title to your reel']", "Reel title placeholder (exact)"),

                    # Method 2: Case variations of reel title
                    ("//input[contains(@placeholder, 'Add a title')]", "Reel title (contains)"),
                    ("//input[contains(@placeholder, 'title to your reel')]", "Reel title (partial)"),

                    # Method 3: Generic title placeholder
                    ("//input[@placeholder='Title']", "Generic title placeholder"),

                    # Method 4: Contains 'title' in placeholder (case-insensitive)
                    ("//input[contains(translate(@placeholder, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'title')]", "Title (case-insensitive)"),

                    # Method 5: Title aria-label
                    ("//input[contains(@aria-label, 'Title') or contains(@aria-label, 'title')]", "Title aria-label"),

                    # Method 6: Input with name='title'
                    ("//input[@name='title']", "Title name attribute"),

                    # Method 7: Any text input in upload form
                    ("//input[@type='text']", "Any text input"),
                ]

                # DEBUG: Show all input fields on page
                logger.info("[Upload] DEBUG: Searching for ALL input fields on page...")
                try:
                    all_inputs = self.driver.find_elements(By.XPATH, "//input | //textarea")
                    logger.info("[Upload] DEBUG: Found %d total input/textarea fields", len(all_inputs))

                    for idx, inp in enumerate(all_inputs[:10], 1):  # Show first 10
                        try:
                            if inp.is_displayed():
                                tag = inp.tag_name
                                placeholder = inp.get_attribute("placeholder") or "(none)"
                                aria_label = inp.get_attribute("aria-label") or "(none)"
                                inp_type = inp.get_attribute("type") or "(none)"
                                logger.info("[Upload] DEBUG: Field %d - <%s type='%s'> placeholder='%s' aria-label='%s'",
                                          idx, tag, inp_type, placeholder[:50], aria_label[:50])
                        except:
                            pass
                except Exception as e:
                    logger.debug("[Upload] DEBUG: Could not list all fields - %s", str(e))

                # Try each selector with PROPER SELENIUM SYNTAX
                for selector, selector_name in title_selectors:
                    try:
                        logger.info("[Upload] ───────────────────────────────────────────")
                        logger.info("[Upload] Trying: %s", selector_name)
                        logger.info("[Upload] XPath: %s", selector)

                        # FIXED: Use By.XPATH (proper Selenium syntax)
                        fields = self.driver.find_elements(By.XPATH, selector)

                        if not fields:
                            logger.info("[Upload] ✗ No fields found with this selector")
                            continue

                        logger.info("[Upload] ✓ Found %d field(s)", len(fields))

                        # Try each field found
                        for field_idx, field in enumerate(fields, 1):
                            try:
                                logger.info("[Upload] Testing field %d/%d...", field_idx, len(fields))

                                # Check visibility
                                is_visible = field.is_displayed()
                                logger.info("[Upload]   Visible: %s", "YES" if is_visible else "NO")

                                if not is_visible:
                                    logger.info("[Upload]   Skipping invisible field")
                                    continue

                                # Get field details
                                tag = field.tag_name
                                placeholder = field.get_attribute("placeholder") or "(none)"
                                aria_label = field.get_attribute("aria-label") or "(none)"
                                existing = field.get_attribute("value") or ""

                                logger.info("[Upload]   Tag: %s", tag)
                                logger.info("[Upload]   Placeholder: %s", placeholder)
                                logger.info("[Upload]   Aria-label: %s", aria_label)
                                logger.info("[Upload]   Current value: %s", existing if existing else "(empty)")

                                # Scroll field into view
                                logger.info("[Upload]   Scrolling into view...")
                                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", field)
                                time.sleep(0.5)

                                # Highlight field for debugging (temporary yellow border)
                                try:
                                    original_style = field.get_attribute("style")
                                    self.driver.execute_script("arguments[0].style.border='3px solid yellow'", field)
                                    time.sleep(0.5)
                                    logger.info("[Upload]   ✓ Field highlighted (yellow border)")
                                except:
                                    pass

                                # Clear existing text if present
                                if existing:
                                    logger.info("[Upload]   Clearing existing text: '%s'", existing)
                                    if not self._clear_field_with_human_behavior(field):
                                        logger.warning("[Upload]   Clear failed, trying next field...")
                                        continue

                                # Type title with human behavior
                                logger.info("[Upload]   Typing title...")
                                if self._type_with_human_behavior(field, title):
                                    logger.info("[Upload] ═══════════════════════════════════════════")
                                    logger.info("[Upload] ✓✓✓ SUCCESS: Title Set! ✓✓✓")
                                    logger.info("[Upload]   Method: %s", selector_name)
                                    logger.info("[Upload]   " \
                                    ": %s", selector)
                                    logger.info("[Upload]   Title: %s", title)
                                    logger.info("[Upload] ═══════════════════════════════════════════")

                                    # Remove highlight
                                    try:
                                        self.driver.execute_script("arguments[0].style.border=''", field)
                                    except:
                                        pass

                                    return True
                                else:
                                    logger.warning("[Upload]   Typing failed, trying next field...")
                                    continue

                            except Exception as e:
                                logger.warning("[Upload]   Field interaction error: %s", str(e))
                                continue

                    except Exception as e:
                        logger.warning("[Upload] Selector '%s' error: %s", selector_name, str(e))
                        continue

                # Method 8: Description field (fallback for Reels)
                logger.info("[Upload] ═══════════════════════════════════════════")
                logger.info("[Upload] Title fields failed, trying DESCRIPTION field...")
                logger.info("[Upload] ═══════════════════════════════════════════")

                try:
                    desc_selectors = [
                        "//textarea[@placeholder='Describe your reel...']",
                        "//textarea[contains(@placeholder, 'Describe your reel')]",
                        "//textarea[contains(@placeholder, 'describe your reel')]",
                        "//textarea[contains(@placeholder, 'Describe')]",
                        "//textarea",  # Any textarea as last resort
                    ]

                    for desc_selector in desc_selectors:
                        logger.info("[Upload] Trying description: %s", desc_selector)
                        desc_fields = self.driver.find_elements(By.XPATH, desc_selector)

                        if desc_fields:
                            logger.info("[Upload] ✓ Found %d description field(s)", len(desc_fields))

                            for field in desc_fields:
                                try:
                                    if field.is_displayed():
                                        placeholder = field.get_attribute("placeholder") or "(none)"
                                        logger.info("[Upload] ✓ Found visible description field")
                                        logger.info("[Upload]   Placeholder: %s", placeholder)

                                        # Scroll into view
                                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", field)
                                        time.sleep(0.5)

                                        # Clear and type
                                        field.click()
                                        time.sleep(0.3)

                                        existing = field.get_attribute("value") or field.text or ""
                                        if existing:
                                            self._clear_field_with_human_behavior(field)

                                        if self._type_with_human_behavior(field, title):
                                            logger.info("[Upload] ✓ Title set in description field (fallback)")
                                            return True
                                except:
                                    continue

                except Exception as e:
                    logger.warning("[Upload] Description field error: %s", str(e))

                logger.warning("[Upload] ═══════════════════════════════════════════")
                logger.warning("[Upload] Attempt %d/%d FAILED - No suitable field found", attempt, retries)
                logger.warning("[Upload] ═══════════════════════════════════════════")

            except Exception as e:
                logger.error("[Upload] Attempt %d error: %s", attempt, str(e))
                import traceback
                logger.error("[Upload] Traceback: %s", traceback.format_exc())

        logger.error("[Upload] ═══════════════════════════════════════════")
        logger.error("[Upload] ✗✗✗ FAILED: Could not set title after %d attempts", retries)
        logger.error("[Upload] ═══════════════════════════════════════════")
        return False

    def monitor_upload_progress(self) -> bool:
        """
        Monitor upload progress until 100% complete.
        Enhanced with extensive logging and multiple fallback methods.

        Returns:
            True if upload completed successfully
        """
        logger.info("[Upload] Monitoring upload progress...")

        start_time = time.time()
        last_progress = 0
        stuck_count = 0
        max_stuck_iterations = 10  # Alert if stuck for 50 seconds (10 * 5s)

        while (time.time() - start_time) < self.upload_timeout:
            try:
                # Method 1: Progress bar with role="progressbar"
                logger.debug("[Upload] Looking for progress bars...")
                progress_bars = self.driver.find_elements(By.XPATH, "//*[@role='progressbar']")

                logger.info("[Upload] Found %d element(s) with role='progressbar'", len(progress_bars))

                if progress_bars:
                    for idx, bar in enumerate(progress_bars, 1):
                        try:
                            # Check visibility
                            is_visible = bar.is_displayed()
                            logger.info("[Upload] Progress bar #%d - Visible: %s", idx, is_visible)

                            if not is_visible:
                                logger.debug("[Upload] Skipping hidden progress bar #%d", idx)
                                continue

                            # Get all ARIA attributes for debugging
                            aria_valuenow = bar.get_attribute("aria-valuenow")
                            aria_valuemin = bar.get_attribute("aria-valuemin")
                            aria_valuemax = bar.get_attribute("aria-valuemax")

                            logger.info("[Upload] Progress bar #%d attributes:", idx)
                            logger.info("[Upload]   aria-valuenow: '%s'", aria_valuenow)
                            logger.info("[Upload]   aria-valuemin: '%s'", aria_valuemin)
                            logger.info("[Upload]   aria-valuemax: '%s'", aria_valuemax)

                            # Method 1A: Try aria-valuenow attribute
                            if aria_valuenow:
                                try:
                                    progress = int(float(aria_valuenow))
                                    logger.info("[Upload] ✓ Got progress from aria-valuenow: %d%%", progress)

                                    if progress != last_progress:
                                        logger.info("[Upload] Progress: %d%%", progress)
                                        last_progress = progress
                                        stuck_count = 0  # Reset stuck counter

                                        # Phase 2: Save progress to state
                                        self.state_manager.update_current_upload(progress=progress)

                                    if progress >= 100:
                                        logger.info("[Upload] ✓ Upload 100% complete!")
                                        # Phase 2: Update state to 100%
                                        self.state_manager.update_current_upload(progress=100, status="completed")
                                        return True

                                    # Successfully got progress, continue monitoring
                                    break  # Exit bar loop, wait and check again

                                except Exception as parse_error:
                                    logger.warning("[Upload] ⚠ Failed to parse aria-valuenow '%s': %s",
                                                 aria_valuenow, str(parse_error))

                            else:
                                logger.warning("[Upload] ⚠ Progress bar #%d has NO aria-valuenow attribute!", idx)

                            # Method 1B: Fallback - Find percentage text INSIDE progress bar
                            logger.info("[Upload] Trying fallback: looking for %% text inside progress bar #%d", idx)
                            try:
                                # Find span elements inside this progress bar
                                inner_spans = bar.find_elements(By.XPATH, ".//span")
                                logger.info("[Upload] Found %d span(s) inside progress bar #%d", len(inner_spans), idx)

                                for span_idx, span in enumerate(inner_spans, 1):
                                    span_text = span.text.strip()
                                    logger.debug("[Upload] Span #%d text: '%s'", span_idx, span_text)

                                    if "%" in span_text:
                                        try:
                                            # Extract number (e.g., "5%" -> 5)
                                            progress_str = span_text.replace("%", "").strip()
                                            progress = int(float(progress_str))

                                            logger.info("[Upload] ✓ Got progress from inner span text: %d%%", progress)

                                            if progress != last_progress:
                                                logger.info("[Upload] Progress: %d%%", progress)
                                                last_progress = progress
                                                stuck_count = 0

                                                # Phase 2: Save progress to state
                                                self.state_manager.update_current_upload(progress=progress)

                                            if progress >= 100:
                                                logger.info("[Upload] ✓ Upload 100% complete!")
                                                # Phase 2: Update state to 100%
                                                self.state_manager.update_current_upload(progress=100, status="completed")
                                                return True

                                            # Successfully got progress
                                            break

                                        except Exception as span_parse_error:
                                            logger.debug("[Upload] Failed to parse span text '%s': %s",
                                                       span_text, str(span_parse_error))

                            except Exception as inner_error:
                                logger.debug("[Upload] Inner span search failed: %s", str(inner_error))

                        except Exception as bar_error:
                            logger.warning("[Upload] Error processing progress bar #%d: %s", idx, str(bar_error))
                            continue

                # Method 2: Text-based percentage anywhere on page (broader search)
                logger.debug("[Upload] Method 2: Searching for percentage text on page...")
                progress_texts = self.driver.find_elements(By.XPATH, "//*[contains(text(), '%')]")

                logger.debug("[Upload] Found %d element(s) with %% symbol", len(progress_texts))

                for text_elem in progress_texts:
                    text = text_elem.text.strip()
                    if "%" in text and text_elem.is_displayed():
                        try:
                            # Extract number before % (handle "Uploading: 95%" or just "95%")
                            progress_str = text.split("%")[0].strip().split()[-1]
                            progress = int(float(progress_str))

                            # Validate it's a reasonable percentage (0-100)
                            if 0 <= progress <= 100:
                                logger.info("[Upload] ✓ Got progress from page text: %d%% (text: '%s')", progress, text)

                                if progress != last_progress:
                                    logger.info("[Upload] Progress: %d%%", progress)
                                    last_progress = progress
                                    stuck_count = 0

                                    # Phase 2: Save progress to state
                                    self.state_manager.update_current_upload(progress=progress)

                                if progress >= 100:
                                    logger.info("[Upload] ✓ Upload 100% complete!")
                                    # Phase 2: Update state to 100%
                                    self.state_manager.update_current_upload(progress=100, status="completed")
                                    return True

                                break  # Got valid progress

                        except Exception as text_parse_error:
                            logger.debug("[Upload] Failed to parse text '%s': %s", text, str(text_parse_error))

                # Method 3: "Complete" or "Published" indicators
                logger.debug("[Upload] Method 3: Checking for completion indicators...")
                complete_indicators = self.driver.find_elements(By.XPATH,
                    "//*[contains(text(), 'Complete') or contains(text(), 'Published') or contains(text(), 'Done')]")

                if complete_indicators:
                    for indicator in complete_indicators:
                        if indicator.is_displayed():
                            logger.info("[Upload] ✓ Upload completed (indicator found: '%s')!", indicator.text)
                            # Phase 2: Update state to 100%
                            self.state_manager.update_current_upload(progress=100, status="completed")
                            return True

                # Check if progress is stuck
                if last_progress > 0:
                    stuck_count += 1
                    if stuck_count >= max_stuck_iterations:
                        logger.warning("[Upload] ⚠ Progress stuck at %d%% for %d seconds",
                                     last_progress, stuck_count * 5)
                        stuck_count = 0  # Reset to avoid spam

            except Exception as e:
                logger.warning("[Upload] Progress check error: %s", str(e))
                import traceback
                logger.debug("[Upload] Traceback: %s", traceback.format_exc())

            # Wait before next check with star movement (shows bot is active)
            logger.debug("[Upload] Waiting 5 seconds before next check (with star animation)...")
            self.idle_mouse_activity(duration=5.0, base_radius=80)

        # Timeout reached
        elapsed = time.time() - start_time
        logger.error("[Upload] ✗ Upload timeout after %.0f seconds (limit: %d seconds)",
                    elapsed, self.upload_timeout)
        logger.error("[Upload]   Last detected progress: %d%%", last_progress)
        return False

    def find_publish_button(self) -> Optional[Any]:
        """
        Find publish button using multiple detection methods.

        Returns:
            WebElement if found, None otherwise
        """
        logger.info("[Upload] ═══════════════════════════════════════════")
        logger.info("[Upload] Searching for Publish Button")
        logger.info("[Upload] ═══════════════════════════════════════════")

        # Method 1: Exact text match "Publish" (most reliable for div with text)
        try:
            logger.info("[Upload] Method 1: Exact text 'Publish'")
            buttons = self.driver.find_elements(By.XPATH, "//*[text()='Publish']")

            logger.info("[Upload] Found %d element(s) with exact text 'Publish'", len(buttons))

            for idx, btn in enumerate(buttons, 1):
                try:
                    is_visible = btn.is_displayed()
                    logger.info("[Upload] Button #%d - Visible: %s", idx, is_visible)

                    if is_visible:
                        logger.info("[Upload] ✓ Found visible Publish button (Method 1)")
                        return btn
                except:
                    continue

        except Exception as e:
            logger.debug("[Upload] Method 1 failed: %s", str(e))

        # Method 2: Contains text "Publish" (case variations, partial match)
        try:
            logger.info("[Upload] Method 2: Contains text 'Publish'")
            buttons = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'Publish')]")

            logger.info("[Upload] Found %d element(s) containing 'Publish'", len(buttons))

            for idx, btn in enumerate(buttons, 1):
                try:
                    if btn.is_displayed():
                        logger.info("[Upload] ✓ Found visible Publish button (Method 2)")
                        return btn
                except:
                    continue

        except Exception as e:
            logger.debug("[Upload] Method 2 failed: %s", str(e))

        # Method 3: div/button with role and text
        try:
            logger.info("[Upload] Method 3: Role-based with text")
            selectors = [
                "//div[@role='button'][text()='Publish']",
                "//div[@role='button'][contains(text(), 'Publish')]",
                "//button[text()='Publish']",
                "//button[contains(text(), 'Publish')]",
            ]

            for selector in selectors:
                buttons = self.driver.find_elements(By.XPATH, selector)
                if buttons:
                    for btn in buttons:
                        try:
                            if btn.is_displayed():
                                logger.info("[Upload] ✓ Found visible Publish button (Method 3: %s)", selector)
                                return btn
                        except:
                            continue

        except Exception as e:
            logger.debug("[Upload] Method 3 failed: %s", str(e))

        # Method 4: Image recognition (enabled state)
        try:
            logger.info("[Upload] Method 4: Image recognition (enabled button)")

            # Take screenshot to search in
            screenshot = pyautogui.screenshot()

            # Find button using image matching
            button_location = pyautogui.locateOnScreen(
                PUBLISH_BUTTON_ENABLED_IMAGE,
                confidence=0.8
            )

            if button_location:
                logger.info("[Upload] ✓ Found Publish button via image recognition!")
                logger.info("[Upload]   Location: %s", button_location)

                # Get center coordinates
                center_x, center_y = pyautogui.center(button_location)

                # Find element at those coordinates using JavaScript
                element = self.driver.execute_script("""
                    return document.elementFromPoint(arguments[0], arguments[1]);
                """, center_x, center_y)

                if element:
                    logger.info("[Upload] ✓ Got WebElement from image coordinates")
                    return element

        except Exception as e:
            logger.debug("[Upload] Method 4 (image recognition) failed: %s", str(e))

        logger.warning("[Upload] ⚠ Publish button NOT found after trying all methods")
        return None

    def is_publish_button_enabled(self, button) -> bool:
        """
        Check if publish button is enabled (not disabled/grayed out).

        Args:
            button: WebElement of publish button

        Returns:
            True if enabled, False if disabled
        """
        try:
            # Method 1: Check aria-disabled attribute
            aria_disabled = button.get_attribute("aria-disabled")
            if aria_disabled == "true":
                logger.debug("[Upload] Button is disabled (aria-disabled='true')")
                return False

            # Method 2: Check disabled attribute
            disabled = button.get_attribute("disabled")
            if disabled:
                logger.debug("[Upload] Button is disabled (disabled attribute)")
                return False

            # Method 3: Check if button classes contain "disabled"
            button_class = button.get_attribute("class") or ""
            if "disabled" in button_class.lower():
                logger.debug("[Upload] Button appears disabled (class contains 'disabled')")
                return False

            # Method 4: Image recognition - check if it matches ENABLED state image
            try:
                # Get button location and screenshot
                location = button.location
                size = button.size

                # Use image recognition to verify enabled state
                enabled_match = pyautogui.locateOnScreen(
                    PUBLISH_BUTTON_ENABLED_IMAGE,
                    confidence=0.75
                )

                if enabled_match:
                    logger.info("[Upload] ✓ Button is ENABLED (image match confirmed)")
                    return True
                else:
                    # Try matching disabled state
                    disabled_match = pyautogui.locateOnScreen(
                        PUBLISH_BUTTON_DISABLED_IMAGE,
                        confidence=0.75
                    )

                    if disabled_match:
                        logger.debug("[Upload] Button is DISABLED (disabled image match)")
                        return False

            except Exception as img_error:
                logger.debug("[Upload] Image state check failed: %s", str(img_error))

            # Default: Assume enabled if no disabled indicators found
            logger.info("[Upload] ✓ Button appears ENABLED (no disabled indicators)")
            return True

        except Exception as e:
            logger.warning("[Upload] Error checking button state: %s", str(e))
            return False

    def hover_on_publish_button(self, button) -> bool:
        """
        Move ACTUAL physical mouse to publish button and hover for visual confirmation.
        Uses PyAutoGUI for real mouse movement (visible on screen).
        Does NOT click (production mode).

        Args:
            button: WebElement of publish button

        Returns:
            True if hover successful
        """
        try:
            logger.info("[Upload] ═══════════════════════════════════════════")
            logger.info("[Upload] Hovering on Publish Button (Physical Mouse)")
            logger.info("[Upload] ═══════════════════════════════════════════")

            # Step 1: Scroll button into view (center of screen)
            logger.info("[Upload] Scrolling button into view...")
            self.driver.execute_script("""
                arguments[0].scrollIntoView({
                    behavior: 'smooth',
                    block: 'center',
                    inline: 'center'
                });
            """, button)

            time.sleep(0.5)  # Let scroll complete and element settle

            # Step 2: Get element position relative to viewport
            logger.info("[Upload] Getting element coordinates...")
            element_rect = button.rect  # x, y, width, height

            logger.info("[Upload] Element rect: x=%s, y=%s, width=%s, height=%s",
                       element_rect['x'], element_rect['y'],
                       element_rect['width'], element_rect['height'])

            # Step 3: Get browser window position and chrome height
            try:
                # Get window position and browser chrome dimensions using JavaScript
                browser_info = self.driver.execute_script("""
                    return {
                        windowX: window.screenX,
                        windowY: window.screenY,
                        outerWidth: window.outerWidth,
                        outerHeight: window.outerHeight,
                        innerWidth: window.innerWidth,
                        innerHeight: window.innerHeight
                    };
                """)

                # Calculate browser chrome dimensions
                # Chrome width = left border + right border + scrollbar
                chrome_width = browser_info['outerWidth'] - browser_info['innerWidth']
                # Chrome height = title bar + address bar + bookmarks bar + tabs
                chrome_height = browser_info['outerHeight'] - browser_info['innerHeight']

                logger.info("[Upload] Browser window position: x=%s, y=%s",
                           browser_info['windowX'], browser_info['windowY'])
                logger.info("[Upload] Browser chrome: width=%dpx, height=%dpx",
                           chrome_width, chrome_height)

                window_pos = {
                    'x': browser_info['windowX'],
                    'y': browser_info['windowY']
                }

                # Typical browser chrome includes:
                # - Left/right borders: ~8-10px total
                # - Top: title bar + address bar + tabs + bookmarks = chrome_height
                chrome_offset_x = chrome_width // 2  # Split border width evenly
                chrome_offset_y = chrome_height  # Full chrome height at top

            except Exception as js_error:
                logger.warning("[Upload] Could not get window position via JS: %s", str(js_error))
                # Fallback: assume window is at top-left with typical chrome
                window_pos = {'x': 0, 'y': 0}
                chrome_offset_x = 8  # Default border width
                chrome_offset_y = 130  # Default chrome height (title+address+tabs)

            # Step 4: Calculate absolute screen coordinates
            # Element center point (relative to viewport)
            element_center_x = element_rect['x'] + (element_rect['width'] / 2)
            element_center_y = element_rect['y'] + (element_rect['height'] / 2)

            # Absolute screen coordinates = window position + chrome offset + element position
            screen_x = window_pos['x'] + chrome_offset_x + element_center_x
            screen_y = window_pos['y'] + chrome_offset_y + element_center_y

            logger.info("[Upload] Calculated screen coordinates: x=%d, y=%d",
                       int(screen_x), int(screen_y))
            logger.info("[Upload]   Formula: window(%d,%d) + chrome(%d,%d) + element(%d,%d)",
                       int(window_pos['x']), int(window_pos['y']),
                       int(chrome_offset_x), int(chrome_offset_y),
                       int(element_center_x), int(element_center_y))

            # Step 5: Move ACTUAL physical mouse using PyAutoGUI
            logger.info("[Upload] Moving PHYSICAL mouse to button...")

            # Get current mouse position
            current_x, current_y = pyautogui.position()
            logger.info("[Upload] Current mouse position: x=%d, y=%d", current_x, current_y)

            # Smooth movement to button (duration makes it visible)
            pyautogui.moveTo(
                int(screen_x),
                int(screen_y),
                duration=0.5  # 0.5 seconds smooth movement (very visible!)
            )

            logger.info("[Upload] ✓ Physical mouse moved to Publish button!")

            # Step 6: Hover for additional 0.5 seconds (visual confirmation)
            logger.info("[Upload] Hovering for 0.5 seconds...")
            time.sleep(0.5)

            # Step 7: Move mouse in small circle (visual emphasis)
            logger.info("[Upload] Moving mouse in small circle (visual confirmation)...")

            # Small circular motion around button (8 points)
            radius = 10  # Small 10px circle
            for angle in range(0, 360, 45):  # 45° increments = 8 points
                offset_x = int(radius * math.cos(math.radians(angle)))
                offset_y = int(radius * math.sin(math.radians(angle)))

                pyautogui.moveTo(
                    int(screen_x + offset_x),
                    int(screen_y + offset_y),
                    duration=0.05  # Fast small movements
                )

            # Return to button center
            pyautogui.moveTo(int(screen_x), int(screen_y), duration=0.1)

            logger.info("[Upload] ✓ Hover complete!")
            logger.info("[Upload] (Production mode: NOT clicking button)")
            logger.info("[Upload] ═══════════════════════════════════════════")

            # Return mouse to mid-screen after activity complete
            self.return_to_mid_screen()

            return True

        except Exception as e:
            logger.error("[Upload] Failed to hover on button: %s", str(e))
            import traceback
            logger.debug("[Upload] Traceback: %s", traceback.format_exc())
            return False

    def detect_and_hover_publish_button(self) -> bool:
        """
        Complete workflow: Find publish button, check if enabled, and hover on it.
        This is called after upload completes.

        Returns:
            True if button found and hovered, False otherwise
        """
        try:
            # Step 1: Find the button
            button = self.find_publish_button()

            if not button:
                logger.warning("[Upload] ⚠ Could not find Publish button")
                logger.warning("[Upload] Continuing to next bookmark anyway...")
                return False

            logger.info("[Upload] ✓ Publish button found!")

            # Step 2: Check if enabled
            logger.info("[Upload] Checking button state...")
            is_enabled = self.is_publish_button_enabled(button)

            if is_enabled:
                logger.info("[Upload] ✓ Publish button is ENABLED")
            else:
                logger.warning("[Upload] ⚠ Publish button is DISABLED")
                logger.warning("[Upload] (Upload might not be complete yet)")

            # Step 3: Hover on button (regardless of enabled state, for visual confirmation)
            hover_success = self.hover_on_publish_button(button)

            # Step 4: Wait for Facebook "bulk upload processing" notification
            # Facebook shows this notification after publish button appears
            # User's smart solution: Let it show, then navigate to next page (dismisses automatically)
            try:
                from .config.upload_config import NOTIFICATION_CONFIG
                post_publish_wait = NOTIFICATION_CONFIG.get('post_publish_wait', 3)

                logger.info("[Upload] ═══════════════════════════════════════════")
                logger.info("[Upload] Waiting %d seconds for Facebook notifications...", post_publish_wait)
                logger.info("[Upload] Note: 'Bulk upload processing' notification will appear")
                logger.info("[Upload] It will auto-dismiss when moving to next page")
                logger.info("[Upload] ═══════════════════════════════════════════")

                time.sleep(post_publish_wait)

                # Optional: Try to dismiss any notifications that appeared
                self.dismiss_notifications()

            except Exception as e:
                logger.debug("[Upload] Post-publish wait failed: %s", str(e))

            return hover_success

        except Exception as e:
            logger.error("[Upload] Error in detect_and_hover_publish_button: %s", str(e))
            return False

    def idle_mouse_activity(self, duration: float = 3.0, base_radius: int = 100) -> None:
        """
        Move mouse with random human-like patterns during idle/wait periods.
        Shows user that bot is active and working naturally.

        Randomly selects from 10 different movement patterns with imperfect,
        human-like behavior. Patterns may be incomplete based on duration.

        Args:
            duration: How long to animate (seconds) - patterns adapt to available time
            base_radius: Base size for patterns in pixels (randomized per pattern)
        """
        # Get screen dimensions
        screen_width, screen_height = pyautogui.size()
        center_x = screen_width // 2
        center_y = screen_height // 2

        # Define 10 movement patterns
        def shrinking_circles(dur, radius):
            """Circles from large to small (10 rounds)"""
            logger.debug("[Mouse] 🔵 Shrinking circles pattern")
            start = time.time()
            max_radius = int(radius * 1.5)  # Start big
            min_radius = int(radius * 0.2)  # End small

            for round_num in range(10):
                if time.time() - start >= dur:
                    break

                # Decrease radius each round
                current_radius = max_radius - (round_num * (max_radius - min_radius) // 10)
                # Add wobble (±5%)
                current_radius = int(current_radius * random.uniform(0.95, 1.05))

                # Random points per circle (12-20 for natural imperfection)
                num_points = random.randint(12, 20)

                for i in range(num_points):
                    if time.time() - start >= dur:
                        return  # Incomplete circle OK

                    angle = (360 / num_points) * i
                    # Add wobble to angle (±3°)
                    angle += random.uniform(-3, 3)
                    rad_angle = math.radians(angle)

                    # Add wobble to radius (±3%)
                    wobble_radius = current_radius * random.uniform(0.97, 1.03)

                    x = center_x + int(wobble_radius * math.cos(rad_angle))
                    y = center_y + int(wobble_radius * math.sin(rad_angle))

                    # Variable speed
                    move_dur = random.uniform(0.05, 0.15)
                    pyautogui.moveTo(x, y, duration=move_dur)

                    # Random pause (sometimes none)
                    if random.random() < 0.3:
                        time.sleep(random.uniform(0.02, 0.08))

        def expanding_circles(dur, radius):
            """Circles from small to large (10 rounds)"""
            logger.debug("[Mouse] 🔴 Expanding circles pattern")
            start = time.time()
            min_radius = int(radius * 0.2)  # Start small
            max_radius = int(radius * 1.5)  # End big

            for round_num in range(10):
                if time.time() - start >= dur:
                    break

                # Increase radius each round
                current_radius = min_radius + (round_num * (max_radius - min_radius) // 10)
                current_radius = int(current_radius * random.uniform(0.95, 1.05))

                num_points = random.randint(12, 20)

                for i in range(num_points):
                    if time.time() - start >= dur:
                        return

                    angle = (360 / num_points) * i + random.uniform(-3, 3)
                    rad_angle = math.radians(angle)
                    wobble_radius = current_radius * random.uniform(0.97, 1.03)

                    x = center_x + int(wobble_radius * math.cos(rad_angle))
                    y = center_y + int(wobble_radius * math.sin(rad_angle))

                    pyautogui.moveTo(x, y, duration=random.uniform(0.05, 0.15))

                    if random.random() < 0.3:
                        time.sleep(random.uniform(0.02, 0.08))

        def figure_eight(dur, radius):
            """Infinity/figure-8 pattern"""
            logger.debug("[Mouse] ∞ Figure-8 pattern")
            start = time.time()

            # Parameter for lemniscate (figure-8)
            a = radius * random.uniform(0.8, 1.2)
            num_points = int(dur * 15)  # Adapt to duration

            for i in range(num_points):
                if time.time() - start >= dur:
                    return

                t = (i / num_points) * 4 * math.pi  # Full figure-8
                # Add wobble
                t += random.uniform(-0.1, 0.1)

                # Lemniscate equations with wobble
                denominator = 1 + math.sin(t) ** 2
                x = center_x + int((a * math.cos(t) / denominator) * random.uniform(0.95, 1.05))
                y = center_y + int((a * math.sin(t) * math.cos(t) / denominator) * random.uniform(0.95, 1.05))

                pyautogui.moveTo(x, y, duration=random.uniform(0.08, 0.2))

                if random.random() < 0.2:
                    time.sleep(random.uniform(0.01, 0.05))

        def spiral_outward(dur, radius):
            """Spiral from center outward"""
            logger.debug("[Mouse] 🌀 Spiral outward pattern")
            start = time.time()

            max_radius = radius * random.uniform(1.2, 1.5)
            num_points = int(dur * 20)

            for i in range(num_points):
                if time.time() - start >= dur:
                    return

                # Gradually increasing radius
                current_r = (i / num_points) * max_radius
                angle = i * 25  # Degrees per point (creates spiral)
                angle += random.uniform(-5, 5)  # Wobble

                rad_angle = math.radians(angle)
                x = center_x + int(current_r * math.cos(rad_angle) * random.uniform(0.95, 1.05))
                y = center_y + int(current_r * math.sin(rad_angle) * random.uniform(0.95, 1.05))

                pyautogui.moveTo(x, y, duration=random.uniform(0.05, 0.12))

                if random.random() < 0.25:
                    time.sleep(random.uniform(0.01, 0.06))

        def spiral_inward(dur, radius):
            """Spiral from outside inward"""
            logger.debug("[Mouse] 🌀 Spiral inward pattern")
            start = time.time()

            max_radius = radius * random.uniform(1.2, 1.5)
            num_points = int(dur * 20)

            for i in range(num_points):
                if time.time() - start >= dur:
                    return

                # Gradually decreasing radius
                current_r = max_radius - ((i / num_points) * max_radius)
                angle = i * 25
                angle += random.uniform(-5, 5)

                rad_angle = math.radians(angle)
                x = center_x + int(current_r * math.cos(rad_angle) * random.uniform(0.95, 1.05))
                y = center_y + int(current_r * math.sin(rad_angle) * random.uniform(0.95, 1.05))

                pyautogui.moveTo(x, y, duration=random.uniform(0.05, 0.12))

                if random.random() < 0.25:
                    time.sleep(random.uniform(0.01, 0.06))

        def random_wander(dur, radius):
            """Random wandering within safe area"""
            logger.debug("[Mouse] 🔀 Random wandering pattern")
            start = time.time()

            # Safe area (60% of screen centered)
            safe_width = int(screen_width * 0.6)
            safe_height = int(screen_height * 0.6)
            min_x = center_x - safe_width // 2
            max_x = center_x + safe_width // 2
            min_y = center_y - safe_height // 2
            max_y = center_y + safe_height // 2

            while time.time() - start < dur:
                # Random destination within safe area
                dest_x = random.randint(min_x, max_x)
                dest_y = random.randint(min_y, max_y)

                # Smooth movement with variable speed
                move_dur = random.uniform(0.3, 0.8)
                pyautogui.moveTo(dest_x, dest_y, duration=move_dur)

                # Random pause
                pause = random.uniform(0.1, 0.4)
                time.sleep(min(pause, dur - (time.time() - start)))

        def wave_horizontal(dur, radius):
            """Horizontal wave pattern"""
            logger.debug("[Mouse] 〰️ Horizontal wave pattern")
            start = time.time()

            amplitude = radius * random.uniform(0.6, 1.0)
            wavelength = screen_width * 0.3
            num_points = int(dur * 25)

            start_x = center_x - int(wavelength)

            for i in range(num_points):
                if time.time() - start >= dur:
                    return

                x = start_x + (i / num_points) * (wavelength * 2)
                # Sine wave with wobble
                y = center_y + int(amplitude * math.sin((x - start_x) / wavelength * 2 * math.pi) * random.uniform(0.9, 1.1))

                pyautogui.moveTo(int(x), int(y), duration=random.uniform(0.06, 0.15))

                if random.random() < 0.2:
                    time.sleep(random.uniform(0.01, 0.05))

        def wave_vertical(dur, radius):
            """Vertical wave pattern"""
            logger.debug("[Mouse] 〰️ Vertical wave pattern")
            start = time.time()

            amplitude = radius * random.uniform(0.6, 1.0)
            wavelength = screen_height * 0.3
            num_points = int(dur * 25)

            start_y = center_y - int(wavelength)

            for i in range(num_points):
                if time.time() - start >= dur:
                    return

                y = start_y + (i / num_points) * (wavelength * 2)
                x = center_x + int(amplitude * math.sin((y - start_y) / wavelength * 2 * math.pi) * random.uniform(0.9, 1.1))

                pyautogui.moveTo(int(x), int(y), duration=random.uniform(0.06, 0.15))

                if random.random() < 0.2:
                    time.sleep(random.uniform(0.01, 0.05))

        def zigzag_pattern(dur, radius):
            """Sharp zigzag movements"""
            logger.debug("[Mouse] ⚡ Zigzag pattern")
            start = time.time()

            amplitude = radius * random.uniform(0.8, 1.2)
            num_zigs = int(dur * 3)  # 3 zigs per second

            for i in range(num_zigs):
                if time.time() - start >= dur:
                    return

                # Alternate left-right
                direction = 1 if i % 2 == 0 else -1
                x = center_x + int(direction * amplitude * random.uniform(0.8, 1.2))
                y = center_y + int((i - num_zigs/2) * (amplitude / 2) * random.uniform(0.9, 1.1))

                pyautogui.moveTo(x, int(y), duration=random.uniform(0.2, 0.4))

                if random.random() < 0.3:
                    time.sleep(random.uniform(0.05, 0.15))

        def butterfly_pattern(dur, radius):
            """Butterfly/Lissajous curve"""
            logger.debug("[Mouse] 🦋 Butterfly pattern")
            start = time.time()

            a = radius * random.uniform(0.8, 1.2)
            b = radius * random.uniform(0.7, 1.1)
            num_points = int(dur * 20)

            for i in range(num_points):
                if time.time() - start >= dur:
                    return

                t = (i / num_points) * 4 * math.pi
                t += random.uniform(-0.05, 0.05)

                # Parametric butterfly curve with wobble
                x = center_x + int(a * math.sin(t) * random.uniform(0.95, 1.05))
                y = center_y + int(b * math.sin(2*t) * random.uniform(0.95, 1.05))

                pyautogui.moveTo(x, y, duration=random.uniform(0.08, 0.18))

                if random.random() < 0.2:
                    time.sleep(random.uniform(0.01, 0.06))

        # List of all 10 patterns
        patterns = [
            shrinking_circles,
            expanding_circles,
            figure_eight,
            spiral_outward,
            spiral_inward,
            random_wander,
            wave_horizontal,
            wave_vertical,
            zigzag_pattern,
            butterfly_pattern
        ]

        # Randomly select one pattern
        selected_pattern = random.choice(patterns)

        try:
            logger.debug("[Mouse] 🎨 Starting idle mouse activity (duration=%.1fs)", duration)
            start_time = time.time()

            # Execute selected pattern
            selected_pattern(duration, base_radius)

            elapsed = time.time() - start_time
            logger.debug("[Mouse] ✓ Mouse activity complete (%.1f seconds)", elapsed)

        except Exception as e:
            logger.warning("[Mouse] Mouse activity failed: %s", str(e))
        finally:
            # Always try to return to center gracefully
            try:
                remaining_time = max(0.1, duration - (time.time() - start_time))
                pyautogui.moveTo(center_x, center_y, duration=min(0.3, remaining_time))
            except:
                pass

    def return_to_mid_screen(self) -> None:
        """
        Return mouse to center of screen after completing an activity.
        Provides visual closure and prepares for next action.
        """
        try:
            screen_width, screen_height = pyautogui.size()
            center_x = screen_width // 2
            center_y = screen_height // 2

            logger.debug("[Mouse] Returning to mid-screen (%d, %d)", center_x, center_y)
            pyautogui.moveTo(center_x, center_y, duration=0.4)

        except Exception as e:
            logger.warning("[Mouse] Failed to return to mid-screen: %s", str(e))

    def upload_to_bookmark(self, bookmark: Dict[str, str], folder_path: str, max_retries: int = 3) -> bool:
        """
        Complete upload workflow for single bookmark.

        Args:
            bookmark: Bookmark dict with title and URL
            folder_path: Path to creator folder with videos
            max_retries: Maximum retry attempts

        Returns:
            True if upload successful
        """
        bookmark_title = bookmark['title']

        # Phase 2: Check network before starting
        if not self.network_monitor.is_network_stable():
            logger.warning("[Upload] Network unstable, waiting for recovery...")
            if not self.network_monitor.wait_for_reconnection(max_wait=300):
                logger.error("[Upload] Network timeout, cannot start upload")
                return False

        for attempt in range(1, max_retries + 1):
            try:
                logger.info("[Upload] ═══════════════════════════════════════════")
                logger.info("[Upload] Attempt %d/%d for: %s", attempt, max_retries, bookmark_title)
                logger.info("[Upload] ═══════════════════════════════════════════")

                # Step 1: Navigate to bookmark
                if not self.navigate_to_bookmark(bookmark):
                    if attempt < max_retries:
                        logger.warning("[Upload] Navigation failed, retrying...")
                        continue
                    raise Exception("Failed to navigate to bookmark")

                # Step 2: Get video file FIRST (before clicking button!)
                video_file = self.get_first_video_from_folder(folder_path)
                if not video_file:
                    raise Exception("No video found in folder")

                video_name = os.path.splitext(os.path.basename(video_file))[0]
                logger.info("[Upload] ✓ Video ready: %s", video_name)

                # Phase 2: Track current upload in state
                self.current_video = video_file
                self.current_bookmark = bookmark_title
                self.current_attempt = attempt

                self.state_manager.update_current_upload(
                    video_file=video_file,
                    video_name=video_name,
                    bookmark=bookmark_title,
                    status="uploading",
                    progress=0,
                    attempt=attempt
                )
                logger.debug("[Upload] ✓ State saved (video: %s, attempt: %d)", video_name, attempt)

                # Step 3: Wait for page to stabilize with star animation
                logger.info("[Upload] Waiting for page to fully stabilize (with star animation)...")
                self.idle_mouse_activity(duration=3.0, base_radius=95)  # Give Facebook time to load all elements

                # Step 3-Priority2: Dismiss any popups/notifications before proceeding
                self.dismiss_notifications()

                # Step 3a: Find file input element (BEFORE clicking "Add Videos" button)
                logger.info("[Upload] ═══════════════════════════════════════════")
                logger.info("[Upload] PRE-LOADING File (Prevents Dialog)")
                logger.info("[Upload] ═══════════════════════════════════════════")

                file_inputs = self.driver.find_elements(By.XPATH, "//input[@type='file']")
                file_preloaded = False

                if file_inputs:
                    logger.info("[Upload] ✓ Found %d file input(s) BEFORE button click", len(file_inputs))

                    # Inject file path into ALL file inputs (prevents dialog)
                    for idx, file_input in enumerate(file_inputs, 1):
                        try:
                            logger.info("[Upload] Injecting file into input #%d...", idx)

                            # Make input visible temporarily (helps with some implementations)
                            try:
                                self.driver.execute_script("""
                                    arguments[0].style.display = 'block';
                                    arguments[0].style.visibility = 'visible';
                                    arguments[0].style.opacity = '1';
                                """, file_input)
                            except:
                                pass

                            # Inject file path
                            file_input.send_keys(video_file)
                            time.sleep(0.5)

                            # Verify injection
                            value = file_input.get_attribute("value")
                            if value and video_file in value:
                                logger.info("[Upload] ✓ File verified in input #%d: %s", idx, value[-50:])
                                file_preloaded = True
                            else:
                                logger.warning("[Upload] ⚠ File not verified in input #%d", idx)

                            # Hide input again
                            try:
                                self.driver.execute_script("""
                                    arguments[0].style.display = 'none';
                                """, file_input)
                            except:
                                pass

                        except Exception as e:
                            logger.warning("[Upload] Input #%d injection failed: %s", idx, str(e))

                    if file_preloaded:
                        logger.info("[Upload] ═══════════════════════════════════════════")
                        logger.info("[Upload] ✓✓✓ FILE PRE-LOADED SUCCESSFULLY! ✓✓✓")
                        logger.info("[Upload] ═══════════════════════════════════════════")
                        logger.info("[Upload] Letting file settle (with star animation)...")
                        self.idle_mouse_activity(duration=2.0, base_radius=85)  # Let it settle
                    else:
                        logger.warning("[Upload] ⚠ File pre-load verification failed")
                else:
                    logger.warning("[Upload] ⚠ No file inputs found yet (will try after button click)")
                    file_preloaded = False

                # Step 4: Now find and click "Add Videos" button
                logger.info("[Upload] ───────────────────────────────────────────")
                logger.info("[Upload] Finding 'Add Videos' button...")
                logger.info("[Upload] ───────────────────────────────────────────")

                # DEFENSIVE CHECK: Ensure window is ready before finding button
                if not self.ensure_window_ready("finding Add Videos button"):
                    logger.warning("[Upload] ⚠ Window readiness check failed, but continuing...")

                button_result = self.find_add_videos_button()
                if not button_result:
                    if attempt < max_retries:
                        logger.warning("[Upload] Button not found, retrying...")
                        continue
                    raise Exception("Add Videos button not found")

                # Click the button (file is ALREADY injected, so NO DIALOG!)
                logger.info("[Upload] ═══════════════════════════════════════════")
                logger.info("[Upload] Clicking 'Add Videos' Button...")
                logger.info("[Upload] ═══════════════════════════════════════════")

                if isinstance(button_result, tuple):
                    # Image recognition result - use PyAutoGUI
                    button_x, button_y = button_result
                    logger.info("[Upload] Using PyAutoGUI click at (%d, %d)...", button_x, button_y)
                    pyautogui.click(button_x, button_y)
                else:
                    # Text-based result - use Selenium click
                    logger.info("[Upload] Using Selenium click (tag: %s)...", button_result.tag_name)
                    button_result.click()

                logger.info("[Upload] ✓ Button clicked!")

                # CRITICAL: Monitor for file dialog and close it if it appears
                logger.info("[Upload] Monitoring for unwanted file dialog...")
                time.sleep(1)  # Give time for dialog to appear if it's going to

                # Check if dialog opened (Windows-specific)
                import platform
                if platform.system() == "Windows":
                    try:
                        import subprocess
                        # Check for "Open" dialog window
                        ps_check = '''
                        $windows = Get-Process | Where-Object {$_.MainWindowTitle -like "*Open*" -or $_.MainWindowTitle -like "*Browse*"}
                        if ($windows) { Write-Output "DialogFound" } else { Write-Output "NoDialog" }
                        '''

                        result = subprocess.run(
                            ["powershell", "-Command", ps_check],
                            capture_output=True,
                            text=True,
                            timeout=2
                        )

                        if "DialogFound" in result.stdout:
                            logger.warning("[Upload] ⚠ File dialog detected! Closing it...")

                            # Send ESC key to close dialog
                            ps_close = '''
                            Add-Type @"
                            using System;
                            using System.Runtime.InteropServices;
                            public class KeySend {
                                [DllImport("user32.dll")]
                                public static extern void keybd_event(byte bVk, byte bScan, int dwFlags, int dwExtraInfo);
                            }
"@
                            [KeySend]::keybd_event(0x1B, 0, 0, 0)  # ESC key down
                            Start-Sleep -Milliseconds 100
                            [KeySend]::keybd_event(0x1B, 0, 2, 0)  # ESC key up
                            '''

                            subprocess.run(
                                ["powershell", "-ExecutionPolicy", "Bypass", "-Command", ps_close],
                                timeout=2
                            )

                            logger.info("[Upload] ✓ Dialog closed with ESC key")
                            time.sleep(0.5)
                        else:
                            logger.info("[Upload] ✓ No file dialog detected (good!)")

                    except Exception as e:
                        logger.debug("[Upload] Dialog check failed: %s", str(e))

                logger.info("[Upload] Waiting for page response (with star animation)...")
                self.idle_mouse_activity(duration=2.0, base_radius=90)  # Wait for page response

                if file_preloaded:
                    logger.info("[Upload] ═══════════════════════════════════════════")
                    logger.info("[Upload] ✓ Button clicked (file was pre-loaded)")
                    logger.info("[Upload] ✓ NO FILE DIALOG SHOULD HAVE APPEARED!")
                    logger.info("[Upload] ═══════════════════════════════════════════")
                else:
                    logger.warning("[Upload] ⚠ Button clicked but file was not pre-loaded")
                    logger.warning("[Upload] ⚠ Dialog may have appeared")

                # Step 5: If file input wasn't available before, inject now
                if not file_inputs:
                    logger.info("[Upload] Injecting file NOW (after button click)...")
                    if not self.upload_video_file(video_file):
                        if attempt < max_retries:
                            logger.warning("[Upload] Upload failed, retrying...")
                            continue
                        raise Exception("File upload failed")

                # Step 6: Set title IMMEDIATELY (while upload is in progress)
                # Don't wait for 100% - title field appears as soon as upload starts
                logger.info("[Upload] ═══════════════════════════════════════════")
                logger.info("[Upload] Setting Title (Upload In Progress)")
                logger.info("[Upload] ═══════════════════════════════════════════")

                # Short wait for upload interface to fully appear
                time.sleep(1)

                # Set title NOW (upload running in background)
                title_set = self.set_video_title(video_name)
                if title_set:
                    logger.info("[Upload] ✓ Title set while video uploading!")
                else:
                    logger.warning("[Upload] ⚠ Could not set title (continuing anyway)")

                # Step 7: Monitor progress (upload continues in background)
                logger.info("[Upload] ═══════════════════════════════════════════")
                logger.info("[Upload] Monitoring Upload Progress")
                logger.info("[Upload] ═══════════════════════════════════════════")

                # DEFENSIVE CHECK: Ensure window is ready before monitoring
                if not self.ensure_window_ready("monitoring upload progress"):
                    logger.warning("[Upload] ⚠ Window readiness check failed, but continuing...")

                if not self.monitor_upload_progress():
                    if attempt < max_retries:
                        logger.warning("[Upload] Upload did not complete, retrying...")
                        continue
                    raise Exception("Upload did not complete")

                # Success!
                logger.info("[Upload] ═══════════════════════════════════════════")
                logger.info("[Upload] ✓ SUCCESS: Video Uploaded")
                logger.info("[Upload]   Bookmark: %s", bookmark_title)
                logger.info("[Upload]   Video: %s", video_name)
                logger.info("[Upload]   Status: 100%% Complete")
                logger.info("[Upload] ═══════════════════════════════════════════")

                # DEFENSIVE CHECK: Ensure window is ready before finding publish button
                if not self.ensure_window_ready("finding publish button"):
                    logger.warning("[Upload] ⚠ Window readiness check failed, but continuing...")

                # Detect and hover on Publish button (production mode: no click)
                self.detect_and_hover_publish_button()

                # Phase 2: Move video using FileHandler (robust file operations)
                moved_to = self.file_handler.move_video_to_uploaded(video_file, folder_path)
                if moved_to:
                    logger.info("[Upload] ✓ Video moved to 'uploaded videos' folder")

                    # Phase 2: Mark video as uploaded in permanent history
                    self.state_manager.mark_video_uploaded(
                        video_file=video_file,
                        bookmark=bookmark_title,
                        moved_to=moved_to
                    )
                else:
                    logger.warning("[Upload] ⚠ Could not move video (continuing anyway)")

                # Phase 2: Clear current upload state
                self.state_manager.clear_current_upload()
                logger.debug("[Upload] ✓ State cleared after successful upload")

                return True

            except Exception as e:
                logger.error("[Upload] Attempt %d failed: %s", attempt, str(e))

                # Phase 2: Update state with failure info
                self.state_manager.update_current_upload(
                    status="failed",
                    attempt=attempt
                )

                if attempt < max_retries:
                    logger.info("[Upload] Retrying in 5 seconds...")
                    time.sleep(5)
                else:
                    # Phase 2: All retries exhausted - delete failed video
                    logger.error("[Upload] ═══════════════════════════════════════════")
                    logger.error("[Upload] ✗ FAILED: %s", bookmark_title)
                    logger.error("[Upload]   Error: %s", str(e))
                    logger.error("[Upload]   Video: %s", video_name)
                    logger.error("[Upload] ═══════════════════════════════════════════")

                    # Delete video after 3 failed attempts
                    if self.file_handler.delete_failed_video(
                        video_file,
                        reason=f"failed after {max_retries} retries: {str(e)}"
                    ):
                        logger.warning("[Upload] ✓ Failed video deleted to prevent re-upload")
                    else:
                        logger.error("[Upload] ✗ Could not delete failed video")

                    # Phase 2: Clear state after failure
                    self.state_manager.clear_current_upload()

                    return False

        return False
