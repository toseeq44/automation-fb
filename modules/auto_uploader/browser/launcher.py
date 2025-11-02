"""
Browser Launcher
================
Handles browser launching operations for GoLogin, Incogniton, and generic browsers.

This module provides methods to:
- Desktop-based browser search (.lnk files)
- Launch different browser types
- Check if browser is running
- Kill browser processes
- PyQt5 download popup if browser not found
"""

import os
import logging
import subprocess
import platform
import time
import psutil
from pathlib import Path
from typing import Optional, Dict, Any, List

try:
    from PyQt5.QtWidgets import QMessageBox, QApplication
    from PyQt5.QtCore import Qt
    PYQT5_AVAILABLE = True
except ImportError:
    PYQT5_AVAILABLE = False
    logging.warning("PyQt5 not available. Download popup will not work.")


class BrowserLauncher:
    """Launches and manages anti-detect browsers."""

    # Browser-specific process names
    BROWSER_PROCESSES = {
        'gologin': ['orbita.exe', 'GoLogin.exe', 'gologin'],
        'ix': ['chrome.exe', 'incogniton', 'ix'],
        'chrome': ['chrome.exe', 'google-chrome', 'chromium']
    }

    # Browser download URLs
    DOWNLOAD_URLS = {
        'gologin': 'https://gologin.com/download',
        'ix': 'https://incogniton.com/download'
    }

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize browser launcher.

        Args:
            config: Configuration dictionary with browser settings
        """
        self.config = config or {}
        self.platform = platform.system()
        self.active_processes = {}

        # Get desktop path
        self.desktop_path = self._get_desktop_path()

        logging.debug("BrowserLauncher initialized for platform: %s", self.platform)
        logging.debug("Desktop path: %s", self.desktop_path)

    def find_browser_on_desktop(self, browser_name: str) -> Optional[Path]:
        """
        Search for browser shortcut on desktop.

        Args:
            browser_name: Name of browser to search for (case-insensitive)

        Returns:
            Path to shortcut if found, None otherwise

        Example:
            >>> launcher = BrowserLauncher()
            >>> gologin_path = launcher.find_browser_on_desktop('gologin')
        """
        logging.info("Searching desktop for '%s' browser shortcut...", browser_name)

        if not self.desktop_path or not self.desktop_path.exists():
            logging.warning("Desktop path not found: %s", self.desktop_path)
            return None

        try:
            # Search for .lnk files containing browser name
            for file_path in self.desktop_path.iterdir():
                if file_path.suffix.lower() == '.lnk':
                    if browser_name.lower() in file_path.stem.lower():
                        logging.info("Found browser shortcut: %s", file_path)
                        return file_path

            logging.warning("Browser shortcut '%s' not found on desktop", browser_name)
            return None

        except Exception as e:
            logging.error("Error searching desktop: %s", e, exc_info=True)
            return None

    def show_download_popup(self, browser_type: str) -> bool:
        """
        Show PyQt5 popup with download option if browser not found.

        Args:
            browser_type: Type of browser (gologin, ix, etc.)

        Returns:
            True if user clicked download, False otherwise
        """
        if not PYQT5_AVAILABLE:
            logging.error("PyQt5 not available, cannot show download popup")
            return False

        logging.info("Showing download popup for %s", browser_type)

        try:
            # Create QApplication if it doesn't exist
            app = QApplication.instance()
            if app is None:
                app = QApplication([])

            # Create message box
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Warning)
            msg_box.setWindowTitle(f"{browser_type.upper()} Not Found")
            msg_box.setText(f"{browser_type.upper()} browser was not found on your desktop.")
            msg_box.setInformativeText("Would you like to download it?")

            # Add buttons
            download_btn = msg_box.addButton("Download", QMessageBox.AcceptRole)
            cancel_btn = msg_box.addButton("Cancel", QMessageBox.RejectRole)

            msg_box.setDefaultButton(download_btn)
            msg_box.exec_()

            if msg_box.clickedButton() == download_btn:
                logging.info("User chose to download %s", browser_type)
                # Open download URL
                download_url = self.DOWNLOAD_URLS.get(browser_type.lower())
                if download_url:
                    import webbrowser
                    webbrowser.open(download_url)
                return True
            else:
                logging.info("User cancelled download")
                return False

        except Exception as e:
            logging.error("Error showing download popup: %s", e, exc_info=True)
            return False

    def launch_gologin(self, **kwargs) -> bool:
        """
        Launch GoLogin browser from desktop shortcut.

        Args:
            **kwargs: Additional launch parameters
                - desktop_shortcut: Path to desktop shortcut (auto-detected if None)
                - startup_wait: Wait time after launch (default: 10 seconds)
                - show_popup: Show download popup if not found (default: True)

        Returns:
            True if launched successfully, False otherwise

        Example:
            >>> launcher = BrowserLauncher()
            >>> launcher.launch_gologin(startup_wait=15)
        """
        logging.info("Launching GoLogin browser...")

        # Check if already running
        if self.is_browser_running('gologin'):
            logging.info("GoLogin is already running")
            return True

        # Get shortcut path
        shortcut_path = kwargs.get('desktop_shortcut')
        if not shortcut_path:
            shortcut_path = self.find_browser_on_desktop('gologin')

        if not shortcut_path:
            logging.warning("GoLogin shortcut not found on desktop")
            if kwargs.get('show_popup', True):
                self.show_download_popup('gologin')
            return False

        # Launch browser
        success = self.launch_from_shortcut(shortcut_path, **kwargs)

        if success:
            # Wait for startup
            startup_wait = kwargs.get('startup_wait', 10)
            logging.info("Waiting %ds for GoLogin to start...", startup_wait)
            time.sleep(startup_wait)

            # Verify it's running
            if self.is_browser_running('gologin'):
                logging.info("GoLogin launched successfully")
                return True
            else:
                logging.warning("GoLogin process not detected after launch")
                return False

        return False

    def launch_incogniton(self, **kwargs) -> bool:
        """
        Launch Incogniton (IX) browser from desktop shortcut.

        Args:
            **kwargs: Additional launch parameters

        Returns:
            True if launched successfully, False otherwise
        """
        logging.info("Launching Incogniton browser...")

        # Check if already running
        if self.is_browser_running('ix'):
            logging.info("Incogniton is already running")
            return True

        # Get shortcut path
        shortcut_path = kwargs.get('desktop_shortcut')
        if not shortcut_path:
            shortcut_path = self.find_browser_on_desktop('incogniton')

        if not shortcut_path:
            logging.warning("Incogniton shortcut not found on desktop")
            if kwargs.get('show_popup', True):
                self.show_download_popup('ix')
            return False

        # Launch browser
        success = self.launch_from_shortcut(shortcut_path, **kwargs)

        if success:
            # Wait for startup
            startup_wait = kwargs.get('startup_wait', 10)
            time.sleep(startup_wait)

            if self.is_browser_running('ix'):
                logging.info("Incogniton launched successfully")
                return True

        return False

    def launch_generic(self, browser_type: str, **kwargs) -> bool:
        """
        Launch a generic browser by type.

        Args:
            browser_type: Browser type identifier (gologin, ix, chrome, etc.)
            **kwargs: Additional launch parameters

        Returns:
            True if launched successfully, False otherwise
        """
        logging.info("Launching browser: %s", browser_type)

        browser_type_lower = browser_type.lower()

        if browser_type_lower == 'gologin':
            return self.launch_gologin(**kwargs)
        elif browser_type_lower in ['ix', 'incogniton']:
            return self.launch_incogniton(**kwargs)
        else:
            logging.warning("Unknown browser type: %s", browser_type)
            return False

    def launch_from_exe(self, exe_path: str, **kwargs) -> bool:
        """
        Launch browser from executable path.

        Args:
            exe_path: Path to browser executable
            **kwargs: Additional parameters

        Returns:
            True if launched successfully
        """
        logging.info("Launching from exe: %s", exe_path)

        try:
            if self.platform == 'Windows':
                # Windows: use os.startfile
                os.startfile(exe_path)
            else:
                # Linux/Mac: use subprocess
                subprocess.Popen([exe_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            logging.info("Browser launched from exe")
            return True

        except Exception as e:
            logging.error("Error launching from exe: %s", e, exc_info=True)
            return False

    def launch_from_shortcut(self, shortcut_path: Path, **kwargs) -> bool:
        """
        Launch browser from desktop shortcut (.lnk file).

        Args:
            shortcut_path: Path to shortcut file
            **kwargs: Additional parameters

        Returns:
            True if launched successfully
        """
        logging.info("Launching from shortcut: %s", shortcut_path)

        try:
            if self.platform == 'Windows':
                # Windows: use os.startfile for .lnk files
                os.startfile(str(shortcut_path))
            else:
                # Linux/Mac: resolve symlink and execute
                resolved_path = shortcut_path.resolve()
                subprocess.Popen([str(resolved_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            logging.info("Browser launched from shortcut")
            return True

        except Exception as e:
            logging.error("Error launching from shortcut: %s", e, exc_info=True)
            return False

    def is_browser_running(self, browser_type: str) -> bool:
        """
        Check if a specific browser is currently running.

        Args:
            browser_type: Browser type to check

        Returns:
            True if browser is running, False otherwise

        Example:
            >>> launcher = BrowserLauncher()
            >>> if launcher.is_browser_running('gologin'):
            >>>     print("GoLogin is running")
        """
        logging.debug("Checking if %s is running...", browser_type)

        process_names = self.BROWSER_PROCESSES.get(browser_type.lower(), [])

        try:
            for proc in psutil.process_iter(['name']):
                proc_name = proc.info['name']
                if proc_name and any(name.lower() in proc_name.lower() for name in process_names):
                    logging.debug("Found %s process: %s", browser_type, proc_name)
                    return True

            return False

        except Exception as e:
            logging.error("Error checking if browser running: %s", e, exc_info=True)
            return False

    def get_browser_process(self, browser_type: str) -> Optional[psutil.Process]:
        """
        Get the process object for a running browser.

        Args:
            browser_type: Browser type

        Returns:
            Process object if found, None otherwise
        """
        logging.debug("Getting process for %s", browser_type)

        process_names = self.BROWSER_PROCESSES.get(browser_type.lower(), [])

        try:
            for proc in psutil.process_iter(['name', 'pid']):
                proc_name = proc.info['name']
                if proc_name and any(name.lower() in proc_name.lower() for name in process_names):
                    logging.debug("Found %s process: PID=%d, Name=%s", browser_type, proc.info['pid'], proc_name)
                    return proc

            return None

        except Exception as e:
            logging.error("Error getting browser process: %s", e, exc_info=True)
            return None

    def kill_browser(self, browser_type: str, force: bool = False) -> bool:
        """
        Kill a running browser process.

        Args:
            browser_type: Browser type to kill
            force: Force kill if True

        Returns:
            True if killed successfully
        """
        logging.info("Killing browser: %s (force=%s)", browser_type, force)

        proc = self.get_browser_process(browser_type)
        if not proc:
            logging.warning("Browser process not found: %s", browser_type)
            return False

        try:
            if force:
                proc.kill()  # SIGKILL
            else:
                proc.terminate()  # SIGTERM

            # Wait for process to end
            proc.wait(timeout=5)

            logging.info("Browser killed: %s", browser_type)
            return True

        except psutil.TimeoutExpired:
            logging.warning("Browser did not terminate within timeout, force killing...")
            proc.kill()
            return True

        except Exception as e:
            logging.error("Error killing browser: %s", e, exc_info=True)
            return False

    def kill_all_browsers(self) -> int:
        """
        Kill all active browser processes.

        Returns:
            Number of browsers killed
        """
        logging.info("Killing all active browsers...")

        killed_count = 0

        for browser_type in self.BROWSER_PROCESSES.keys():
            if self.is_browser_running(browser_type):
                if self.kill_browser(browser_type, force=True):
                    killed_count += 1

        logging.info("Killed %d browser(s)", killed_count)
        return killed_count

    def restart_browser(self, browser_type: str, **kwargs) -> bool:
        """
        Restart a browser (kill and relaunch).

        Args:
            browser_type: Browser to restart
            **kwargs: Launch parameters

        Returns:
            True if restarted successfully
        """
        logging.info("Restarting browser: %s", browser_type)

        # Kill if running
        if self.is_browser_running(browser_type):
            self.kill_browser(browser_type, force=True)
            time.sleep(2)

        # Relaunch
        return self.launch_generic(browser_type, **kwargs)

    def get_browser_info(self, browser_type: str) -> Dict[str, Any]:
        """
        Get information about a browser.

        Args:
            browser_type: Browser type

        Returns:
            Dictionary with browser information (PID, status, etc.)
        """
        logging.debug("Getting info for %s", browser_type)

        info = {
            'browser_type': browser_type,
            'running': False,
            'pid': None,
            'name': None,
            'memory_mb': None
        }

        proc = self.get_browser_process(browser_type)
        if proc:
            try:
                info['running'] = True
                info['pid'] = proc.pid
                info['name'] = proc.name()
                info['memory_mb'] = proc.memory_info().rss / (1024 * 1024)  # Convert to MB
            except Exception as e:
                logging.error("Error getting browser info: %s", e)

        return info

    def _get_desktop_path(self) -> Optional[Path]:
        """
        Get path to user's desktop.

        Returns:
            Path to desktop or None if not found
        """
        if self.platform == 'Windows':
            desktop = Path.home() / 'Desktop'
        elif self.platform == 'Darwin':  # macOS
            desktop = Path.home() / 'Desktop'
        else:  # Linux
            desktop = Path.home() / 'Desktop'

        if desktop.exists():
            return desktop

        logging.warning("Desktop path not found: %s", desktop)
        return None

    def _resolve_exe_path(self, browser_type: str) -> Optional[str]:
        """
        Resolve executable path for browser type.

        Args:
            browser_type: Browser type

        Returns:
            Resolved exe path or None
        """
        # Check config first
        exe_path = self.config.get(f'{browser_type}_exe_path')
        if exe_path and Path(exe_path).exists():
            return exe_path

        # Platform-specific default paths
        if self.platform == 'Windows':
            if browser_type == 'gologin':
                default_paths = [
                    Path.home() / 'AppData' / 'Local' / 'GoLogin' / 'app' / 'orbita.exe',
                    Path('C:/Program Files/GoLogin/orbita.exe')
                ]
            elif browser_type == 'ix':
                default_paths = [
                    Path.home() / 'AppData' / 'Local' / 'Incogniton' / 'chrome.exe'
                ]
            else:
                return None

            for path in default_paths:
                if path.exists():
                    return str(path)

        return None

    def _wait_for_startup(self, browser_type: str, timeout: int = 15) -> bool:
        """
        Wait for browser to fully start.

        Args:
            browser_type: Browser type
            timeout: Maximum wait time in seconds

        Returns:
            True if browser started within timeout
        """
        logging.debug("Waiting for %s to start (timeout: %ds)", browser_type, timeout)

        start_time = time.time()

        while time.time() - start_time < timeout:
            if self.is_browser_running(browser_type):
                logging.debug("Browser started successfully")
                return True

            time.sleep(1)

        logging.warning("Browser did not start within timeout")
        return False
