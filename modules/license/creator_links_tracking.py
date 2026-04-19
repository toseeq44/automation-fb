"""
Client-side collection helpers for creator-profile URL tracking.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List
from urllib.parse import urlparse


def _default_links_root() -> Path:
    return Path.home() / "Desktop" / "Links Grabber"


def _resolve_links_root() -> Path:
    try:
        from modules.config import get_config

        config = get_config()
        root = Path(config.get("link_grabber.save_folder", str(_default_links_root())))
        return root.expanduser()
    except Exception:
        return _default_links_root()


def _detect_platform(url: str) -> str:
    raw = (url or "").strip().lower()
    if not raw:
        return "unknown"
    try:
        host = (urlparse(raw).netloc or "").lower().replace("www.", "")
    except Exception:
        host = raw
    if "youtube.com" in host or "youtu.be" in host:
        return "youtube"
    if "facebook.com" in host or host == "fb.com":
        return "facebook"
    if "instagram.com" in host:
        return "instagram"
    if "tiktok.com" in host:
        return "tiktok"
    return host or "unknown"


def collect_creator_links_snapshot(installation_id: str, device_name: str) -> Dict:
    """
    Scan Desktop/Links Grabber creator folders and build a portable JSON snapshot
    of all creator URLs currently configured on the client.
    """
    from modules.creator_profiles.config_manager import CreatorConfig

    root = _resolve_links_root()
    creators: List[Dict] = []

    if root.exists():
        for item in sorted(root.iterdir(), key=lambda p: p.name.lower()):
            if not item.is_dir():
                continue

            cfg_path = item / "creator_config.json"
            if not cfg_path.exists():
                continue

            try:
                cfg = CreatorConfig(item)
                creator_url = (cfg.creator_url or "").strip() or (cfg.infer_creator_url() or "").strip()
                creators.append(
                    {
                        "folder_name": item.name,
                        "creator_url": creator_url,
                        "platform": _detect_platform(creator_url),
                        "uploading_target": int(cfg.uploading_target),
                        "n_videos": int(cfg.n_videos),
                        "config_path": str(cfg_path),
                    }
                )
            except Exception as exc:
                creators.append(
                    {
                        "folder_name": item.name,
                        "creator_url": "",
                        "platform": "unknown",
                        "error": str(exc),
                        "config_path": str(cfg_path),
                    }
                )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "installation_id": installation_id,
        "device_name": device_name,
        "links_root": str(root),
        "creator_count": len(creators),
        "creators": creators,
    }
