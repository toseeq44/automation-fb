"""Read and validate login data for the Facebook workflow."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict


class LoginDataError(Exception):
    """Raised when login data cannot be loaded or validated."""


@dataclass(frozen=True)
class LoginData:
    """Structured login data read from ``login_data.txt``."""

    browser: str
    email: str
    password: str

    @property
    def browser_key(self) -> str:
        """Normalized browser key used by other helpers."""
        return self.browser.strip().lower()


def _read_pairs(file_path: Path) -> Dict[str, str]:
    pairs: Dict[str, str] = {}

    with file_path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()

            if not line or line.startswith("#"):
                continue

            if ":" not in line:
                logging.warning("Skipping malformed line in %s: %s", file_path, raw_line.rstrip())
                continue

            key, value = line.split(":", 1)
            pairs[key.strip().lower()] = value.strip()

    return pairs


def load_login_data(data_folder: Path) -> LoginData:
    """
    Load login data from ``login_data.txt``.

    Args:
        data_folder: Directory that contains the credential file.

    Returns:
        ``LoginData`` structure with browser, email, and password.

    Raises:
        LoginDataError: If the directory or file cannot be found or is invalid.
    """
    data_folder = Path(data_folder).expanduser().resolve()

    if not data_folder.is_dir():
        raise LoginDataError(f"Data folder not found: {data_folder}")

    candidate_names = ("login_data.txt", "login_data_.txt")
    data_file = next((data_folder / name for name in candidate_names if (data_folder / name).is_file()), None)

    if data_file is None:
        raise LoginDataError(
            f"Could not locate login data file in {data_folder}. "
            "Expected login_data.txt (or legacy login_data_.txt)."
        )

    entries = _read_pairs(data_file)
    required_keys = ("browser", "email", "password")
    missing = [key for key in required_keys if key not in entries]

    if missing:
        raise LoginDataError(f"Missing required fields in {data_file}: {', '.join(missing)}")

    logging.info("Loaded login data from %s", data_file)

    return LoginData(
        browser=entries["browser"],
        email=entries["email"],
        password=entries["password"],
    )
