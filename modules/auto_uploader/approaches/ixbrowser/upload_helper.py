"""
Video Upload Helper for ixBrowser Approach
Handles bulk video upload to Facebook bookmarks
"""

import logging
import os
import time
import glob
import pyautogui
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

# Image path for Add Videos button
ADD_VIDEOS_BUTTON_IMAGE = "/home/user/automation-fb/modules/auto_uploader/helper_images/add_videos_button.png"


class VideoUploadHelper:
    """Helper class for uploading videos to Facebook via bookmarks."""

    def __init__(self, driver: Any):
        """
        Initialize upload helper.

        Args:
            driver: Selenium WebDriver instance
        """
        self.driver = driver
        self.upload_timeout = 600  # 10 minutes max per video

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

            # Debug: See what's on the page
            self.debug_page_content(title)

            return True

        except Exception as e:
            logger.error("[Upload] Navigation failed: %s", str(e))
            return False

    def debug_page_content(self, bookmark_name: str) -> None:
        """Debug helper to see what's on the page."""
        try:
            # Get all clickable elements (buttons, divs with role=button, etc)
            all_buttons = self.driver.find_elements("xpath", "//button")
            all_divs_button = self.driver.find_elements("xpath", "//div[@role='button']")
            all_clickable = self.driver.find_elements("xpath", "//*[@onclick or @role='button']")

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
                    logger.info("[Upload] Retry %d/%d", attempt, retries)
                    time.sleep(2)

                # Method 1: ANY element containing "Add Videos" text (divs, spans, buttons, etc)
                try:
                    elements = self.driver.find_elements("xpath",
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
                    elements = self.driver.find_elements("xpath",
                        "//div[@role='button' and contains(., 'Add Videos')]")
                    if elements:
                        logger.info("[Upload] ✓ Found button (div role=button)")
                        return elements[0]
                except Exception as e:
                    logger.debug("[Upload] Div role=button search failed: %s", str(e))

                # Method 3: Spans containing text
                try:
                    elements = self.driver.find_elements("xpath",
                        "//span[contains(text(), 'Add Videos')]")
                    if elements:
                        # Get the parent element (likely the clickable container)
                        parent = elements[0].find_element("xpath", "..")
                        logger.info("[Upload] ✓ Found button (span parent)")
                        return parent
                except Exception as e:
                    logger.debug("[Upload] Span search failed: %s", str(e))

                # Method 4: Case-insensitive search
                try:
                    elements = self.driver.find_elements("xpath",
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
                    elements = self.driver.find_elements("xpath",
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
                    logger.info("[Upload] Retry %d/%d", attempt, retries)
                    time.sleep(2)

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

    def upload_video_file(self, video_path: str) -> bool:
        """
        Upload video via file input element.

        Args:
            video_path: Full path to video file

        Returns:
            True if upload initiated
        """
        try:
            logger.info("[Upload] Initiating file upload...")

            # Find file input elements (usually hidden)
            file_inputs = self.driver.find_elements("xpath", "//input[@type='file']")

            if not file_inputs:
                logger.error("[Upload] ✗ File input element not found")
                return False

            # Try first input
            file_input = file_inputs[0]

            logger.info("[Upload] Sending file path to input...")
            file_input.send_keys(video_path)

            # Wait for upload to start
            time.sleep(3)

            logger.info("[Upload] ✓ File sent to uploader")
            return True

        except Exception as e:
            logger.error("[Upload] File upload failed: %s", str(e))
            return False

    def set_video_title(self, title: str) -> bool:
        """
        Set video title in appropriate field.

        Args:
            title: Video title to set

        Returns:
            True if title was set
        """
        logger.info("[Upload] Setting title: %s", title)

        # Method 1: Title field (various selectors)
        title_selectors = [
            "//input[@placeholder='Title']",
            "//input[@name='title']",
            "//input[contains(@aria-label, 'Title')]",
            "//input[contains(@placeholder, 'title')]",
        ]

        for selector in title_selectors:
            try:
                fields = self.driver.find_elements("xpath", selector)
                if fields:
                    field = fields[0]

                    # Check existing text
                    existing = field.get_attribute("value") or ""
                    if existing:
                        logger.info("[Upload] Clearing existing title: %s", existing)
                        field.clear()

                    field.send_keys(title)
                    logger.info("[Upload] ✓ Title set in title field")
                    return True
            except:
                pass

        # Method 2: Description field (fallback)
        try:
            desc_fields = self.driver.find_elements("xpath",
                "//textarea[contains(@placeholder, 'describe your reel')]")

            if desc_fields:
                field = desc_fields[0]
                field.send_keys(title)
                logger.info("[Upload] ✓ Title set in description field (fallback)")
                return True

        except Exception as e:
            logger.debug("[Upload] Description field failed: %s", str(e))

        logger.warning("[Upload] ⚠ Could not set title")
        return False

    def monitor_upload_progress(self) -> bool:
        """
        Monitor upload progress until 100% complete.

        Returns:
            True if upload completed successfully
        """
        logger.info("[Upload] Monitoring upload progress...")

        start_time = time.time()
        last_progress = 0

        while (time.time() - start_time) < self.upload_timeout:
            try:
                # Method 1: Progress bar with aria-valuenow
                progress_bars = self.driver.find_elements("xpath", "//*[@role='progressbar']")

                if progress_bars:
                    for bar in progress_bars:
                        value = bar.get_attribute("aria-valuenow")
                        if value:
                            try:
                                progress = int(float(value))

                                if progress != last_progress:
                                    logger.info("[Upload] Progress: %d%%", progress)
                                    last_progress = progress

                                if progress >= 100:
                                    logger.info("[Upload] ✓ Upload 100% complete!")
                                    return True
                            except:
                                pass

                # Method 2: Text-based percentage (e.g., "95%")
                progress_texts = self.driver.find_elements("xpath", "//*[contains(text(), '%')]")

                for text_elem in progress_texts:
                    text = text_elem.text
                    if "%" in text:
                        try:
                            # Extract number before %
                            progress_str = text.split("%")[0].strip().split()[-1]
                            progress = int(progress_str)

                            if progress != last_progress:
                                logger.info("[Upload] Progress: %d%%", progress)
                                last_progress = progress

                            if progress >= 100:
                                logger.info("[Upload] ✓ Upload 100% complete!")
                                return True
                        except:
                            pass

                # Method 3: "Complete" or "Published" indicators
                complete_indicators = self.driver.find_elements("xpath",
                    "//*[contains(text(), 'Complete') or contains(text(), 'Published') or contains(text(), 'Done')]")

                if complete_indicators:
                    logger.info("[Upload] ✓ Upload completed (indicator found)!")
                    return True

            except Exception as e:
                logger.debug("[Upload] Progress check error: %s", str(e))

            # Wait before next check
            time.sleep(3)

        # Timeout reached
        logger.error("[Upload] ✗ Upload timeout after %d seconds", self.upload_timeout)
        return False

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

                # Step 2: Find Add Videos button (text-based or image recognition)
                button_result = self.find_add_videos_button()
                if not button_result:
                    if attempt < max_retries:
                        logger.warning("[Upload] Button not found, retrying...")
                        continue
                    raise Exception("Add Videos button not found")

                # Click the button (handle both WebElement and coordinates)
                if isinstance(button_result, tuple):
                    # Image recognition result - use PyAutoGUI
                    button_x, button_y = button_result
                    logger.info("[Upload] Clicking button at (%d, %d) using PyAutoGUI...", button_x, button_y)
                    pyautogui.click(button_x, button_y)
                else:
                    # Text-based result - use Selenium click
                    logger.info("[Upload] Clicking button using Selenium (tag: %s)...", button_result.tag_name)
                    button_result.click()

                time.sleep(2)  # Wait for click response
                logger.info("[Upload] ✓ Button clicked")

                # Step 3: Get video file
                video_file = self.get_first_video_from_folder(folder_path)
                if not video_file:
                    raise Exception("No video found in folder")

                video_name = os.path.splitext(os.path.basename(video_file))[0]

                # Step 4: Upload video
                if not self.upload_video_file(video_file):
                    if attempt < max_retries:
                        logger.warning("[Upload] Upload failed, retrying...")
                        continue
                    raise Exception("File upload failed")

                # Step 5: Set title
                self.set_video_title(video_name)

                # Step 6: Monitor progress
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
                return True

            except Exception as e:
                logger.error("[Upload] Attempt %d failed: %s", attempt, str(e))
                if attempt < max_retries:
                    logger.info("[Upload] Retrying in 5 seconds...")
                    time.sleep(5)
                else:
                    logger.error("[Upload] ═══════════════════════════════════════════")
                    logger.error("[Upload] ✗ FAILED: %s", bookmark_title)
                    logger.error("[Upload]   Error: %s", str(e))
                    logger.error("[Upload] ═══════════════════════════════════════════")
                    return False

        return False
