"""
Launch the app with the local Nuitka overlay first in sys.path.

This is for source-mode testing only. It keeps the main repo untouched and lets
us confirm selected modules are being loaded from compiled .pyd files before we
think about PyInstaller integration.
"""

from __future__ import annotations

import argparse
import importlib
import runpy
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent
OVERLAY_ROOT = REPO_ROOT / ".nuitka_critical"
TARGET_MODULES = [
    "modules.license.hardware_id",
    "modules.license.firebase_license_manager",
    "modules.license.license_manager",
    "modules.license.creator_links_tracking",
    "modules.license.lease_crypto",
    "modules.security.hardening",
]


def _activate_overlay() -> None:
    if not OVERLAY_ROOT.exists():
        raise SystemExit(
            "Nuitka overlay not found. Run: python build_nuitka_critical.py"
        )

    repo_root_str = str(REPO_ROOT)
    overlay_root_str = str(OVERLAY_ROOT)

    cleaned = [entry for entry in sys.path if entry not in ("", repo_root_str, overlay_root_str)]
    sys.path[:] = [overlay_root_str, repo_root_str, *cleaned]


def _probe_compiled_modules() -> list[tuple[str, bool, str]]:
    results: list[tuple[str, bool, str]] = []
    for module_name in TARGET_MODULES:
        module = importlib.import_module(module_name)
        is_compiled = bool(getattr(module, "__compiled__", False))
        module_file = str(getattr(module, "__file__", "(unknown)"))
        results.append((module_name, is_compiled, module_file))
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--probe-only",
        action="store_true",
        help="Only verify compiled modules are loading; do not launch the GUI.",
    )
    args = parser.parse_args()

    _activate_overlay()
    results = _probe_compiled_modules()

    print("Nuitka critical-module probe:")
    all_compiled = True
    for module_name, is_compiled, module_file in results:
        state = "compiled" if is_compiled else "source"
        print(f" - {module_name}: {state} -> {module_file}")
        all_compiled &= is_compiled

    if not all_compiled:
        raise SystemExit("One or more target modules did not load from compiled artifacts.")

    if args.probe_only:
        return

    runpy.run_path(str(REPO_ROOT / "main.py"), run_name="__main__")


if __name__ == "__main__":
    main()
