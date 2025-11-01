"""
Simple Browser Handler - Simple and effective
Just one job: Open the browser and handle login
"""

import logging
import time
from pathlib import Path
from typing import Optional

try:
    import pyautogui
    import pygetwindow as gw
    AVAILABLE = True
except ImportError:
    AVAILABLE = False
    logging.warning("pyautogui or pygetwindow not available")


class SimpleBrowserHandler:
    """Simple browser handler - nothing complicated"""

    def __init__(self, browser_type: str = 'ix'):
        """
        Initialize handler

        Args:
            browser_type: 'ix' or 'gologin'
        """
        self.browser_type = browser_type
        self.window = None
        self.window_title_patterns = {
            'ix': ['ixBrowser', 'IX', 'Incogniton'],
            'gologin': ['GoLogin', 'Orbita']
        }

    def open_browser(self) -> bool:
        """
        Open browser - very simple, just this:
        1. Find Desktop shortcut
        2. Click it
        3. Wait

        Returns: True if successful
        """
        logging.info("=" * 60)
        logging.info(f"🚀 Opening {self.browser_type} Browser")
        logging.info("=" * 60)

        # Step 1: Network check
        logging.info("\n1️⃣  Checking network...")
        if not self._check_network():
            logging.error("❌ Network not available")
            return False
        logging.info("✓ Network OK")

        # Step 2: Open browser using desktop shortcut
        logging.info("\n2️⃣  Launching browser from desktop...")
        if not self._launch_from_desktop():
            logging.error("❌ Failed to launch browser")
            return False
        logging.info("✓ Browser launched")

        # Step 3: Find window - This is important!
        logging.info("\n3️⃣  Finding browser window...")
        self.window = self._find_window()

        if not self.window:
            logging.warning("⚠ Could not find window immediately")
            logging.warning("⚠ But browser may still be running...")
        else:
            logging.info(f"✓ Found window: {self.window.title}")

            # Step 4: Wait for browser to fully load
            logging.info("\n4️⃣  Waiting for browser to fully load...")
            self._show_activity("⏳ Loading browser...", duration=8)
            logging.info("✓ Browser ready")

        # Step 5: Maximize window
        if self.window:
            logging.info("\n5️⃣  Maximizing window...")
            try:
                self.window.maximize()
                logging.info("✓ Window maximized")
            except Exception as e:
                logging.warning(f"⚠ Could not maximize: {e}")

        logging.info("\n" + "=" * 60)
        logging.info("✅ Browser Launch Complete")
        logging.info("=" * 60)

        return True

    def check_login_status(self) -> str:
        """
        Check if logged in - simple approach:
        Just by looking at the desktop normally can tell

        Returns: 'LOGGED_IN' or 'NOT_LOGGED_IN' or 'UNCLEAR'
        """
        logging.info("\n6️⃣  Checking login status...")

        # Take screenshot
        try:
            screenshot = pyautogui.screenshot()
            # Save for manual inspection
            screenshot.save("current_screen.png")
            logging.info("✓ Screenshot saved: current_screen.png")
            logging.info("📌 Please check if you see:")
            logging.info("   - Profile icon (top right) = Logged IN")
            logging.info("   - Login form (center) = NOT logged in")

            # For now, ask user to check manually
            return 'UNCLEAR'

        except Exception as e:
            logging.error(f"❌ Error taking screenshot: {e}")
            return 'UNCLEAR'

    def logout_facebook(self) -> bool:
        """
        Logout from Facebook - simple steps

        Returns: True if successful
        """
        logging.info("\n7️⃣  Logging out current user...")

        try:
            # Try three methods:

            # Method 1: Try Alt+F4 (dangerous - could close entire window)
            # logging.info("  Trying keyboard shortcut...")
            # pyautogui.hotkey('alt', 'f4')
            # time.sleep(2)

            # Method 2: Click profile menu
            logging.info("  Looking for profile menu (top right)...")
            screen_w, screen_h = pyautogui.size()

            # Profile usually at top-right
            profile_x = screen_w - 100  # 100px from right
            profile_y = 50              # 50px from top

            logging.info(f"  Clicking at ({profile_x}, {profile_y})...")
            pyautogui.click(profile_x, profile_y)

            time.sleep(2)

            # Method 3: Click logout button (usually below profile)
            logging.info("  Looking for logout option...")
            logout_y = profile_y + 150
            pyautogui.click(profile_x, logout_y)

            time.sleep(2)

            logging.info("✓ Logout attempted")
            return True

        except Exception as e:
            logging.error(f"❌ Error during logout: {e}")
            return False

    def login_facebook(self, email: str, password: str) -> bool:
        """
        Login to Facebook - simple steps

        Args:
            email: Facebook email
            password: Facebook password

        Returns: True if successful
        """
        logging.info("\n8️⃣  Logging in to Facebook...")
        logging.info(f"📧 Email: {email}")

        try:
            # Step 1: Find login form (usually center)
            logging.info("  Looking for login form...")
            screen_w, screen_h = pyautogui.size()

            form_x = screen_w // 2
            form_y = screen_h // 2

            logging.info(f"  Clicking on login form at ({form_x}, {form_y})...")
            pyautogui.click(form_x, form_y)
            time.sleep(1)

            # Step 2: Clear existing data
            logging.info("  Clearing existing credentials...")
            pyautogui.hotkey('ctrl', 'a')  # Select all
            time.sleep(0.2)
            pyautogui.press('delete')      # Delete
            time.sleep(0.5)

            # Step 3: Type email
            logging.info("  Typing email...")
            pyautogui.typewrite(email, interval=0.02)
            time.sleep(1)

            # Step 4: Tab to password field
            logging.info("  Moving to password field...")
            pyautogui.press('tab')
            time.sleep(1)

            # Step 5: Clear password field
            logging.info("  Clearing password field...")
            pyautogui.hotkey('ctrl', 'a')
            time.sleep(0.2)
            pyautogui.press('delete')
            time.sleep(0.5)

            # Step 6: Type password
            logging.info("  Typing password...")
            pyautogui.typewrite(password, interval=0.02)
            time.sleep(1)

            # Step 7: Submit
            logging.info("  Submitting form...")
            pyautogui.press('enter')
            time.sleep(3)

            # Step 8: Wait for login
            logging.info("  Waiting for login to complete...")
            self._show_activity("⏳ Logging in...", duration=10)

            logging.info("✓ Login completed")
            return True

        except Exception as e:
            logging.error(f"❌ Error during login: {e}")
            return False

    def close_browser(self) -> bool:
        """
        Close browser safely

        Returns: True if successful
        """
        logging.info("\n9️⃣  Closing browser...")

        try:
            # Close any popups first
            logging.info("  Checking for Exit Safely popup...")
            pyautogui.press('enter')  # In case dialog is focused
            time.sleep(1)

            # Close browser window
            if self.window:
                logging.info("  Closing browser window...")
                self.window.close()
                time.sleep(2)

            logging.info("✓ Browser closed")
            return True

        except Exception as e:
            logging.error(f"❌ Error closing browser: {e}")
            return False

    # ============ Helper Functions ============

    def _check_network(self) -> bool:
        """Check internet connectivity"""
        try:
            import socket
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            return True
        except:
            return False

    def _launch_from_desktop(self) -> bool:
        """Launch browser from desktop shortcut"""
        try:
            import os
            import subprocess

            desktop = os.path.expanduser("~/Desktop")

            # Look for shortcuts
            shortcuts = [
                os.path.join(desktop, "ixBrowser.lnk"),
                os.path.join(desktop, "IX Browser.lnk"),
                os.path.join(desktop, "Incogniton.lnk"),
                os.path.join(desktop, "GoLogin.lnk"),
            ]

            for shortcut in shortcuts:
                if os.path.exists(shortcut):
                    logging.info(f"  Found shortcut: {shortcut}")
                    os.startfile(shortcut)
                    time.sleep(15)  # Wait 15 seconds for app to start
                    return True

            logging.warning("  No desktop shortcut found")
            return False

        except Exception as e:
            logging.error(f"Error launching from desktop: {e}")
            return False

    def _find_window(self) -> Optional[object]:
        """Find browser window"""
        try:
            patterns = self.window_title_patterns.get(self.browser_type, [])

            for pattern in patterns:
                windows = gw.getWindowsWithTitle(pattern)
                if windows:
                    logging.info(f"  Found window with title: {windows[0].title}")
                    return windows[0]

            logging.warning("  No window found with expected patterns")
            return None

        except Exception as e:
            logging.error(f"Error finding window: {e}")
            return None

    def _show_activity(self, message: str, duration: int = 5) -> None:
        """
        Show circular mouse movement during wait

        Args:
            message: Message to display
            duration: How long to show activity
        """
        logging.info(message)

        try:
            import math

            screen_w, screen_h = pyautogui.size()
            center_x = screen_w // 2
            center_y = screen_h // 2

            radius = 50
            points = 20
            iterations = duration  # One iteration per second

            for _ in range(iterations):
                for i in range(points):
                    angle = (2 * math.pi * i) / points
                    x = int(center_x + radius * math.cos(angle))
                    y = int(center_y + radius * math.sin(angle))

                    # Don't move if out of bounds
                    if 0 <= x < screen_w and 0 <= y < screen_h:
                        pyautogui.moveTo(x, y, duration=0.05)

                # Return to center
                pyautogui.moveTo(center_x, center_y, duration=0.1)
                time.sleep(0.5)

        except Exception as e:
            logging.debug(f"Could not show activity: {e}")


