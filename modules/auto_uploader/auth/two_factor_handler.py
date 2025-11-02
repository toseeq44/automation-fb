"""
Two Factor Handler
==================
Handles Facebook 2FA (two-factor authentication) scenarios.

Integrates with browser module for intelligent 2FA detection.
"""

import logging
import time
from typing import Optional, Dict, Any

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

from ..browser.mouse_controller import MouseController
from ..browser.screen_detector import ScreenDetector


class TwoFactorHandler:
    """Handles 2FA operations with intelligent detection."""

    # 2FA detection keywords
    TWOFA_KEYWORDS = [
        'two-factor',
        'two factor',
        '2fa',
        'authentication code',
        'security code',
        'approvals',
        'login approval',
        'enter code',
        'verification code'
    ]

    def __init__(self, driver: Optional[Any] = None, config: Optional[Dict] = None):
        """
        Initialize 2FA handler.

        Args:
            driver: Selenium WebDriver instance
            config: Configuration dictionary
        """
        self.driver = driver
        self.config = config or {}
        self.mouse = MouseController()
        self.screen_detector = ScreenDetector()

        logging.debug("TwoFactorHandler initialized")

    def detect_2fa_prompt(self) -> Dict[str, Any]:
        """
        Detect if 2FA prompt is showing.

        Returns:
            Dictionary with detection results

        Example:
            >>> handler = TwoFactorHandler(driver)
            >>> result = handler.detect_2fa_prompt()
            >>> if result['detected']:
            >>>     print(f"2FA type: {result['type']}")
        """
        logging.info("Detecting 2FA prompt...")

        result = {
            'detected': False,
            'type': None,  # 'code', 'approval', 'sms', etc.
            'confidence': 0.0
        }

        if not self.driver:
            logging.error("No WebDriver available")
            return result

        try:
            # Check URL for 2FA indicators
            current_url = self.driver.current_url

            if 'checkpoint' in current_url.lower() and 'approvals' in current_url.lower():
                result['detected'] = True
                result['type'] = 'approval'
                result['confidence'] = 0.9
                logging.info("✓ 2FA detected via URL (approval)")
                return result

            # Check page source for 2FA keywords
            page_source = self.driver.page_source.lower()

            for keyword in self.TWOFA_KEYWORDS:
                if keyword in page_source:
                    result['detected'] = True
                    result['confidence'] = 0.7

                    # Determine type based on keyword
                    if 'code' in keyword:
                        result['type'] = 'code'
                    elif 'approval' in keyword:
                        result['type'] = 'approval'
                    elif 'sms' in keyword:
                        result['type'] = 'sms'
                    else:
                        result['type'] = 'unknown'

                    logging.info("✓ 2FA detected via keyword: %s (type: %s)", keyword, result['type'])
                    return result

            # Check for code input field
            try:
                code_inputs = self.driver.find_elements(By.CSS_SELECTOR, 'input[name*="code"], input[name*="approvals"], input[placeholder*="code"]')

                if code_inputs:
                    result['detected'] = True
                    result['type'] = 'code'
                    result['confidence'] = 0.85
                    logging.info("✓ 2FA detected via code input field")
                    return result

            except Exception:
                pass

            logging.debug("No 2FA prompt detected")
            return result

        except Exception as e:
            logging.error("Error detecting 2FA: %s", e, exc_info=True)
            return result

    def wait_for_2fa_completion(self, timeout: int = 300) -> bool:
        """
        Wait for user to complete 2FA manually.

        Shows trust-building animations while waiting.

        Args:
            timeout: Maximum wait time in seconds (default 5 minutes)

        Returns:
            True if 2FA completed within timeout

        Example:
            >>> handler = TwoFactorHandler(driver)
            >>> if handler.detect_2fa_prompt()['detected']:
            >>>     print("Please complete 2FA...")
            >>>     if handler.wait_for_2fa_completion(timeout=300):
            >>>         print("2FA completed!")
        """
        logging.info("Waiting for 2FA completion (timeout: %ds)...", timeout)

        if not self.driver:
            logging.error("No WebDriver available")
            return False

        start_time = time.time()
        check_interval = 5  # Check every 5 seconds

        while time.time() - start_time < timeout:
            # Show circular animation for trust-building
            self.mouse.circular_idle_movement(duration=3.0, radius=40)

            # Check if still on 2FA page
            detection = self.detect_2fa_prompt()

            if not detection['detected']:
                # No longer on 2FA page - success!
                elapsed = time.time() - start_time
                logging.info("✓ 2FA completed after %.1fs", elapsed)
                return True

            # Log progress
            elapsed = time.time() - start_time
            remaining = timeout - elapsed
            logging.info("Still waiting for 2FA... (%.0fs elapsed, %.0fs remaining)", elapsed, remaining)

            time.sleep(check_interval)

        logging.warning("✗ 2FA not completed within timeout")
        return False

    def handle_2fa_automatically(self, code: Optional[str] = None) -> bool:
        """
        Attempt to handle 2FA automatically if code is provided.

        Args:
            code: 2FA code to enter

        Returns:
            True if code entered successfully

        Example:
            >>> handler = TwoFactorHandler(driver)
            >>> # If you have the 2FA code
            >>> handler.handle_2fa_automatically(code="123456")
        """
        logging.info("Attempting automatic 2FA handling...")

        if not self.driver:
            logging.error("No WebDriver available")
            return False

        if not code:
            logging.warning("No 2FA code provided, cannot handle automatically")
            return False

        try:
            # Find code input field
            code_inputs = self.driver.find_elements(
                By.CSS_SELECTOR,
                'input[name*="code"], input[name*="approvals"], input[placeholder*="code"], input[type="text"]'
            )

            if not code_inputs:
                logging.error("Code input field not found")
                return False

            # Use first visible input
            code_input = None
            for inp in code_inputs:
                if inp.is_displayed():
                    code_input = inp
                    break

            if not code_input:
                logging.error("No visible code input field")
                return False

            # Clear and enter code
            code_input.clear()
            time.sleep(0.5)

            # Type code with human-like timing
            self.mouse.type_text(code, interval=None)

            time.sleep(1)

            # Find and click submit button
            submit_buttons = self.driver.find_elements(
                By.CSS_SELECTOR,
                'button[type="submit"], button[name="submit"], input[type="submit"]'
            )

            for button in submit_buttons:
                if button.is_displayed():
                    # Get button position and click with mouse controller
                    location = button.location
                    size = button.size
                    x = location['x'] + size['width'] // 2
                    y = location['y'] + size['height'] // 2

                    self.mouse.click_at_position(x, y)
                    logging.info("✓ 2FA code submitted")

                    time.sleep(2)
                    return True

            logging.warning("Submit button not found")
            return False

        except Exception as e:
            logging.error("Error handling 2FA automatically: %s", e, exc_info=True)
            return False

    def is_on_2fa_page(self) -> bool:
        """
        Quick check if currently on 2FA page.

        Returns:
            True if on 2FA page
        """
        detection = self.detect_2fa_prompt()
        return detection['detected']

    def prompt_user_for_2fa(self) -> None:
        """
        Display message prompting user to complete 2FA.

        Shows console message and circular mouse animation.
        """
        logging.warning("="*60)
        logging.warning("⚠ TWO-FACTOR AUTHENTICATION REQUIRED ⚠")
        logging.warning("Please complete 2FA in the browser window")
        logging.warning("The automation will continue once 2FA is completed")
        logging.warning("="*60)

        # Show circular animation to indicate waiting
        self.mouse.circular_idle_movement(duration=5.0, radius=50)

    def wait_with_user_prompt(self, timeout: int = 300) -> bool:
        """
        Wait for 2FA completion with user prompt.

        Combines prompt_user_for_2fa() and wait_for_2fa_completion().

        Args:
            timeout: Maximum wait time

        Returns:
            True if 2FA completed

        Example:
            >>> handler = TwoFactorHandler(driver)
            >>> if handler.detect_2fa_prompt()['detected']:
            >>>     success = handler.wait_with_user_prompt(timeout=300)
        """
        self.prompt_user_for_2fa()
        return self.wait_for_2fa_completion(timeout=timeout)

    def get_2fa_info(self) -> Dict[str, Any]:
        """
        Get detailed 2FA information.

        Returns:
            Dictionary with 2FA details

        Example:
            >>> info = handler.get_2fa_info()
            >>> print(f"2FA detected: {info['detected']}")
            >>> print(f"Type: {info['type']}")
        """
        detection = self.detect_2fa_prompt()

        info = {
            'detected': detection['detected'],
            'type': detection.get('type'),
            'confidence': detection.get('confidence', 0.0),
            'url': self.driver.current_url if self.driver else None
        }

        return info

    def set_driver(self, driver: Any) -> None:
        """
        Set or update WebDriver instance.

        Args:
            driver: Selenium WebDriver
        """
        self.driver = driver
        logging.debug("WebDriver updated")
