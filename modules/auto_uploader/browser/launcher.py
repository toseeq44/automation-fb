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
import csv
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any, List


@dataclass(frozen=True)
class ProcessEntry:
    """Lightweight representation of a running process."""

    pid: int
    name: str

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
    # Note: IX is a Chrome-based browser, but we check for IX-specific processes first
    # chrome.exe is a fallback only if no IX-specific processes are found
    BROWSER_PROCESSES = {
        'gologin': ['orbita.exe', 'gologin.exe', 'GoLogin.exe', 'gologin'],
        'ix': ['ixbrowser.exe', 'incogniton.exe', 'Incogniton.exe', 'ixbrowser', 'incogniton', 'chrome.exe'],
        'chrome': ['chrome.exe', 'google-chrome', 'chromium']
    }

    BROWSER_ALIASES = {
        'gologin': 'gologin',
        'orbita': 'gologin',
        'gologinbrowser': 'gologin',
        'ix': 'ix',
        'ixbrowser': 'ix',
        'incogniton': 'ix',
        'incognitonbrowser': 'ix',
        'chrome': 'chrome',
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
        logging.info("🔍 [DESKTOP SEARCH] Searching for '%s' browser shortcut...", browser_name.upper())

        if not self.desktop_path or not self.desktop_path.exists():
            logging.error("❌ [DESKTOP SEARCH] Desktop path doesn't exist: %s", self.desktop_path)
            return None

        try:
            # List all files on desktop first for debugging
            desktop_files = list(self.desktop_path.iterdir())
            shortcut_files = [f for f in desktop_files if f.suffix.lower() == '.lnk']

            logging.debug("   📁 Desktop path: %s", self.desktop_path)
            logging.debug("   📊 Total files on desktop: %d", len(desktop_files))
            logging.debug("   🔗 Shortcut files found: %d", len(shortcut_files))

            if shortcut_files:
                logging.debug("   📋 Available shortcuts:")
                for f in shortcut_files:
                    logging.debug("      → %s", f.name)
            else:
                logging.warning("   ⚠️  NO shortcut files (.lnk) found on desktop!")

            # Search for .lnk files containing browser name
            search_target = browser_name.lower()
            logging.debug("   🎯 Searching for keyword: '%s'", search_target)

            for file_path in shortcut_files:
                file_stem_lower = file_path.stem.lower()
                logging.debug("   ✓ Checking: %s (stem: '%s')", file_path.name, file_stem_lower)

                if search_target in file_stem_lower:
                    logging.info("   ✅ [FOUND] Browser shortcut: %s", file_path.name)
                    logging.info("   📌 Full path: %s", file_path)
                    return file_path
                else:
                    logging.debug("      (no match: '%s' not in '%s')", search_target, file_stem_lower)

            logging.error("   ❌ [NOT FOUND] Browser shortcut for '%s' not found on desktop", browser_name)
            logging.error("   💡 Expected filename pattern: *%s*.lnk (case-insensitive)", browser_name.lower())
            return None

        except Exception as e:
            logging.error("   ❌ [ERROR] Error searching desktop: %s", e, exc_info=True)
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

        logging.info("Browser '%s' not found on desktop", browser_type)

        try:
            # Check if event loop is already running
            from PyQt5.QtCore import QCoreApplication
            app = QApplication.instance()

            # If running from GUI (event loop already exists), just log and return
            if app is not None and isinstance(QCoreApplication.instance(), QCoreApplication):
                logging.warning("PyQt5 event loop already running, skipping popup")
                logging.warning("Please install %s browser manually", browser_type.upper())
                logging.warning("Download URL: %s", self.DOWNLOAD_URLS.get(browser_type.lower(), 'N/A'))
                return False

            # Only show popup if NOT running from GUI
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

            # Use exec_() only if we created the app (not running from GUI)
            result = msg_box.exec_()

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
        logging.info("="*60)
        logging.info("🚀 [GOLOGIN] Starting GoLogin browser launch sequence")
        logging.info("="*60)

        # Check if already running
        logging.info("⚙️  [GOLOGIN] Step 1/4: Checking if GoLogin is already running...")
        if self.is_browser_running('gologin'):
            logging.info("   ✅ [GOLOGIN] GoLogin is already running - skipping launch")
            return True

        # Get shortcut path
        logging.info("⚙️  [GOLOGIN] Step 2/4: Searching for GoLogin shortcut on desktop...")

        # Prioritize browser_name from login_data.txt if provided
        browser_name_hint = kwargs.get('browser_name')
        if browser_name_hint:
            logging.info("   Using browser name from login_data.txt: %s", browser_name_hint)
            shortcut_path = self.find_browser_on_desktop(browser_name_hint)
        else:
            # Fall back to hardcoded desktop_shortcut or default search
            shortcut_path = kwargs.get('desktop_shortcut')
            if not shortcut_path:
                logging.info("   Using default browser name: gologin")
                shortcut_path = self.find_browser_on_desktop('gologin')

        if not shortcut_path:
            logging.error("   ❌ [GOLOGIN] GoLogin shortcut not found on desktop!")
            logging.error("   💡 Please create a shortcut to GoLogin on your desktop")
            if kwargs.get('show_popup', True):
                logging.info("   📋 Attempting to show download popup...")
                self.show_download_popup('gologin')
            return False

        # Launch browser
        logging.info("⚙️  [GOLOGIN] Step 3/4: Executing GoLogin shortcut...")
        success = self.launch_from_shortcut(shortcut_path, **kwargs)

        if success:
            # Wait for startup
            startup_wait = kwargs.get('startup_wait', 10)
            logging.info("⚙️  [GOLOGIN] Step 4/4: Waiting for GoLogin startup (timeout: %ds)...", startup_wait)
            time.sleep(startup_wait)

            # Verify it's running
            logging.info("   🔍 Verifying GoLogin process...")
            if self.is_browser_running('gologin'):
                logging.info("   ✅ [GOLOGIN] GoLogin process detected - launch successful!")
                logging.info("="*60)
                return True
            else:
                logging.error("   ❌ [GOLOGIN] GoLogin process NOT detected after waiting %ds", startup_wait)
                logging.error("   💡 Process may still be starting, or launch failed silently")
                logging.info("="*60)
                return False

        logging.error("❌ [GOLOGIN] Failed to execute GoLogin shortcut")
        logging.info("="*60)
        return False

    def launch_incogniton(self, **kwargs) -> bool:
        """
        Launch Incogniton (IX) browser from desktop shortcut.

        Args:
            **kwargs: Additional launch parameters

        Returns:
            True if launched successfully, False otherwise
        """
        logging.info("="*60)
        logging.info("🚀 [INCOGNITON] Starting Incogniton (IX) browser launch sequence")
        logging.info("="*60)

        # Get shortcut path
        logging.info("⚙️  [INCOGNITON] Step 1/3: Searching for Incogniton shortcut on desktop...")

        # Prioritize browser_name from login_data.txt if provided
        browser_name_hint = kwargs.get('browser_name')
        if browser_name_hint:
            logging.info("   Using browser name from login_data.txt: %s", browser_name_hint)
            shortcut_path = self.find_browser_on_desktop(browser_name_hint)
        else:
            # Fall back to hardcoded desktop_shortcut or default search
            shortcut_path = kwargs.get('desktop_shortcut')
            if not shortcut_path:
                logging.info("   Using default browser name: incogniton")
                shortcut_path = self.find_browser_on_desktop('incogniton')

        if not shortcut_path:
            logging.error("   ❌ [INCOGNITON] Incogniton shortcut not found on desktop!")
            logging.error("   💡 Please create a shortcut to Incogniton on your desktop")
            if kwargs.get('show_popup', True):
                logging.info("   📋 Attempting to show download popup...")
                self.show_download_popup('ix')
            return False

        # Launch browser from shortcut
        logging.info("⚙️  [INCOGNITON] Step 2/3: Executing Incogniton shortcut...")
        success = self.launch_from_shortcut(shortcut_path, **kwargs)

        if success:
            # Wait for startup
            startup_wait = kwargs.get('startup_wait', 10)
            logging.info("⚙️  [INCOGNITON] Step 3/3: Waiting for Incogniton startup (timeout: %ds)...", startup_wait)
            time.sleep(startup_wait)
            logging.info("   ✅ [INCOGNITON] Incogniton launched and ready")
            logging.info("="*60)
            return True

        logging.error("❌ [INCOGNITON] Failed to execute Incogniton shortcut")
        logging.info("="*60)
        return False

    def launch_generic(self, browser_type: str, **kwargs) -> bool:
        """
        Launch a generic browser by type.

        Args:
            browser_type: Browser type identifier (gologin, ix, chrome, free_automation, etc.)
            **kwargs: Additional launch parameters
                - browser_name: Specific browser shortcut name to search for (used with free_automation)

        Returns:
            True if launched successfully, False otherwise
        """
        logging.info("")
        logging.info("╔" + "═"*58 + "╗")
        logging.info("║ BROWSER LAUNCHER - GENERIC LAUNCH REQUEST              ║")
        logging.info("╚" + "═"*58 + "╝")
        logging.info("📌 Browser Type: %s", browser_type.upper())
        logging.debug("   Launch kwargs: %s", kwargs)

        browser_type_lower = browser_type.lower()

        if browser_type_lower == 'gologin':
            logging.info("⚡ Routing to: launch_gologin()")
            return self.launch_gologin(**kwargs)

        elif browser_type_lower in ['ix', 'incogniton']:
            logging.info("⚡ Routing to: launch_incogniton()")
            return self.launch_incogniton(**kwargs)

        elif browser_type_lower in ['chrome', 'free_automation']:
            logging.info("⚡ Routing to: Free Automation Mode")
            logging.info("")
            logging.info("🔄 [FREE_AUTO] Starting free automation browser search...")

            # For free automation, try to find any browser on desktop
            # User can specify browser_name in kwargs or we search for common browsers
            browser_name = kwargs.get('browser_name', 'chrome')
            logging.info("   🎯 Primary search target: '%s'", browser_name.upper())

            # Search for browser shortcut on desktop
            logging.info("   🔍 Searching for shortcut...")
            shortcut_path = self.find_browser_on_desktop(browser_name)

            if not shortcut_path:
                # Try alternative browser names
                logging.info("   ❌ Not found. Trying alternative browsers...")
                alternative_names = ['chrome', 'firefox', 'edge', 'brave', 'opera']
                for alt_name in alternative_names:
                    if alt_name.lower() == browser_name.lower():
                        continue
                    logging.info("   → Trying: %s", alt_name.upper())
                    shortcut_path = self.find_browser_on_desktop(alt_name)
                    if shortcut_path:
                        logging.info("   ✅ Found alternative: %s", alt_name.upper())
                        browser_name = alt_name
                        break

            if not shortcut_path:
                logging.error("   ❌ [FREE_AUTO] NO browser shortcut found on desktop!")
                logging.error("   💡 Please create a desktop shortcut for one of these browsers:")
                logging.error("      • Chrome")
                logging.error("      • Firefox")
                logging.error("      • Edge")
                logging.error("      • Brave")
                logging.error("      • Opera")
                return False

            logging.info("   ✅ Browser shortcut found: %s", shortcut_path.name)

            # Launch browser from shortcut
            logging.info("   🚀 Executing browser shortcut...")
            success = self.launch_from_shortcut(shortcut_path, **kwargs)

            if success:
                startup_wait = kwargs.get('startup_wait', 5)
                logging.info("   ⏳ Waiting %ds for browser to start...", startup_wait)
                time.sleep(startup_wait)
                logging.info("   ✅ [FREE_AUTO] Browser launched successfully")
                logging.info("")
                return True
            else:
                logging.error("   ❌ [FREE_AUTO] Failed to execute browser shortcut")
                logging.info("")
                return False
        else:
            logging.warning("❌ Unknown browser type: %s", browser_type)
            logging.warning("   Supported types: gologin, ix, incogniton, chrome, free_automation")
            logging.info("")
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

    def launch_from_shortcut(self, shortcut_path, **kwargs) -> bool:
        """
        Launch browser from desktop shortcut (.lnk file).

        Args:
            shortcut_path: Path to shortcut file (str or Path)
            **kwargs: Additional parameters

        Returns:
            True if launched successfully
        """
        # Convert to Path if string
        if isinstance(shortcut_path, str):
            shortcut_path = Path(shortcut_path)

        logging.info("🚀 [LAUNCH] Starting browser from shortcut: %s", shortcut_path.name)
        logging.debug("   📍 Full path: %s", shortcut_path)
        logging.debug("   ✓ File exists: %s", shortcut_path.exists())
        logging.debug("   ℹ️  Platform: %s", self.platform)

        try:
            if self.platform == 'Windows':
                logging.debug("   🪟 Using Windows os.startfile() for shortcut execution")
                logging.info("   Launching via shortcut file")
                os.startfile(str(shortcut_path))
                logging.debug("   ✓ os.startfile() executed successfully")

            else:
                # Linux/Mac: resolve symlink and execute
                logging.debug("   🐧 Using subprocess on Linux/Mac")
                resolved_path = shortcut_path.resolve()
                subprocess.Popen([str(resolved_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                logging.debug("   ✓ subprocess.Popen() executed successfully")

            logging.info("   ✅ [LAUNCH] Browser launched successfully")
            return True

        except FileNotFoundError as e:
            logging.error("   ❌ [LAUNCH] Shortcut file not found: %s", e, exc_info=True)
            return False
        except OSError as e:
            logging.error("   ❌ [LAUNCH] OS error executing shortcut: %s", e, exc_info=True)
            return False
        except Exception as e:
            logging.error("   ❌ [LAUNCH] Unexpected error launching from shortcut: %s", e, exc_info=True)
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

        matches = self._collect_process_entries(browser_type)
        running = bool(matches)

        if running:
            logging.debug("Detected %s process(es): %s", browser_type, ", ".join(f"{m.name} (PID {m.pid})" for m in matches))

        return running

    def get_browser_process(self, browser_type: str) -> Optional[ProcessEntry]:
        """
        Get the process object for a running browser.

        Args:
            browser_type: Browser type

        Returns:
            Process object if found, None otherwise
        """
        logging.debug("Getting process for %s", browser_type)

        matches = self._collect_process_entries(browser_type)
        return matches[0] if matches else None

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

        matches = self._collect_process_entries(browser_type)
        if not matches:
            logging.warning("Browser process not found: %s", browser_type)
            return False

        success = True
        for proc in matches:
            if self._kill_process_entry(proc, force=force):
                logging.info("Browser process terminated: %s (PID=%s)", proc.name, proc.pid)
            else:
                success = False

        return success

    def kill_all_browsers(self) -> int:
        """
        Kill all active browser processes.

        Returns:
            Number of browsers killed
        """
        logging.info("Killing all active browsers...")

        killed_count = 0

        for browser_type in self.BROWSER_PROCESSES.keys():
            matches = self._collect_process_entries(browser_type)
            if not matches:
                continue
            if self.kill_browser(browser_type, force=True):
                killed_count += len(matches)

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
            info['running'] = True
            info['pid'] = proc.pid
            info['name'] = proc.name

        return info

    # ------------------------------------------------------------------ #
    # Process helpers                                                    #
    # ------------------------------------------------------------------ #
    def _collect_process_entries(self, browser_type: str) -> List[ProcessEntry]:
        """Return a list of matching process entries for the given browser type."""
        process_names = self.BROWSER_PROCESSES.get(browser_type.lower(), [])
        if not process_names:
            return []

        matches: Dict[int, ProcessEntry] = {}

        if self.platform == 'Windows':
            try:
                result = subprocess.run(
                    ["tasklist", "/FO", "CSV", "/NH"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
            except Exception as exc:
                logging.debug("tasklist invocation failed: %s", exc)
                return []

            output = result.stdout.strip()
            if not output:
                return []

            normalized_targets: List[str] = []
            for candidate in process_names:
                lowered = candidate.lower()
                normalized_targets.append(lowered)
                if not lowered.endswith(".exe"):
                    normalized_targets.append(f"{lowered}.exe")

            reader = csv.reader(io.StringIO(output))
            for row in reader:
                if not row:
                    continue
                image_name = row[0].strip('"')
                try:
                    pid = int(row[1])
                except (IndexError, ValueError):
                    continue

                lowered_image = image_name.lower()

                # Normal matching - check against process names for this browser type
                if any(target == lowered_image or target in lowered_image for target in normalized_targets):
                    matches[pid] = ProcessEntry(pid=pid, name=image_name)
        else:  # macOS / Linux
            for candidate in process_names:
                try:
                    result = subprocess.run(
                        ["pgrep", "-fl", candidate],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                except Exception as exc:
                    logging.debug("pgrep failed for %s: %s", candidate, exc)
                    continue

                if result.returncode != 0:
                    continue

                for line in result.stdout.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split(None, 1)
                    try:
                        pid = int(parts[0])
                    except (ValueError, IndexError):
                        continue
                    name = parts[1] if len(parts) > 1 else candidate
                    matches[pid] = ProcessEntry(pid=pid, name=name)

        return list(matches.values())

    def _kill_process_entry(self, entry: ProcessEntry, *, force: bool) -> bool:
        """Terminate a process entry using platform-specific tools."""
        if self.platform == 'Windows':
            command = ["taskkill"]
            if force:
                command.append("/F")
            command.extend(["/PID", str(entry.pid)])
            result = subprocess.run(command, capture_output=True, text=True, check=False)
            if result.returncode != 0:
                logging.error("taskkill failed for PID %s: %s", entry.pid, (result.stderr or result.stdout).strip())
                return False
            return True

        signal = "-9" if force else "-15"
        result = subprocess.run(["kill", signal, str(entry.pid)], capture_output=True, text=True, check=False)
        if result.returncode != 0:
            logging.error("kill command failed for PID %s: %s", entry.pid, result.stderr.strip())
            return False
        return True

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
