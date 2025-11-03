"""Upload Tracker - Persist upload history for the modular workflow."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


def _timestamp() -> str:
    """Return an ISO-8601 timestamp in UTC."""
    return datetime.now(tz=timezone.utc).isoformat()


@dataclass(slots=True)
class _TrackerData:
    """Internal representation of the tracking file."""

    upload_history: List[Dict[str, object]] = field(default_factory=list)
    failed_uploads: List[Dict[str, object]] = field(default_factory=list)
    browser_accounts: Dict[str, Dict[str, object]] = field(default_factory=dict)
    last_updated: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        return {
            "upload_history": self.upload_history,
            "failed_uploads": self.failed_uploads,
            "browser_accounts": self.browser_accounts,
            "last_updated": self.last_updated,
        }


class UploadTracker:
    """Small helper that keeps track of completed and failed uploads."""

    def __init__(self, tracking_path: Path) -> None:
        self._path = Path(tracking_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._data = self._load()
        self._completed_cache = {
            (entry.get("creator"), entry.get("video"))
            for entry in self._data.upload_history
            if entry.get("status") == "completed"
        }
        self._dirty = False
        logging.debug("UploadTracker initialized at %s", self._path)

    # ------------------------------------------------------------------ #
    # Public API                                                         #
    # ------------------------------------------------------------------ #
    def record_upload(
        self,
        creator: str,
        video: str,
        status: str,
        account: Optional[str] = None,
        browser_type: Optional[str] = None,
        metadata: Optional[Dict[str, object]] = None,
    ) -> None:
        """Record the outcome of an upload attempt."""
        entry = {
            "creator": creator,
            "video": video,
            "status": status,
            "timestamp": _timestamp(),
        }
        if account:
            entry["account"] = account
        if browser_type:
            entry["browser_type"] = browser_type
        if metadata:
            entry["metadata"] = metadata

        self._data.upload_history.append(entry)
        if status != "completed":
            self._data.failed_uploads.append(entry)
        else:
            self._completed_cache.add((creator, video))

        if account:
            account_block = self._data.browser_accounts.setdefault(
                account,
                {
                    "browser_type": browser_type,
                    "uploads": [],
                    "failures": [],
                    "last_status": None,
                },
            )
            account_block["browser_type"] = browser_type
            account_block["last_status"] = status
            target_list = account_block["uploads"] if status == "completed" else account_block["failures"]
            target_list.append(
                {
                    "creator": creator,
                    "video": video,
                    "timestamp": entry["timestamp"],
                }
            )

        self._data.last_updated = entry["timestamp"]
        self._dirty = True
        logging.debug("Recorded upload (%s/%s) status=%s", creator, video, status)

    def was_uploaded(self, creator: str, video: str) -> bool:
        """Return True if a creator/video pair has already been marked as completed."""
        return (creator, video) in self._completed_cache

    def flush(self) -> None:
        """Persist the in-memory state to disk if it changed."""
        if not self._dirty:
            return

        payload = self._data.to_dict()
        try:
            self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            self._dirty = False
            logging.debug("Upload history persisted to %s", self._path)
        except OSError as exc:  # pragma: no cover - filesystem guard
            logging.error("Unable to write upload tracking file %s: %s", self._path, exc)

    # ------------------------------------------------------------------ #
    # Internal helpers                                                   #
    # ------------------------------------------------------------------ #
    def _load(self) -> _TrackerData:
        """Load tracker data from disk, falling back to defaults on failure."""
        if self._path.is_file():
            try:
                raw = json.loads(self._path.read_text(encoding="utf-8"))
                return _TrackerData(
                    upload_history=list(raw.get("upload_history", [])),
                    failed_uploads=list(raw.get("failed_uploads", [])),
                    browser_accounts=dict(raw.get("browser_accounts", {})),
                    last_updated=raw.get("last_updated"),
                )
            except (OSError, json.JSONDecodeError) as exc:
                logging.warning("UploadTracker: failed to parse %s (%s). Recreating fresh state.", self._path, exc)

        return _TrackerData()
