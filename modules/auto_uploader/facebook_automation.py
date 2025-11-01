"""Entry point for the reorganized Facebook automation workflow."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

from .facebook_steps import (
    BrowserLaunchError,
    BrowserWindowNotFoundError,
    FacebookAutomationWorkflow,
    LoginDataError,
    ShortcutNotFoundError,
)


def _resolve_data_folder(folder_argument: Optional[str]) -> Path:
    if folder_argument:
        return Path(folder_argument).expanduser().resolve()

    print("Enter path to folder containing login_data.txt:")
    user_input = input().strip()
    if not user_input:
        raise LoginDataError("No data folder provided.")

    return Path(user_input).expanduser().resolve()


def main(folder_argument: Optional[str] = None) -> int:
    """Execute the workflow and return an exit code."""
    try:
        data_folder = _resolve_data_folder(folder_argument)
        workflow = FacebookAutomationWorkflow(data_folder)
        workflow.run()
        return 0

    except LoginDataError as exc:
        logging.error("Login data error: %s", exc)
    except ShortcutNotFoundError as exc:
        logging.error("Shortcut not found: %s", exc)
    except BrowserLaunchError as exc:
        logging.error("Browser launch failed: %s", exc)
    except BrowserWindowNotFoundError as exc:
        logging.error("Browser window error: %s", exc)
    except Exception as exc:  # pragma: no cover - defensive catch-all
        logging.exception("Unexpected error: %s", exc)

    return 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
    argument = sys.argv[1] if len(sys.argv) > 1 else None
    sys.exit(main(argument))
