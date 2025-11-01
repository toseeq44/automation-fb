"""Step 1: Load and read login credentials from login_data.txt file."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict


class CredentialsError(Exception):
    """Raised when credentials cannot be loaded or validated."""


@dataclass(frozen=True)
class Credentials:
    """Structured credentials read from login_data.txt."""

    browser: str
    email: str
    password: str

    @property
    def browser_key(self) -> str:
        """Normalized browser key (lowercase)."""
        return self.browser.strip().lower()


def _parse_credentials_file(file_path: Path) -> Dict[str, str]:
    """
    Parse key-value pairs from login_data.txt.

    Expected format:
        browser: browser_name
        email: user@example.com
        password: secret123

    Args:
        file_path: Path to the credentials file.

    Returns:
        Dictionary of key-value pairs (keys are lowercase).
    """
    pairs: Dict[str, str] = {}

    with file_path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()

            # Skip empty lines and comments
            if not line or line.startswith("#"):
                continue

            if ":" not in line:
                logging.warning("Skipping malformed line: %s", raw_line.rstrip())
                continue

            key, value = line.split(":", 1)
            pairs[key.strip().lower()] = value.strip()

    return pairs


def load_credentials(data_folder: Path) -> Credentials:
    """
    Load credentials from login_data.txt in the specified folder.

    Args:
        data_folder: Directory containing login_data.txt.

    Returns:
        Credentials object with browser, email, and password.

    Raises:
        CredentialsError: If the file cannot be found or is missing required fields.
    """
    data_folder = Path(data_folder).expanduser().resolve()

    if not data_folder.is_dir():
        raise CredentialsError(f"Data folder not found: {data_folder}")

    # Try standard filename first
    credentials_file = data_folder / "login_data.txt"

    if not credentials_file.is_file():
        raise CredentialsError(f"login_data.txt not found in {data_folder}")

    logging.info("Loading credentials from: %s", credentials_file)

    pairs = _parse_credentials_file(credentials_file)
    required_fields = ("browser", "email", "password")
    missing = [field for field in required_fields if field not in pairs]

    if missing:
        raise CredentialsError(f"Missing required fields in login_data.txt: {', '.join(missing)}")

    return Credentials(
        browser=pairs["browser"],
        email=pairs["email"],
        password=pairs["password"],
    )
