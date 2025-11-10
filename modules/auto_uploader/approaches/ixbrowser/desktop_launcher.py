"""
Desktop Application Launcher for ixBrowser
Automatically launches ixBrowser desktop app if not running
"""

import logging
import subprocess
import time
from pathlib import Path
from typing import Optional, List
import socket

logger = logging.getLogger(__name__)


class DesktopAppLauncher:
    """Manages ixBrowser desktop application lifecycle."""

    # Common installation paths for ixBrowser on Windows
    COMMON_PATHS = [
        # User-specific installations
        Path.home() / "AppData" / "Local" / "ixBrowser" / "ixBrowser.exe",
        Path.home() / "AppData" / "Local" / "Programs" / "ixBrowser" / "ixBrowser.exe",
        Path.home() / "AppData" / "Roaming" / "ixBrowser" / "ixBrowser.exe",

        # System-wide installations
        Path("C:/Program Files/ixBrowser/ixBrowser.exe"),
        Path("C:/Program Files (x86)/ixBrowser/ixBrowser.exe"),

        # Alternative names
        Path.home() / "AppData" / "Local" / "Incogniton" / "Incogniton.exe",
        Path.home() / "AppData" / "Local" / "Programs" / "Incogniton" / "Incogniton.exe",
        Path("C:/Program Files/Incogniton/Incogniton.exe"),
        Path("C:/Program Files (x86)/Incogniton/Incogniton.exe"),
    ]

    def __init__(self, host: str = "127.0.0.1", port: int = 53200,
                 email: Optional[str] = None, password: Optional[str] = None):
        """
        Initialize desktop app launcher.

        Args:
            host: API host to check
            port: API port to check
            email: ixBrowser login email (for auto-login)
            password: ixBrowser login password (for auto-login)
        """
        self.host = host
        self.port = port
        self.email = email
        self.password = password
        self.process: Optional[subprocess.Popen] = None
        self.app_path: Optional[Path] = None

    def is_api_available(self) -> bool:
        """
        Check if ixBrowser API is available by testing port connection.

        Returns:
            True if API is reachable
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((self.host, self.port))
            sock.close()
            return result == 0
        except Exception as e:
            logger.debug("[DesktopLauncher] Port check failed: %s", str(e))
            return False

    def find_executable(self) -> Optional[Path]:
        """
        Find ixBrowser executable in common installation paths.

        Returns:
            Path to executable if found, None otherwise
        """
        logger.info("[DesktopLauncher] Searching for ixBrowser executable...")

        # Check common paths
        for path in self.COMMON_PATHS:
            if path.exists() and path.is_file():
                logger.info("[DesktopLauncher] ✓ Found executable: %s", path)
                return path
            else:
                logger.debug("[DesktopLauncher]   Not found: %s", path)

        # Try to find via registry (Windows-specific)
        try:
            import winreg
            logger.debug("[DesktopLauncher] Searching Windows registry...")

            # Check uninstall registry entries
            registry_paths = [
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
                r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"
            ]

            for reg_path in registry_paths:
                try:
                    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path)
                    i = 0
                    while True:
                        try:
                            subkey_name = winreg.EnumKey(key, i)
                            subkey = winreg.OpenKey(key, subkey_name)

                            try:
                                display_name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                                if "ixbrowser" in display_name.lower() or "incogniton" in display_name.lower():
                                    try:
                                        install_location = winreg.QueryValueEx(subkey, "InstallLocation")[0]
                                        exe_path = Path(install_location) / "ixBrowser.exe"
                                        if exe_path.exists():
                                            logger.info("[DesktopLauncher] ✓ Found via registry: %s", exe_path)
                                            return exe_path

                                        # Try Incogniton.exe
                                        exe_path = Path(install_location) / "Incogniton.exe"
                                        if exe_path.exists():
                                            logger.info("[DesktopLauncher] ✓ Found via registry: %s", exe_path)
                                            return exe_path
                                    except:
                                        pass
                            except:
                                pass

                            winreg.CloseKey(subkey)
                            i += 1
                        except OSError:
                            break

                    winreg.CloseKey(key)
                except:
                    pass
        except ImportError:
            logger.debug("[DesktopLauncher] winreg not available (not Windows)")
        except Exception as e:
            logger.debug("[DesktopLauncher] Registry search error: %s", str(e))

        logger.warning("[DesktopLauncher] ✗ Executable not found in common paths")
        return None

    def launch_application(self, exe_path: Optional[Path] = None) -> bool:
        """
        Launch ixBrowser desktop application.

        Args:
            exe_path: Path to executable (will search if not provided)

        Returns:
            True if launched successfully
        """
        # Find executable if not provided
        if exe_path is None:
            exe_path = self.find_executable()

        if exe_path is None:
            logger.error("[DesktopLauncher] ✗ Cannot launch: Executable not found")
            logger.error("[DesktopLauncher] Please install ixBrowser or provide path manually")
            return False

        self.app_path = exe_path

        logger.info("[DesktopLauncher] Launching ixBrowser application...")
        logger.info("[DesktopLauncher]   Executable: %s", exe_path)

        try:
            # Launch process in background
            self.process = subprocess.Popen(
                [str(exe_path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )

            logger.info("[DesktopLauncher] ✓ Process started (PID: %s)", self.process.pid)
            return True

        except Exception as e:
            logger.error("[DesktopLauncher] ✗ Failed to launch: %s", str(e))
            return False

    def wait_for_api(self, timeout: int = 60, check_interval: int = 2) -> bool:
        """
        Wait for ixBrowser API to become available.

        Args:
            timeout: Maximum time to wait in seconds
            check_interval: How often to check in seconds

        Returns:
            True if API becomes available within timeout
        """
        logger.info("[DesktopLauncher] Waiting for API to become available...")
        logger.info("[DesktopLauncher]   Checking: %s:%s", self.host, self.port)
        logger.info("[DesktopLauncher]   Timeout: %s seconds", timeout)

        start_time = time.time()
        attempts = 0

        while (time.time() - start_time) < timeout:
            attempts += 1

            if self.is_api_available():
                elapsed = time.time() - start_time
                logger.info("[DesktopLauncher] ✓ API available! (took %.1f seconds, %d attempts)",
                          elapsed, attempts)
                return True

            logger.debug("[DesktopLauncher]   Attempt %d: Not ready yet...", attempts)
            time.sleep(check_interval)

        logger.error("[DesktopLauncher] ✗ API did not become available within %s seconds", timeout)
        return False

    def ensure_running(self, timeout: int = 60) -> bool:
        """
        Ensure ixBrowser application is running and API is available.

        If not running, launches the application and waits for API.
        If API doesn't become available, attempts auto-login if credentials provided.

        Args:
            timeout: Maximum time to wait for API

        Returns:
            True if API is available (was already running or launched successfully)
        """
        logger.info("[DesktopLauncher] Checking if ixBrowser is running...")

        # Check if already running
        if self.is_api_available():
            logger.info("[DesktopLauncher] ✓ ixBrowser already running!")
            return True

        logger.info("[DesktopLauncher] ✗ ixBrowser not running")
        logger.info("[DesktopLauncher] Attempting to launch ixBrowser...")

        # Launch application
        if not self.launch_application():
            return False

        # Wait for API to be ready (initial attempt - 20 seconds with 2 sec interval)
        logger.info("[DesktopLauncher] Initial API check (20 seconds)...")
        if self.wait_for_api(timeout=20, check_interval=2):
            logger.info("[DesktopLauncher] ✓ ixBrowser launched successfully!")
            return True

        # API not available - might need login
        logger.warning("[DesktopLauncher] ⚠ API not available after launch")
        logger.warning("[DesktopLauncher] Possible reasons:")
        logger.warning("[DesktopLauncher]   1. ixBrowser is logged out")
        logger.warning("[DesktopLauncher]   2. Startup is taking longer than usual")

        # Try auto-login if credentials provided
        if self.email and self.password:
            logger.info("[DesktopLauncher] ═══════════════════════════════════════════")
            logger.info("[DesktopLauncher] Attempting Auto-Login")
            logger.info("[DesktopLauncher] ═══════════════════════════════════════════")

            try:
                from .ix_login_helper import IXBrowserLoginHelper

                login_helper = IXBrowserLoginHelper(self.email, self.password)

                if login_helper.perform_login():
                    logger.info("[DesktopLauncher] ✓ Login sequence completed")
                    logger.info("[DesktopLauncher] Waiting for API (checking every 7 seconds)...")

                    # Retry API check with 7-second intervals
                    remaining_timeout = max(timeout - 20, 30)  # At least 30 more seconds
                    if self.wait_for_api(timeout=remaining_timeout, check_interval=7):
                        logger.info("[DesktopLauncher] ✓ ixBrowser ready after login!")
                        return True
                    else:
                        logger.error("[DesktopLauncher] ✗ API still not available after login")
                        logger.error("[DesktopLauncher] Please check:")
                        logger.error("[DesktopLauncher]   - Login credentials are correct")
                        logger.error("[DesktopLauncher]   - ixBrowser accepted the login")
                        logger.error("[DesktopLauncher]   - No popup blocking API startup")
                        return False
                else:
                    logger.error("[DesktopLauncher] ✗ Auto-login failed")
                    return False

            except Exception as e:
                logger.error("[DesktopLauncher] Auto-login error: %s", str(e))
                return False
        else:
            logger.error("[DesktopLauncher] ✗ No credentials provided for auto-login")
            logger.error("[DesktopLauncher] Please either:")
            logger.error("[DesktopLauncher]   1. Login to ixBrowser manually, or")
            logger.error("[DesktopLauncher]   2. Provide email/password for auto-login")
            return False

    def get_process_info(self) -> dict:
        """
        Get information about the launched process.

        Returns:
            Dictionary with process information
        """
        if self.process is None:
            return {"running": False}

        try:
            poll = self.process.poll()
            return {
                "running": poll is None,
                "pid": self.process.pid,
                "returncode": poll,
                "exe_path": str(self.app_path) if self.app_path else None
            }
        except Exception as e:
            return {"running": False, "error": str(e)}


if __name__ == "__main__":
    # Test mode
    logging.basicConfig(
        level=logging.INFO,
        format='%(message)s'
    )

    print("\n" + "="*60)
    print("ixBrowser Desktop Launcher - Test Mode")
    print("="*60 + "\n")

    launcher = DesktopAppLauncher()

    # Test 1: Check if API is available
    print("Test 1: Checking if API is available...")
    if launcher.is_api_available():
        print("✓ API is already available!")
    else:
        print("✗ API is not available")

    # Test 2: Find executable
    print("\nTest 2: Finding ixBrowser executable...")
    exe_path = launcher.find_executable()
    if exe_path:
        print(f"✓ Found: {exe_path}")
    else:
        print("✗ Not found")

    # Test 3: Ensure running
    print("\nTest 3: Ensuring ixBrowser is running...")
    if launcher.ensure_running(timeout=30):
        print("✓ ixBrowser is running!")

        # Show process info
        info = launcher.get_process_info()
        print("\nProcess Info:")
        for key, value in info.items():
            print(f"  {key}: {value}")
    else:
        print("✗ Failed to start ixBrowser")