# ============ Simple Usage Example ============

def run_simple_workflow(browser_type: str = 'ix', email: str = '', password: str = '') -> bool:
    """
    Simple complete workflow

    Args:
        browser_type: 'ix' or 'gologin'
        email: Facebook email
        password: Facebook password

    Returns: True if successful
    """

    handler = SimpleBrowserHandler(browser_type)

    try:
        # Step 1: Open browser
        if not handler.open_browser():
            logging.error("Failed to open browser")
            return False

        time.sleep(2)

        # Step 2: Check login status
        status = handler.check_login_status()
        logging.info(f"Login Status: {status}")

        time.sleep(2)

        # Step 3: Handle login/logout
        if email and password:
            if status == 'LOGGED_IN':
                logging.info("\n🔄 User already logged in, logging out first...")
                handler.logout_facebook()
                time.sleep(5)

            logging.info("\n📝 Now logging in with new credentials...")
            handler.login_facebook(email, password)

        # Step 4: Keep browser open
        logging.info("\n✅ Done! Browser is ready.")
        logging.info("📌 Press Ctrl+C to close browser")

        # Keep running
        while True:
            time.sleep(1)

        return True

    except KeyboardInterrupt:
        logging.info("\n⏹️  User interrupted")
        handler.close_browser()
        return True

    except Exception as e:
        logging.error(f"Error in workflow: {e}", exc_info=True)
        handler.close_browser()
        return False


if __name__ == "__main__":
    import sys

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    # Example usage
    browser_type = 'ix'
    email = 'your_email@gmail.com'
    password = 'your_password'

    if len(sys.argv) > 1:
        email = sys.argv[1]
    if len(sys.argv) > 2:
        password = sys.argv[2]

    run_simple_workflow(browser_type, email, password)
