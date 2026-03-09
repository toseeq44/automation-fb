"""
modules/creator_profiles/config_manager.py
Per-creator JSON config — save/load settings per folder.
"""

import json
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
from urllib.parse import parse_qs, urlparse

_WATERMARK_TEXT_DEFAULTS = {
    "enabled": False,
    "text": "",                   # empty = use @folderName
    "position": "BottomRight",    # TopLeft|TopRight|BottomLeft|BottomRight|Center|AnimateAround
    "opacity": 80,
    "font_family": "Arial",
    "font_color": "#FFFFFF",
    "font_size": 24,
    "font_weight": "bold",
    "font_style": "normal",
    "render_style": "normal",     # normal|outline_hollow|outline_shadow
    "letter_spacing": 0,
    "shadow_opacity": 75,         # for outline_shadow
    "shadow_offset": 2,           # px, for outline_shadow
}

_WATERMARK_LOGO_DEFAULTS = {
    "enabled": False,
    "path": "",                   # empty = auto-detect logo.* in creator folder
    "position": "TopLeft",
    "opacity": 80,
}

_DEFAULTS = {
    "creator_url": "",
    "n_videos": 5,
    "editing_mode": "none",       # "none" | "preset" | "split"
    "preset_name": "",
    "split_duration": 15.0,
    "duplication_control": True,
    "popular_fallback": True,
    "prefer_popular_first": False,
    "randomize_links": False,
    "keep_original_after_edit": True,
    "delete_before_download": False,
    "uploading_target": 0,
    "watermark_enabled": False,
    "watermark_text": _WATERMARK_TEXT_DEFAULTS.copy(),
    "watermark_logo": _WATERMARK_LOGO_DEFAULTS.copy(),
    "downloaded_ids": [],
    "downloaded_url_history": [],
    "last_activity": {
        "date": None,
        "result": None,           # "success" | "partial" | "failed"
        "tier_used": None,
        "videos_downloaded": 0,
    },
}

_RESERVED_PROFILE_SEGMENTS = {
    "reel", "reels", "video", "videos", "featured", "watch", "shorts",
    "posts", "post", "p", "tv", "stories", "story", "about", "photos",
    "photo", "live", "clips",
}


