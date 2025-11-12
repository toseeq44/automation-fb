"""
PHASE 5: Video Title Setter
Sets video title and description after upload completes using multiple detection strategies
"""

import logging
import time
from typing import Optional, Any
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException

logger = logging.getLogger(__name__)


class VideoTitleSetter:
    """Sets video title after upload using multiple robust strategies."""

    def __init__(self, driver: Optional[Any] = None, max_wait: int = 30):
        """
        Initialize title setter.

        Args:
            driver: Selenium WebDriver instance (optional)
            max_wait: Maximum wait time in seconds for elements to appear
        """
        self.driver = driver
        self.max_wait = max_wait
        logger.info("[TITLE SETTER] Initialized with max_wait=%d seconds", max_wait)

    def set_driver(self, driver: Any) -> None:
        """Set or update the Selenium WebDriver instance."""
        self.driver = driver
        logger.debug("[TITLE SETTER] WebDriver instance updated")

    def set_video_title(self, title: str, description: Optional[str] = None) -> bool:
        """
        Set video title (and optionally description) after upload completes.

        Args:
            title: Video title to set
            description: Optional video description

        Returns:
            True if title was set successfully, False otherwise
        """
        if not self.driver:
            logger.error("[TITLE SETTER] ❌ No WebDriver instance available")
            return False

        if not title:
            logger.warning("[TITLE SETTER] ⚠️ No title provided, skipping")
            return False

        logger.info(f"[TITLE SETTER] Setting video title: '{title[:50]}...'")

        # Wait for upload interface to be ready
        if not self._wait_for_upload_completion():
            logger.warning("[TITLE SETTER] ⚠️ Upload interface not confirmed, proceeding anyway")

        # Strategy 1: Try to find title input using multiple selectors
        title_input = self._find_title_input_comprehensive()

        if not title_input:
            logger.error("[TITLE SETTER] ❌ Could not find title input field after trying all strategies")
            return False

        # Set the title
        if self._set_input_value(title_input, title):
            logger.info("[TITLE SETTER] ✅ Title set successfully")

            # Optionally set description if provided
            if description:
                self._set_description(description)

            return True
        else:
            logger.error("[TITLE SETTER] ❌ Failed to set title value")
            return False

    def _wait_for_upload_completion(self) -> bool:
        """
        Wait for upload to complete and form to be ready.

        Returns:
            True if upload completed successfully
        """
        logger.debug("[TITLE SETTER] Waiting for upload completion...")

        # Strategy 1: Wait for progress indicator to disappear
        try:
            wait = WebDriverWait(self.driver, self.max_wait)

            # Common upload progress indicators on Facebook
            progress_selectors = [
                "//div[contains(@role, 'progressbar')]",
                "//div[contains(text(), 'Uploading')]",
                "//div[contains(text(), '%')]",
                "//*[contains(@class, 'progress')]",
            ]

            for selector in progress_selectors:
                try:
                    # Wait for progress element to appear first
                    element = self.driver.find_element(By.XPATH, selector)
                    logger.debug(f"[TITLE SETTER] Found progress indicator: {selector}")

                    # Then wait for it to disappear (upload complete)
                    wait.until(EC.invisibility_of_element(element))
                    logger.info("[TITLE SETTER] ✅ Upload progress completed")
                    time.sleep(2)  # Small delay for form to fully render
                    return True
                except (NoSuchElementException, TimeoutException):
                    continue

        except Exception as e:
            logger.debug(f"[TITLE SETTER] Progress check failed: {e}")

        # Strategy 2: Just wait a fixed time for upload to complete
        logger.debug("[TITLE SETTER] No progress indicator found, using fixed wait")
        time.sleep(5)
        return True

    def _find_title_input_comprehensive(self) -> Optional[Any]:
        """
        Find title input using multiple comprehensive strategies.

        Returns:
            WebElement if found, None otherwise
        """
        logger.info("[TITLE SETTER] Searching for title input field...")

        # Define all possible selectors for Facebook title input
        selectors = [
            # XPath strategies
            ("xpath", "//textarea[@placeholder='Title' or @placeholder='title']", "Title placeholder (case insensitive)"),
            ("xpath", "//textarea[contains(@placeholder, 'itle')]", "Contains 'itle' in placeholder"),
            ("xpath", "//input[@placeholder='Title' or @placeholder='title']", "Input with Title placeholder"),
            ("xpath", "//input[contains(@placeholder, 'itle')]", "Input contains 'itle'"),
            ("xpath", "//input[@name='title' or @name='Title']", "Input name='title'"),
            ("xpath", "//textarea[@name='title' or @name='Title']", "Textarea name='title'"),
            ("xpath", "//textarea[@aria-label='Title' or @aria-label='title']", "Aria-label Title"),
            ("xpath", "//textarea[contains(@aria-label, 'itle')]", "Aria-label contains 'itle'"),
            ("xpath", "//input[@aria-label='Title' or @aria-label='title']", "Input aria-label Title"),
            ("xpath", "//input[contains(@aria-label, 'itle')]", "Input aria-label contains 'itle'"),

            # Facebook-specific patterns
            ("xpath", "//textarea[contains(@placeholder, 'describe your')]", "Describe your... placeholder"),
            ("xpath", "//textarea[contains(@placeholder, 'Say something')]", "Say something placeholder"),
            ("xpath", "//textarea[contains(@placeholder, 'What')]", "What's... placeholder"),
            ("xpath", "//div[@contenteditable='true' and @role='textbox']", "Contenteditable div (common in FB)"),
            ("xpath", "//div[@contenteditable='true'][@aria-label]", "Contenteditable with aria-label"),

            # CSS strategies
            ("css", "textarea[placeholder*='itle']", "CSS: textarea placeholder contains itle"),
            ("css", "input[placeholder*='itle']", "CSS: input placeholder contains itle"),
            ("css", "textarea[name='title']", "CSS: textarea name=title"),
            ("css", "input[name='title']", "CSS: input name=title"),
            ("css", "textarea[aria-label*='itle']", "CSS: textarea aria-label contains itle"),
            ("css", "div[contenteditable='true'][role='textbox']", "CSS: contenteditable div"),

            # Generic fallback - first visible textarea
            ("xpath", "(//textarea)[1]", "First textarea on page"),
            ("css", "textarea", "First textarea (CSS)"),
        ]

        # Try each selector with wait
        for selector_type, selector, description in selectors:
            try:
                logger.debug(f"[TITLE SETTER] Trying: {description}")

                by_type = By.XPATH if selector_type == "xpath" else By.CSS_SELECTOR
                wait = WebDriverWait(self.driver, 3)  # Short wait for each attempt

                element = wait.until(
                    EC.presence_of_element_located((by_type, selector))
                )

                # Verify element is visible and enabled
                if element.is_displayed() and element.is_enabled():
                    logger.info(f"[TITLE SETTER] ✅ Found title input using: {description}")

                    # Scroll element into view
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
                    time.sleep(0.5)

                    return element
                else:
                    logger.debug(f"[TITLE SETTER] Element found but not visible/enabled: {description}")

            except (TimeoutException, NoSuchElementException):
                continue
            except StaleElementReferenceException:
                logger.debug(f"[TITLE SETTER] Stale element, retrying: {description}")
                continue
            except Exception as e:
                logger.debug(f"[TITLE SETTER] Error with {description}: {e}")
                continue

        # If nothing found, try to find any input-like element in the upload form area
        logger.warning("[TITLE SETTER] ⚠️ Standard selectors failed, trying fallback strategies...")
        return self._find_title_input_fallback()

    def _find_title_input_fallback(self) -> Optional[Any]:
        """
        Fallback strategy: Find input by analyzing page structure.

        Returns:
            WebElement if found, None otherwise
        """
        try:
            # Look for all textareas and inputs, filter by context
            all_textareas = self.driver.find_elements(By.TAG_NAME, "textarea")

            for textarea in all_textareas:
                try:
                    if not textarea.is_displayed():
                        continue

                    # Check if this textarea is near upload-related text
                    parent = textarea.find_element(By.XPATH, "..")
                    parent_text = parent.text.lower()

                    upload_keywords = ['upload', 'post', 'video', 'share', 'publish', 'title', 'description']

                    if any(keyword in parent_text for keyword in upload_keywords):
                        logger.info("[TITLE SETTER] ✅ Found likely title input via context analysis")
                        return textarea

                except:
                    continue

            # Last resort: return first visible textarea
            for textarea in all_textareas:
                if textarea.is_displayed() and textarea.is_enabled():
                    logger.warning("[TITLE SETTER] ⚠️ Using first visible textarea as fallback")
                    return textarea

        except Exception as e:
            logger.error(f"[TITLE SETTER] Fallback search failed: {e}")

        return None

    def _set_input_value(self, element: Any, value: str) -> bool:
        """
        Set value in an input/textarea element with multiple strategies.

        Args:
            element: WebElement to set value in
            value: Value to set

        Returns:
            True if successful
        """
        logger.debug(f"[TITLE SETTER] Setting value: '{value[:50]}...'")

        try:
            # Strategy 1: Click and clear first
            element.click()
            time.sleep(0.3)
            element.clear()
            time.sleep(0.3)
            element.send_keys(value)

            # Verify value was set
            time.sleep(0.5)
            current_value = element.get_attribute('value') or element.text

            if current_value and value in current_value:
                logger.info("[TITLE SETTER] ✅ Value verified in element")
                return True
            else:
                logger.debug("[TITLE SETTER] Value not verified, trying alternative method...")

                # Strategy 2: Use JavaScript to set value
                tag_name = element.tag_name.lower()

                if tag_name == "div":  # contenteditable div
                    self.driver.execute_script(
                        "arguments[0].innerText = arguments[1];",
                        element, value
                    )
                else:  # input/textarea
                    self.driver.execute_script(
                        "arguments[0].value = arguments[1];",
                        element, value
                    )

                # Trigger input event
                self.driver.execute_script(
                    "arguments[0].dispatchEvent(new Event('input', { bubbles: true }));",
                    element
                )

                logger.info("[TITLE SETTER] ✅ Value set via JavaScript")
                return True

        except Exception as e:
            logger.error(f"[TITLE SETTER] ❌ Failed to set value: {e}")
            return False

    def _set_description(self, description: str) -> bool:
        """
        Set video description if field is available.

        Args:
            description: Description text

        Returns:
            True if set successfully
        """
        logger.debug(f"[TITLE SETTER] Attempting to set description: '{description[:50]}...'")

        description_selectors = [
            ("xpath", "//textarea[@placeholder='Description' or @placeholder='description']"),
            ("xpath", "//textarea[contains(@placeholder, 'escription')]"),
            ("xpath", "//textarea[contains(@aria-label, 'escription')]"),
            ("xpath", "(//textarea)[2]"),  # Often description is second textarea
        ]

        for selector_type, selector in description_selectors:
            try:
                by_type = By.XPATH if selector_type == "xpath" else By.CSS_SELECTOR
                wait = WebDriverWait(self.driver, 3)
                element = wait.until(EC.presence_of_element_located((by_type, selector)))

                if element.is_displayed() and element.is_enabled():
                    return self._set_input_value(element, description)

            except:
                continue

        logger.debug("[TITLE SETTER] Description field not found or not accessible")
        return False


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    # This would normally be called after upload completes
    # driver = webdriver.Chrome()  # Your existing driver instance
    # title_setter = VideoTitleSetter(driver)
    # success = title_setter.set_video_title("My Amazing Video Title")
    # if success:
    #     print("✅ Title set successfully!")
    # else:
    #     print("❌ Failed to set title")
