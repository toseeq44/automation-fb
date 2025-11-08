"""
Selenium Connector
==================
Connects Selenium WebDriver to existing browser via debugging port.

Features:
- Connect to browser opened by IX API
- Attach to existing session (no new browser window)
- Detailed logging for debugging
- Error handling and recovery

How It Works:
1. IX API opens browser → Returns debugging address (e.g., localhost:9222)
2. Selenium connects to that address
3. Automation starts on existing browser

Example:
    >>> connector = SeleniumConnector()
    >>> driver = connector.connect("localhost:9222")
    >>> driver.get("https://facebook.com")
"""
import logging
from typing import Optional


# Try to import Selenium
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.common.exceptions import WebDriverException
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    logging.warning("⚠️  Selenium not installed")


class SeleniumConnectionError(Exception):
    """Selenium connection failed"""
    pass


class SeleniumConnector:
    """
    Connect Selenium to existing browser

    Uses Chrome DevTools Protocol (CDP) to attach to
    browser that was opened by IX Browser API.
    """

    def __init__(self):
        """Initialize Selenium connector"""
        logging.info("="*60)
        logging.info("SELENIUM CONNECTOR INITIALIZATION")
        logging.info("="*60)

        if not SELENIUM_AVAILABLE:
            logging.error("❌ Selenium not available")
            logging.error("   Install with: pip install selenium")
            logging.info("="*60)
            raise ImportError("Selenium not installed")

        logging.info("✅ Selenium available")
        logging.info("="*60)
        logging.info("")

    def connect(
        self,
        debugging_address: str,
        headless: bool = False
    ) -> Optional[webdriver.Chrome]:
        """
        Connect to browser via debugging port

        Args:
            debugging_address: Debug address from API (e.g., "localhost:9222")
            headless: Run in headless mode (default: False)

        Returns:
            WebDriver instance

        Raises:
            SeleniumConnectionError: Connection failed

        Example:
            >>> connector = SeleniumConnector()
            >>> driver = connector.connect("localhost:9222")
            >>> driver.get("https://facebook.com")
            >>> print(driver.title)
        """
        logging.info("")
        logging.info("="*60)
        logging.info("CONNECTING SELENIUM TO BROWSER")
        logging.info("="*60)
        logging.info(f"📋 Debugging Address: {debugging_address}")
        logging.info(f"📋 Headless Mode: {headless}")

        try:
            logging.info("")
            logging.info("🔧 Step 1/3: Configuring Chrome options...")

            options = Options()

            # Connect to existing browser (most important setting)
            options.debugger_address = debugging_address
            logging.info(f"   ✓ Debugger address set: {debugging_address}")

            # Don't close browser when driver quits
            options.add_experimental_option("detach", True)
            logging.info("   ✓ Detach mode enabled")

            if headless:
                options.add_argument("--headless")
                logging.info("   ✓ Headless mode enabled")

            # Additional options for stability
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-blink-features=AutomationControlled")
            logging.info("   ✓ Stability options added")

            # Exclude automation switches (anti-detection)
            options.add_experimental_option(
                "excludeSwitches",
                ["enable-automation"]
            )
            options.add_experimental_option(
                "useAutomationExtension",
                False
            )
            logging.info("   ✓ Anti-detection options added")

            logging.info("")
            logging.info("🔧 Step 2/3: Creating WebDriver instance...")

            driver = webdriver.Chrome(options=options)

            logging.info("   ✓ WebDriver created successfully")

            logging.info("")
            logging.info("🔧 Step 3/3: Verifying connection...")

            # Try to get current URL to verify connection
            try:
                current_url = driver.current_url
                logging.info(f"   ✓ Current URL: {current_url}")

                # Get window handles count
                handles = driver.window_handles
                logging.info(f"   ✓ Window handles: {len(handles)}")

                # Get title if available
                try:
                    title = driver.title
                    if title:
                        logging.info(f"   ✓ Page title: {title}")
                except:
                    logging.info("   ℹ️  Page title not available yet")

            except Exception as verify_error:
                logging.warning(f"   ⚠️  Could not verify: {verify_error}")
                # Continue anyway - connection might still work

            logging.info("")
            logging.info("✅ SELENIUM CONNECTED SUCCESSFULLY!")
            logging.info("="*60)
            logging.info("")

            return driver

        except WebDriverException as e:
            logging.error("")
            logging.error("❌ SELENIUM CONNECTION FAILED")
            logging.error("="*60)
            logging.error(f"Error: {e}")
            logging.error("")
            logging.error("POSSIBLE CAUSES:")
            logging.error("1. ChromeDriver not installed or not in PATH")
            logging.error("2. Debugging address incorrect")
            logging.error("3. Browser closed before connection")
            logging.error("4. Chrome/Chromium not compatible with ChromeDriver")
            logging.error("")
            logging.error("HOW TO FIX:")
            logging.error("1. Install ChromeDriver:")
            logging.error("   - Download from: https://chromedriver.chromium.org/")
            logging.error("   - Add to system PATH")
            logging.error("2. Verify debugging address format (localhost:PORT)")
            logging.error("3. Ensure browser is running before connecting")
            logging.error("="*60)

            raise SeleniumConnectionError(f"Failed to connect: {e}")

        except Exception as e:
            logging.error("")
            logging.error("❌ UNEXPECTED ERROR")
            logging.error("="*60)
            logging.error(f"Error: {e}", exc_info=True)
            logging.error("="*60)

            raise SeleniumConnectionError(f"Unexpected error: {e}")

    def disconnect(self, driver: webdriver.Chrome) -> None:
        """
        Disconnect Selenium (quit driver)

        Args:
            driver: WebDriver instance to quit

        Note:
            This quits the driver but browser stays open
            because we used detach=True option.
        """
        if not driver:
            logging.info("No driver to disconnect")
            return

        logging.info("")
        logging.info("="*60)
        logging.info("DISCONNECTING SELENIUM")
        logging.info("="*60)

        try:
            driver.quit()
            logging.info("✅ Selenium disconnected")
            logging.info("ℹ️  Note: Browser window remains open (detach mode)")
            logging.info("="*60)
            logging.info("")

        except Exception as e:
            logging.warning(f"⚠️  Error during disconnect: {e}")
            logging.info("="*60)
            logging.info("")

    def is_connected(self, driver: Optional[webdriver.Chrome]) -> bool:
        """
        Check if driver is still connected

        Args:
            driver: WebDriver instance

        Returns:
            True if connected and responsive
        """
        if not driver:
            return False

        try:
            # Try to get current URL - if this works, driver is connected
            _ = driver.current_url
            return True
        except:
            return False