class CreatorConfig:
    """Manages creator_config.json inside the creator's folder."""

    def __init__(self, folder: Path):
        self.folder = Path(folder)
        self.config_file = self.folder / "creator_config.json"
        self.data = self._load()
        self._activity_log = self._resolve_activity_log()

    @staticmethod
    def _resolve_activity_log() -> Path:
        try:
            from modules.config.paths import get_data_dir
            data_dir = get_data_dir()
        except ImportError:
            # Fallback for dev/simple cases
            root = Path(__file__).resolve().parents[2]
            data_dir = root / "data_files"
            data_dir.mkdir(parents=True, exist_ok=True)
            
        return data_dir / "creator_activity_log.jsonl"

    # ── Load / Save ──────────────────────────────────────────────────────────

    def _load(self) -> dict:
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                merged = _DEFAULTS.copy()
                merged.update(saved)
                # Ensure nested defaults
                if not isinstance(merged.get("last_activity"), dict):
                    merged["last_activity"] = _DEFAULTS["last_activity"].copy()
                if not isinstance(merged.get("downloaded_ids"), list):
                    merged["downloaded_ids"] = []
                if not isinstance(merged.get("downloaded_url_history"), list):
                    merged["downloaded_url_history"] = []
                # Ensure watermark nested dicts have all keys
                wm_text = _WATERMARK_TEXT_DEFAULTS.copy()
                wm_text.update(merged.get("watermark_text") or {})
                merged["watermark_text"] = wm_text
                wm_logo = _WATERMARK_LOGO_DEFAULTS.copy()
                wm_logo.update(merged.get("watermark_logo") or {})
                merged["watermark_logo"] = wm_logo
                return merged
            except Exception:
                pass
        return {k: (v.copy() if isinstance(v, (dict, list)) else v)
                for k, v in _DEFAULTS.items()}

    def save(self) -> bool:
        try:
            self.folder.mkdir(parents=True, exist_ok=True)
            tmp = self.config_file.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
            tmp.replace(self.config_file)
            return True
        except Exception as e:
            print(f"[CreatorConfig] save error: {e}")
            return False

    # ── Video ID tracking ────────────────────────────────────────────────────

    def add_downloaded_id(self, video_id: str):
        if video_id and video_id not in self.data["downloaded_ids"]:
            self.data["downloaded_ids"].append(video_id)

    def is_downloaded(self, video_id: str) -> bool:
        return video_id in self.data["downloaded_ids"]

    # ── URL history (capped at 300) ──────────────────────────────────────────

    _URL_HISTORY_CAP = 300

    def add_url_to_history(self, url: str, platform: str = "", creator: str = ""):
        """Record a successfully-downloaded URL for history fallback."""
        if not url:
            return
        history = self.data.setdefault("downloaded_url_history", [])
        # Avoid duplicate entries for the same URL
        if any(h.get("url") == url for h in history):
            return
        history.append({
            "url": url,
            "platform": platform,
            "creator": creator,
            "downloaded_at": datetime.now().isoformat(),
        })
        # Cap: keep most recent entries
        if len(history) > self._URL_HISTORY_CAP:
            self.data["downloaded_url_history"] = history[-self._URL_HISTORY_CAP:]

    def get_url_history(self) -> list:
        """Return the downloaded URL history list."""
        return self.data.get("downloaded_url_history", [])

    # ── Activity ─────────────────────────────────────────────────────────────

    def update_last_activity(self, result: str, tier_used: str, count: int):
        self.data["last_activity"] = {
            "date": datetime.now().isoformat(),
            "result": result,
            "tier_used": tier_used,
            "videos_downloaded": count,
        }
        self.append_activity_event(
            "workflow_completed",
            {
                "result": result,
                "tier_used": tier_used,
                "videos_downloaded": count,
            },
        )

    def append_activity_event(self, event_type: str, payload: Dict[str, Any] | None = None):
        payload = payload or {}
        record = {
            "timestamp": datetime.now().isoformat(),
            "creator_folder": str(self.folder),
            "creator_url": self.data.get("creator_url", ""),
            "event": event_type,
            "payload": payload,
        }
        try:
            with open(self._activity_log, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception:
            # Activity logging must never break workflow
            pass

    # ── URL intelligence ────────────────────────────────────────────────────

    @staticmethod
    def _normalize_profile_url(url: str) -> str:
        url = (url or "").strip()
        if not url:
            return ""
        if not url.startswith(("http://", "https://")):
            return ""
        try:
            parsed = urlparse(url)
            host = (parsed.netloc or "").lower().replace("www.", "")
            parts = [p for p in parsed.path.split("/") if p]
            lower_parts = [p.lower() for p in parts]

            if not host:
                return url.rstrip("/")

            if "instagram.com" in host:
                if parts:
                    user = parts[0]
                    if user.lower() not in _RESERVED_PROFILE_SEGMENTS:
                        return f"https://www.instagram.com/{user}"
                return f"https://www.instagram.com/"

            if "facebook.com" in host or host == "fb.com":
                if lower_parts and lower_parts[0] == "profile.php":
                    q = parse_qs(parsed.query or "")
                    pid = (q.get("id") or [""])[0].strip()
                    if pid:
                        return f"https://www.facebook.com/profile.php?id={pid}"
                if parts:
                    first = parts[0]
                    if first.lower() not in _RESERVED_PROFILE_SEGMENTS:
                        return f"https://www.facebook.com/{first}"
                return "https://www.facebook.com/"

            if "youtube.com" in host or "youtu.be" in host:
                if parts:
                    if parts[0].startswith("@"):
                        return f"https://www.youtube.com/{parts[0]}"
                    if len(parts) >= 2 and lower_parts[0] in {"channel", "c", "user"}:
                        return f"https://www.youtube.com/{parts[0]}/{parts[1]}"
                return url.rstrip("/")

            if "tiktok.com" in host:
                for p in parts:
                    if p.startswith("@") and len(p) > 1:
                        return f"https://www.tiktok.com/{p}"
                return url.rstrip("/")

            return url.rstrip("/")
        except Exception:
            return url.rstrip("/")

    @staticmethod
    def _extract_profile_from_video_url(url: str) -> str:
        u = (url or "").strip()
        if not u:
            return ""

        # TikTok: https://www.tiktok.com/@user/video/123 -> /@user
        m = re.search(r"(https?://(?:www\.)?tiktok\.com/@[^/?#]+)", u, re.IGNORECASE)
        if m:
            return m.group(1).rstrip("/")

        # Instagram profile/reel/post links
        m = re.search(r"https?://(?:www\.)?instagram\.com/([^/?#]+)", u, re.IGNORECASE)
        if m:
            user = m.group(1)
            if user.lower() not in {"reel", "p", "tv", "stories"}:
                return f"https://www.instagram.com/{user}"

        # YouTube handle style
        m = re.search(r"(https?://(?:www\.)?youtube\.com/@[^/?#]+)", u, re.IGNORECASE)
        if m:
            return m.group(1).rstrip("/")
        m = re.search(r"(https?://(?:www\.)?youtube\.com/(?:channel|c|user)/[^/?#]+)", u, re.IGNORECASE)
        if m:
            return m.group(1).rstrip("/")

        # Facebook page/profile (best effort)
        m = re.search(r"(https?://(?:www\.)?facebook\.com/[^/?#]+)", u, re.IGNORECASE)
        if m:
            candidate = m.group(1).rstrip("/")
            if candidate.lower().endswith("/video"):
                return ""
            return candidate

        return ""

    def infer_creator_url(self) -> str:
        """Best-effort URL inference from links files or folder naming."""
        # 1) Try links files inside creator folder
        candidates = []
        for pat in ("*links*.txt", "*.txt"):
            candidates.extend(self.folder.glob(pat))

        for file_path in candidates:
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if not line.startswith(("http://", "https://")):
                            continue
                        profile = self._extract_profile_from_video_url(line)
                        if profile:
                            return profile
            except Exception:
                continue

        # 2) Try folder name if it already carries URL-ish value
        raw_name = self.folder.name
        decoded = raw_name.replace("___", "://").replace("__", "/").replace("_", ".")
        normalized = self._normalize_profile_url(decoded)
        if normalized:
            return normalized

        # 3) If folder is @username, infer by parent platform folder name
        if raw_name.startswith("@"):
            username = raw_name
            parent_name = self.folder.parent.name.lower()
            platform_map = {
                "tiktok": f"https://www.tiktok.com/{username}",
                "youtube": f"https://www.youtube.com/{username}",
                "instagram": f"https://www.instagram.com/{username.lstrip('@')}",
                "facebook": f"https://www.facebook.com/{username.lstrip('@')}",
            }
            for key, url in platform_map.items():
                if key in parent_name:
                    return url

        return ""

    def ensure_creator_url(self) -> Optional[str]:
        """Populate creator_url if missing. Returns final value or None."""
        current = self._normalize_profile_url(self.data.get("creator_url", ""))
        if current:
            self.data["creator_url"] = current
            return current

        inferred = self.infer_creator_url()
        if inferred:
            self.data["creator_url"] = inferred
            self.save()
            self.append_activity_event("creator_url_inferred", {"creator_url": inferred})
            return inferred
        return None

    # ── Convenience properties ───────────────────────────────────────────────

    @property
    def creator_url(self) -> str:
        return self.data.get("creator_url", "")

    @property
    def n_videos(self) -> int:
        return int(self.data.get("n_videos", 5))

    @property
    def editing_mode(self) -> str:
        return str(self.data.get("editing_mode", "none")).strip().lower()

    @property
    def preset_name(self) -> str:
        return self.data.get("preset_name", "")

    @property
    def split_duration(self) -> float:
        return float(self.data.get("split_duration", 15.0))

    @property
    def duplication_control(self) -> bool:
        return bool(self.data.get("duplication_control", True))

    @property
    def popular_fallback(self) -> bool:
        return bool(self.data.get("popular_fallback", True))

    @property
    def prefer_popular_first(self) -> bool:
        return bool(self.data.get("prefer_popular_first", False))

    @property
    def randomize_links(self) -> bool:
        return bool(self.data.get("randomize_links", False))

    @property
    def keep_original_after_edit(self) -> bool:
        return bool(self.data.get("keep_original_after_edit", True))

    @property
    def delete_before_download(self) -> bool:
        return bool(self.data.get("delete_before_download", False))

    @property
    def uploading_target(self) -> int:
        return int(self.data.get("uploading_target", 0))

    @property
    def last_activity(self) -> dict:
        return self.data.get("last_activity", {})

    @property
    def watermark_enabled(self) -> bool:
        return bool(self.data.get("watermark_enabled", False))

    @property
    def watermark_text(self) -> dict:
        wm = self.data.get("watermark_text") or {}
        defaults = _WATERMARK_TEXT_DEFAULTS.copy()
        defaults.update(wm)
        return defaults

    @property
    def watermark_logo(self) -> dict:
        wm = self.data.get("watermark_logo") or {}
        defaults = _WATERMARK_LOGO_DEFAULTS.copy()
        defaults.update(wm)
        return defaults
