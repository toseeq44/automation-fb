"""
Network Monitor for ixBrowser Approach

Handles network health monitoring and reconnection:
- Background thread for continuous monitoring
- Multi-level health checks (ping, HTTP, Selenium)
- Detects network drops
- Waits for reconnection
- Provides callbacks for network events

Usage:
    monitor = NetworkMonitor()
    monitor.start_monitoring()

    if monitor.is_network_stable():
        # Proceed with upload
        pass
"""

import logging
import time
import threading
import requests
import subprocess
from typing import Callable, Optional
from selenium import webdriver

logger = logging.getLogger(__name__)


class NetworkMonitor:
    """Monitors network health and handles reconnection."""

    def __init__(self, check_interval: int = 10):
        """
        Initialize Network Monitor.

        Args:
            check_interval: Seconds between health checks (default: 10)
        """
        self.check_interval = check_interval
        self.is_monitoring = False
        self.monitor_thread = None
        self.current_status = "unknown"  # stable, unstable, disconnected, unknown

        # Callbacks
        self.on_network_drop = None
        self.on_network_back = None

        logger.info("[NetworkMonitor] Initialized with check_interval: %ds", check_interval)

    def register_callbacks(self, on_drop: Callable = None, on_back: Callable = None):
        """
        Register callbacks for network events.

        Args:
            on_drop: Function to call when network drops
            on_back: Function to call when network recovers
        """
        if on_drop:
            self.on_network_drop = on_drop
        if on_back:
            self.on_network_back = on_back
        logger.debug("[NetworkMonitor] Callbacks registered")

    def check_network_health(self) -> str:
        """
        Check network health using multiple methods.

        Returns:
            "stable", "unstable", or "disconnected"
        """
        # Level 1: Quick ping to Google DNS
        try:
            result = subprocess.run(
                ['ping', '-c', '1', '-W', '2', '8.8.8.8'],
                capture_output=True,
                timeout=3
            )
            if result.returncode != 0:
                logger.debug("[NetworkMonitor] Ping failed (no basic connectivity)")
                return "disconnected"
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
            logger.debug("[NetworkMonitor] Ping error: %s", str(e))
            return "disconnected"

        # Level 2: HTTP request to Google
        try:
            response = requests.get("https://www.google.com", timeout=5)
            if response.status_code != 200:
                logger.debug("[NetworkMonitor] Google check failed (status: %d)", response.status_code)
                return "unstable"
        except requests.RequestException as e:
            logger.debug("[NetworkMonitor] Google HTTP failed: %s", str(e))
            return "unstable"

        # Level 3: HTTP request to Facebook
        try:
            response = requests.get("https://www.facebook.com", timeout=5)
            if response.status_code != 200:
                logger.debug("[NetworkMonitor] Facebook check failed (status: %d)", response.status_code)
                return "unstable"
        except requests.RequestException as e:
            logger.debug("[NetworkMonitor] Facebook HTTP failed: %s", str(e))
            return "unstable"

        # All checks passed
        return "stable"

    def is_network_stable(self) -> bool:
        """
        Quick check if network is currently stable.

        Returns:
            True if stable, False otherwise
        """
        return self.current_status == "stable"

    def wait_for_reconnection(self, max_wait: int = 300, check_interval: int = 10) -> bool:
        """
        Wait for network to come back online.

        Args:
            max_wait: Maximum wait time in seconds (default: 300 = 5 min)
            check_interval: Check every N seconds (default: 10)

        Returns:
            True if network recovered, False if timeout
        """
        logger.warning("[NetworkMonitor] Network down! Waiting for reconnection...")
        logger.warning("[NetworkMonitor] Max wait: %d seconds (%d minutes)",
                      max_wait, max_wait // 60)

        waited = 0

        while waited < max_wait:
            # Check if network is back
            status = self.check_network_health()

            if status == "stable":
                logger.info("[NetworkMonitor] ✓ Network recovered after %d seconds!", waited)
                self.current_status = "stable"

                # Trigger callback
                if self.on_network_back:
                    try:
                        self.on_network_back()
                    except Exception as e:
                        logger.error("[NetworkMonitor] Callback error: %s", str(e))

                return True

            # Show progress
            logger.info("[NetworkMonitor] Still waiting... (%d/%d seconds, status: %s)",
                       waited, max_wait, status)

            time.sleep(check_interval)
            waited += check_interval

        # Timeout reached
        logger.error("[NetworkMonitor] ✗ Network timeout after %d seconds", max_wait)
        return False

    def start_monitoring(self):
        """Start background network monitoring thread."""
        if self.is_monitoring:
            logger.warning("[NetworkMonitor] Already monitoring")
            return

        self.is_monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("[NetworkMonitor] ✓ Background monitoring started")

    def stop_monitoring(self):
        """Stop background network monitoring."""
        if not self.is_monitoring:
            logger.debug("[NetworkMonitor] Not monitoring")
            return

        self.is_monitoring = False

        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)

        logger.info("[NetworkMonitor] ✓ Monitoring stopped")

    def _monitoring_loop(self):
        """Background monitoring loop (runs in thread)."""
        logger.info("[NetworkMonitor] Monitoring loop started")
        previous_status = "unknown"

        while self.is_monitoring:
            try:
                # Check network health
                status = self.check_network_health()

                # Update current status
                self.current_status = status

                # Detect status changes
                if status != previous_status:
                    if status == "disconnected" and previous_status in ["stable", "unstable"]:
                        # Network dropped
                        logger.warning("[NetworkMonitor] ⚠ Network dropped! (was: %s)", previous_status)

                        # Trigger callback
                        if self.on_network_drop:
                            try:
                                self.on_network_drop()
                            except Exception as e:
                                logger.error("[NetworkMonitor] Callback error: %s", str(e))

                    elif status == "stable" and previous_status in ["disconnected", "unstable"]:
                        # Network recovered
                        logger.info("[NetworkMonitor] ✓ Network recovered! (was: %s)", previous_status)

                        # Trigger callback
                        if self.on_network_back:
                            try:
                                self.on_network_back()
                            except Exception as e:
                                logger.error("[NetworkMonitor] Callback error: %s", str(e))

                    previous_status = status

                # Sleep before next check
                time.sleep(self.check_interval)

            except Exception as e:
                logger.error("[NetworkMonitor] Monitoring error: %s", str(e))
                time.sleep(self.check_interval)

        logger.info("[NetworkMonitor] Monitoring loop stopped")
