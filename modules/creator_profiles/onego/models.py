"""
OneGo data models — report schema, per-page result, per-profile result.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class PageStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    SKIPPED = "skipped"
    FAILED = "failed"


class SkipReason(str, Enum):
    TARGET_ZERO = "target_zero"
    FOLDER_NOT_FOUND = "folder_not_found"
    BOOKMARK_NOT_FOUND = "bookmark_not_found"
    NO_VIDEOS = "no_videos"
    INSUFFICIENT_VIDEOS_PARTIAL = "insufficient_videos_partial"
    PROFILE_OPEN_FAILED = "profile_open_failed"
    UPLOAD_ACTION_FAILED = "upload_action_failed"


@dataclass
class PageResult:
    """Result for a single page/bookmark upload attempt."""
    page_name: str
    target: int = 0
    available: int = 0
    uploaded: int = 0
    status: PageStatus = PageStatus.SKIPPED
    reason: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "page_name": self.page_name,
            "target": self.target,
            "available": self.available,
            "uploaded": self.uploaded,
            "status": self.status.value,
            "reason": self.reason,
        }


@dataclass
class ProfileResult:
    """Result for one IX browser profile."""
    profile_name: str
    pages: List[PageResult] = field(default_factory=list)

    @property
    def pages_count(self) -> int:
        return len(self.pages)

    @property
    def total_uploaded(self) -> int:
        return sum(p.uploaded for p in self.pages)

    @property
    def total_skipped(self) -> int:
        return sum(1 for p in self.pages if p.status == PageStatus.SKIPPED)

    @property
    def total_failed(self) -> int:
        return sum(1 for p in self.pages if p.status == PageStatus.FAILED)

    def to_dict(self) -> dict:
        return {
            "profile_name": self.profile_name,
            "pages_count": self.pages_count,
            "total_uploaded": self.total_uploaded,
            "pages": [p.to_dict() for p in self.pages],
        }


@dataclass
class OneGoReport:
    """Final report for a OneGo run."""
    mode: str = ""
    profiles: List[ProfileResult] = field(default_factory=list)

    @property
    def profiles_processed(self) -> int:
        return len(self.profiles)

    @property
    def total_pages(self) -> int:
        return sum(p.pages_count for p in self.profiles)

    @property
    def total_uploaded(self) -> int:
        return sum(p.total_uploaded for p in self.profiles)

    @property
    def total_skipped(self) -> int:
        return sum(p.total_skipped for p in self.profiles)

    @property
    def total_partial(self) -> int:
        return sum(
            1 for p in self.profiles
            for pg in p.pages if pg.status == PageStatus.PARTIAL
        )

    @property
    def total_failed(self) -> int:
        return sum(p.total_failed for p in self.profiles)

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "profiles_processed": self.profiles_processed,
            "total_pages": self.total_pages,
            "total_uploaded": self.total_uploaded,
            "total_skipped": self.total_skipped,
            "total_partial": self.total_partial,
            "total_failed": self.total_failed,
            "profiles": [p.to_dict() for p in self.profiles],
        }
