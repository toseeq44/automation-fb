"""
Desktop Application Launcher for NSTbrowser
Automatically launches NSTbrowser desktop app if not running
"""

import logging
import subprocess
import time
import os
from pathlib import Path
from typing import Optional
import socket

logger = logging.getLogger(__name__)


class NSTDesktopLauncher:
    """Manages NSTbrowser desktop application lifecycle."""

    # Common locations for Nstbrowser.lnk shortcut
    COMMON_SHORTCUT_PATHS = [
        # Desktop
        Path.home() / "Desktop" / "Nstbrowser.lnk",
        Path.home() / "Desktop" / "NSTbrowser.lnk",
        Path.home() / "Desktop" / "nstbrowser.lnk",

        # Public Desktop
        Path("C:/Users/Public/Desktop/Nstbrowser.lnk"),
        Path("C:/Users/Public/Desktop/NSTbrowser.lnk"),
    ]

    # Common installation paths for executable
    COMMON_EXE_PATHS = [
        Path.home() / "AppData" / "Local" / "NSTbrowser" / "Nstbrowser.exe",
        Path.home() / "AppData" / "Local" / "Programs" / "NSTbrowser" / "Nstbrowser.exe",
        Path("C:/Program Files/NSTbrowser/Nstbrowser.exe"),
        Path("C:/Program Files (x86)/NSTbrowser/Nstbrowser.exe"),
    ]

    def __init__(self, host: str = "127.0.0.1", port: int = 8848,
                 email: Optional[str] = None, password: Optional[str] = None):
        """
        Initialize desktop app launcher.

        Args:
            host: API host to check
            port: API port to check (default: 8848 for NSTbrowser)
            email: NSTbrowser login email (for future auto-login)
            password: NSTbrowser login password (for future auto-login)
        """
        self.host = host
        self.port = port
        self.email = email
        self.password = password
        self.process: Optional[subprocess.Popen] = None
        self.app_path: Optional[Path] = None

    def is_api_available(self) -> bool:
        """
        Check if NSTbrowser API is available by testing port connection.

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
            logger.debug("[NSTLauncher] Port check failed: %s", str(e))
            return False

    def find_shortcut(self) -> Optional[Path]:
        """
        Find NSTbrowser desktop shortcut.

        Returns:
            Path to shortcut if found, None otherwise
        """
        logger.info("[NSTLauncher] Searching for NSTbrowser shortcut...")

        for shortcut_path in self.COMMON_SHORTCUT_PATHS:
            if shortcut_path.exists() and shortcut_path.is_file():
                logger.info("[NSTLauncher] ✓ Found shortcut: %s", shortcut_path)
                return shortcut_path
            else:
                logger.debug("[NSTLauncher]   Not found: %s", shortcut_path)

        logger.warning("[NSTLauncher] ✗ Shortcut not found in common locations")
        return None

    def find_executable(self) -> Optional[Path]:
        """
        Find NSTbrowser executable in common installation paths.

        Returns:
            Path to executable if found, None otherwise
        """
        logger.info("[NSTLauncher] Searching for NSTbrowser executable...")

        for exe_path in self.COMMON_EXE_PATHS:
            if exe_path.exists() and exe_path.is_file():
                logger.info("[NSTLauncher] ✓ Found executable: %s", exe_path)
                return exe_path
            else:
                logger.debug("[NSTLauncher]   Not found: %s", exe_path)

        # Try to find via registry (Windows-specific)
        try:
            import winreg
            logger.debug("[NSTLauncher] Searching Windows registry...")

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
                                if "nstbrowser" in display_name.lower():
                                    try:
                                        install_location = winreg.QueryValueEx(subkey, "InstallLocation")[0]
                                        exe_path = Path(install_location) / "Nstbrowser.exe"
                                        if exe_path.exists():
                                            logger.info("[NSTLauncher] ✓ Found via registry: %s", exe_path)
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
            logger.debug("[NSTLauncher] winreg not available (not Windows)")
        except Exception as e:
            logger.debug("[NSTLauncher] Registry search error: %s", str(e))

        logger.warning("[NSTLauncher] ✗ Executable not found in common paths")
        return None

    def launch_application(self, shortcut_path: Optional[Path] = None) -> bool:
        """
        Launch NSTbrowser desktop application.

        Args:
            shortcut_path: Path to shortcut (will search if not provided)

        Returns:
            True if launched successfully
        """
        # Find shortcut if not provided
        if shortcut_path is None:
            shortcut_path = self.find_shortcut()

        # If no shortcut found, try executable
        if shortcut_path is None:
            logger.warning("[NSTLauncher] No shortcut found, trying executable...")
            exe_path = self.find_executable()
            if exe_path:
                shortcut_path = exe_path

        if shortcut_path is None:
            logger.error("[NSTLauncher] ✗ Cannot launch: Shortcut/executable not found")
            logger.error("[NSTLauncher] Please install NSTbrowser or create desktop shortcut")
            return False

        self.app_path = shortcut_path

        logger.info("[NSTLauncher] Launching NSTbrowser application...")
        logger.info("[NSTLauncher]   Path: %s", shortcut_path)

        try:
            # Launch shortcut/executable
            if shortcut_path.suffix == '.lnk':
                # Launch .lnk shortcut using Windows command
                logger.info("[NSTLauncher] Launching shortcut via os.startfile...")
                os.startfile(str(shortcut_path))
                logger.info("[NSTLauncher] ✓ Shortcut launched")
                return True
            else:
                # Launch executable directly
                logger.info("[NSTLauncher] Launching executable via subprocess...")
                self.process = subprocess.Popen(
                    [str(shortcut_path)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
                )
                logger.info("[NSTLauncher] ✓ Process started (PID: %s)", self.process.pid)
                return True

        except Exception as e:
            logger.error("[NSTLauncher] ✗ Failed to launch: %s", str(e))
            return False

    def wait_for_api(self, timeout: int = 60, check_interval: int = 2) -> bool:
        """
        Wait for NSTbrowser API to become available.

        Args:
            timeout: Maximum time to wait in seconds
            check_interval: How often to check in seconds

        Returns:
            True if API becomes available within timeout
        """
        logger.info("[NSTLauncher] Waiting for API to become available...")
        logger.info("[NSTLauncher]   Checking: %s:%s", self.host, self.port)
        logger.info("[NSTLauncher]   Timeout: %s seconds", timeout)

        start_time = time.time()
        attempts = 0

        while (time.time() - start_time) < timeout:
            attempts += 1

            if self.is_api_available():
                elapsed = time.time() - start_time
                logger.info("[NSTLauncher] ✓ API available! (took %.1f seconds, %d attempts)",
                          elapsed, attempts)
                return True

            logger.debug("[NSTLauncher]   Attempt %d: Not ready yet...", attempts)
            time.sleep(check_interval)

        logger.error("[NSTLauncher] ✗ API did not become available within %s seconds", timeout)
        return False

    def ensure_running(self, timeout: int = 60) -> bool:
        """
        Ensure NSTbrowser application is running and API is available.

        If not running, launches the application and waits for API.

        Args:
            timeout: Maximum time to wait for API

        Returns:
            True if API is available (was already running or launched successfully)
        """
        logger.info("[NSTLauncher] Checking if NSTbrowser is running...")

        # Check if already running
        if self.is_api_available():
            logger.info("[NSTLauncher] ✓ NSTbrowser already running!")
            return True

        logger.info("[NSTLauncher] ✗ NSTbrowser not running")
        logger.info("[NSTLauncher] Attempting to launch NSTbrowser...")

        # Launch application
        if not self.launch_application():
            return False

        # Wait for API to be ready
        logger.info("[NSTLauncher] Waiting for API to become available...")
        if self.wait_for_api(timeout=timeout, check_interval=2):
            logger.info("[NSTLauncher] ✓ NSTbrowser launched successfully!")
            return True

        # API not available - might need login
        logger.warning("[NSTLauncher] ⚠ API not available after launch")
        logger.warning("[NSTLauncher] Possible reasons:")
        logger.warning("[NSTLauncher]   1. NSTbrowser is logged out")
        logger.warning("[NSTLauncher]   2. Startup is taking longer than usual")
        logger.warning("[NSTLauncher]   3. Please login to NSTbrowser manually")

        # TODO: Implement auto-login helper if credentials provided
        if self.email and self.password:
            logger.info("[NSTLauncher] Auto-login feature not yet implemented")
            logger.info("[NSTLauncher] Please login to NSTbrowser manually")

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
                "app_path": str(self.app_path) if self.app_path else None
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
    print("NSTbrowser Desktop Launcher - Test Mode")
    print("="*60 + "\n")

    launcher = NSTDesktopLauncher()

    # Test 1: Check if API is available
    print("Test 1: Checking if API is available...")
    if launcher.is_api_available():
        print("✓ API is already available!")
    else:
        print("✗ API is not available")

    # Test 2: Find shortcut
    print("\nTest 2: Finding NSTbrowser shortcut...")
    shortcut_path = launcher.find_shortcut()
    if shortcut_path:
        print(f"✓ Found: {shortcut_path}")
    else:
        print("✗ Not found")

    # Test 3: Ensure running
    print("\nTest 3: Ensuring NSTbrowser is running...")
    if launcher.ensure_running(timeout=60):
        print("✓ NSTbrowser is running!")

        # Show process info
        info = launcher.get_process_info()
        if info.get("running"):
            print("\nProcess Info:")
            for key, value in info.items():
                print(f"  {key}: {value}")
    else:
        print("✗ Failed to start NSTbrowser")
