"""Persistent per-creator history tracking."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict


class HistoryManager:
    """Manages history.json for creators."""

    def __init__(self, history_file: Path):
        self.history_file = history_file
        self.data = self._load()

    # ------------------------------------------------------------------
    def record_batch(self, creator: str, total_attempted: int, success_count: int, failure_count: int):
        summary = self.data.setdefault(
            creator,
            {
                "last_upload": None,
                "last_batch_count": 0,
                "last_status": "never_ran",
                "total_uploaded": 0,
                "total_failed": 0,
            },
        )

        summary["last_upload"] = datetime.utcnow().isoformat()
        summary["last_batch_count"] = total_attempted
        summary["total_uploaded"] += success_count
        summary["total_failed"] += failure_count

        if failure_count == 0 and success_count > 0:
            summary["last_status"] = "success"
        elif success_count > 0:
            summary["last_status"] = "partial_success"
        else:
            summary["last_status"] = "failed"

        self._save()

    def get_summary(self, creator: str) -> Dict:
        return self.data.get(creator, {})

    # ------------------------------------------------------------------
    def _load(self) -> Dict:
        if not self.history_file.exists():
            logging.info("Creating new history store at %s", self.history_file)
            return {}

        try:
            with open(self.history_file, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except Exception as exc:
            logging.error("Failed to load history file %s: %s", self.history_file, exc)
            return {}

    def _save(self):
        try:
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.history_file, "w", encoding="utf-8") as handle:
                json.dump(self.data, handle, indent=2, ensure_ascii=False)
        except Exception as exc:
            logging.error("Unable to persist history data: %s", exc)

