"""
Automation Health Checks
========================

Provides a configurable set of pre-flight checks that can be executed before
the login automation kicks in. Each check returns a structured result so the
caller can decide whether to proceed or abort.
"""

from __future__ import annotations

import logging
import socket
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


try:
    import pygetwindow as gw
except ImportError:  # pragma: no cover - optional dependency
    gw = None  # type: ignore[assignment]

try:
    import pyautogui
except ImportError:  # pragma: no cover - optional dependency
    pyautogui = None  # type: ignore[assignment]

try:
    import pyperclip
except ImportError:  # pragma: no cover - optional dependency
    pyperclip = None  # type: ignore[assignment]

try:
    import psutil
except ImportError:  # pragma: no cover - optional dependency
    psutil = None  # type: ignore[assignment]

try:
    import requests
except ImportError:  # pragma: no cover - optional dependency
    requests = None  # type: ignore[assignment]


@dataclass
class CheckResult:
    """Represents the outcome of a single health check."""

    passed: bool
    message: str
    meta: Dict[str, object] = field(default_factory=dict)

    def __bool__(self) -> bool:  # pragma: no cover - convenience
        return self.passed


class HealthChecker:
    """Run and aggregate pre-flight checks for the automation workflow."""

    def __init__(
        self,
        *,
        images_dir: Optional[Path] = None,
        required_images: Optional[Iterable[str]] = None,
        browser_title_hints: Optional[Sequence[str]] = None,
        network_test_url: str = "https://www.google.com",
        min_available_memory: int = 1_000_000_000,
        clipboard_test_value: str = "automation-health-check",
    ) -> None:
        self.images_dir = Path(images_dir or Path(__file__).parent.parent / "helper_images")
        self.required_images = list(required_images or [])
        self.browser_title_hints = list(browser_title_hints or [])
        self.network_test_url = network_test_url
        self.min_available_memory = min_available_memory
        self.clipboard_test_value = clipboard_test_value

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run_checks(self) -> Dict[str, CheckResult]:
        """Execute the configured checks and return their individual outcomes."""
        return {
            "browser": self._check_browser_running(),
            "network": self._check_network_available(),
            "helper_images": self._check_helper_images_present(),
            "automation_libs": self._check_automation_stack(),
            "screen_resolution": self._check_screen_resolution(),
            "clipboard": self._check_clipboard(),
            "memory": self._check_memory_available(),
        }

    def all_passed(self, results: Dict[str, CheckResult]) -> bool:
        """Return True when every check has passed."""
        return all(result.passed for result in results.values())

    def summarize(self, results: Dict[str, CheckResult]) -> str:
        """Produce a human friendly summary string."""
        parts: List[str] = []
        for name, result in results.items():
            status = "OK" if result.passed else "FAIL"
            parts.append(f"{name}: {status} ({result.message})")
        return " | ".join(parts)

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------
    def _check_browser_running(self) -> CheckResult:
        if not self.browser_title_hints:
            return CheckResult(True, "No window hints supplied; skipping.")

        if gw is None:
            return CheckResult(False, "pygetwindow not installed.")

        for hint in self.browser_title_hints:
            try:
                windows = gw.getWindowsWithTitle(hint)
            except Exception as exc:  # pragma: no cover - guard rails
                logging.debug("Browser window lookup failed for %s: %s", hint, exc)
                continue

            if windows:
                title = windows[0].title
                return CheckResult(True, f"Found window '{title}'.")

        return CheckResult(False, "No matching browser windows detected.")

    def _check_network_available(self) -> CheckResult:
        if requests is None:
            return CheckResult(False, "requests not installed.")

        try:
            response = requests.get(self.network_test_url, timeout=3)
            if 200 <= response.status_code < 500:
                return CheckResult(True, f"{self.network_test_url} reachable.")
            return CheckResult(False, f"Unexpected status code: {response.status_code}.")
        except requests.RequestException as exc:
            # Check for DNS availability as a secondary signal.
            try:
                socket.gethostbyname(self.network_test_url.replace("https://", "").replace("http://", ""))
                dns_ok = True
            except socket.gaierror:
                dns_ok = False
            return CheckResult(
                False,
                f"Network request failed: {exc}",
                meta={"dns_resolves": dns_ok},
            )

    def _check_helper_images_present(self) -> CheckResult:
        missing: List[str] = []
        for image_name in self.required_images:
            image_path = self.images_dir / image_name
            if not image_path.exists():
                missing.append(image_name)

        if missing:
            return CheckResult(False, f"Missing helper images: {', '.join(missing)}")
        return CheckResult(True, "All helper images present.")

    def _check_automation_stack(self) -> CheckResult:
        missing: List[str] = []
        for module_name, module in (("pyautogui", pyautogui), ("pyperclip", pyperclip)):
            if module is None:
                missing.append(module_name)

        if missing:
            return CheckResult(False, f"Missing automation libs: {', '.join(missing)}")

        # Sanity check: capture current position (non-destructive)
        try:
            _ = pyautogui.position()  # type: ignore[call-arg]
        except Exception as exc:
            return CheckResult(False, f"pyautogui error: {exc}")

        return CheckResult(True, "Automation libraries ready.")

    def _check_screen_resolution(self) -> CheckResult:
        if pyautogui is None:
            return CheckResult(False, "pyautogui not installed.")

        try:
            width, height = pyautogui.size()
        except Exception as exc:
            return CheckResult(False, f"Unable to read screen size: {exc}")

        if width < 1024 or height < 768:
            return CheckResult(False, f"Resolution too low: {width}x{height}")

        return CheckResult(True, f"Resolution OK: {width}x{height}")

    def _check_clipboard(self) -> CheckResult:
        if pyperclip is None:
            return CheckResult(False, "pyperclip not installed.")

        try:
            original = pyperclip.paste()
            pyperclip.copy(self.clipboard_test_value)
            copied = pyperclip.paste()
            pyperclip.copy(original or "")
        except Exception as exc:
            return CheckResult(False, f"Clipboard test failed: {exc}")

        if copied != self.clipboard_test_value:
            return CheckResult(False, "Clipboard read/write mismatch.")

        return CheckResult(True, "Clipboard operational.")

    def _check_memory_available(self) -> CheckResult:
        if psutil is None:
            return CheckResult(False, "psutil not installed.")

        try:
            stats = psutil.virtual_memory()
        except Exception as exc:
            return CheckResult(False, f"Unable to read memory stats: {exc}")

        available = int(getattr(stats, "available", 0))
        if available < self.min_available_memory:
            return CheckResult(False, f"Available memory low: {available / (1024**2):.0f} MB")

        return CheckResult(True, f"Available memory: {available / (1024**3):.2f} GB")

