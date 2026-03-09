"""
Shared auth/network helpers for cookies, proxies, and yt-dlp resolution.

This module is intentionally lightweight and dependency-minimal so all
downloader/grabber modules can safely consume it.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import quote

from modules.config.paths import find_ytdlp_executable, get_config_dir, get_cookies_dir


class AuthNetworkHub:
    """Single source of truth for cookies/proxies/yt-dlp runtime settings."""

    def __init__(self):
        self.cookies_dir = get_cookies_dir()
        self.config_dir = get_config_dir()
        self.proxy_config_file = self.config_dir / "proxy_settings.json"
        self.auth_state_file = self.config_dir / "auth_state.json"

    @staticmethod
    def detect_platform(url: str) -> str:
        u = (url or "").lower()
        if "youtube.com" in u or "youtu.be" in u:
            return "youtube"
        if "instagram.com" in u:
            return "instagram"
        if "tiktok.com" in u:
            return "tiktok"
        if "facebook.com" in u or "fb.com" in u:
            return "facebook"
        if "twitter.com" in u or "x.com" in u:
            return "twitter"
        return "other"

    def list_cookie_candidates(self, platform: str, source_folder: Optional[str] = None) -> List[Path]:
        candidates: List[Path] = []

        if platform and platform != "other":
            # PRIORITY 1: Canonical Platform-Specific (Most reliable, synced from all sources)
            candidates.append(self.cookies_dir / f"{platform}.txt")
            
            # PRIORITY 2: Direct Chromium Sync (Browser Auth Sync standard)
            candidates.append(self.cookies_dir / "browser_cookies" / f"{platform}_chromium_profile.txt")
            candidates.append(self.cookies_dir / f"{platform}_chromium_profile.txt")
            
            # PRIORITY 3: Legacy/Shared Master (May be stale)
            candidates.append(self.cookies_dir / "chrome_cookies.txt")
            
        else:
            candidates.append(self.cookies_dir / "chrome_cookies.txt")

        # Fallbacks
        candidates.append(self.cookies_dir / "cookies.txt")
        candidates.append(Path.home() / "Desktop" / "toseeq-cookies.txt")

        if source_folder:
            root = Path(source_folder)
            for name in ("chrome_cookies.txt", f"{platform}.txt", "cookies.txt"):
                candidates.append(root / name)
            cookies_sub = root / "cookies"
            for name in ("chrome_cookies.txt", f"{platform}.txt", "cookies.txt"):
                candidates.append(cookies_sub / name)

        unique: List[Path] = []
        seen = set()
        for p in candidates:
            key = str(p).lower()
            if key in seen:
                continue
            seen.add(key)
            unique.append(p)
        return unique

    def valid_cookie_files(self, platform: str, source_folder: Optional[str] = None) -> List[str]:
        found: List[str] = []
        for candidate in self.list_cookie_candidates(platform, source_folder):
            try:
                if candidate.exists() and candidate.is_file() and candidate.stat().st_size > 10:
                    found.append(str(candidate))
            except Exception:
                continue
        return found

    def pick_cookie_file(self, platform: str, source_folder: Optional[str] = None) -> Optional[str]:
        files = self.valid_cookie_files(platform, source_folder)
        return files[0] if files else None

    def load_proxy_settings(self) -> Dict[str, str]:
        data = {"proxy1": "", "proxy2": ""}
        try:
            if self.proxy_config_file.exists():
                raw = json.loads(self.proxy_config_file.read_text(encoding="utf-8"))
                data["proxy1"] = str(raw.get("proxy1", "") or "").strip()
                data["proxy2"] = str(raw.get("proxy2", "") or "").strip()
        except Exception:
            pass
        return data

    def save_proxy_settings(self, proxy1: str = "", proxy2: str = "") -> bool:
        payload = {
            "proxy1": (proxy1 or "").strip(),
            "proxy2": (proxy2 or "").strip(),
            "last_updated": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            self.proxy_config_file.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            return True
        except Exception:
            return False

    @staticmethod
    def parse_proxy(proxy: str) -> str:
        proxy = (proxy or "").strip()
        if not proxy:
            return ""

        if proxy.startswith(("http://", "https://", "socks4://", "socks5://")):
            proto, rest = proxy.split("://", 1)
            if "@" in rest:
                creds, host = rest.split("@", 1)
                if ":" in creds:
                    user, pwd = creds.split(":", 1)
                    return f"{proto}://{user}:{quote(pwd, safe='')}@{host}"
            return proxy

        if "@" in proxy:
            creds, host = proxy.split("@", 1)
            if ":" in creds:
                user, pwd = creds.split(":", 1)
                return f"http://{user}:{quote(pwd, safe='')}@{host}"
            return f"http://{proxy}"

        parts = proxy.split(":")
        if len(parts) == 2:
            return f"http://{proxy}"
        if len(parts) == 4:
            ip, port, user, pwd = parts
            return f"http://{user}:{quote(pwd, safe='')}@{ip}:{port}"
        return f"http://{proxy}"

    def get_proxy_pool(self) -> List[str]:
        data = self.load_proxy_settings()
        proxies: List[str] = []
        for raw in (data.get("proxy1", ""), data.get("proxy2", "")):
            if not raw:
                continue
            parsed = self.parse_proxy(raw)
            if parsed:
                proxies.append(parsed)
        return proxies

    def resolve_ytdlp(self) -> Dict[str, Optional[str]]:
        path = find_ytdlp_executable()
        result = {
            "path": path,
            "version": None,
            "source": None,
            "usable": False,
            "error": None,
        }
        if not path:
            result["error"] = "yt-dlp not found"
            return result

        try:
            run = subprocess.run(
                [path, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
                encoding="utf-8",
                errors="replace",
            )
            if run.returncode == 0:
                result["usable"] = True
                result["version"] = (run.stdout or "").strip().splitlines()[0] if run.stdout else ""
            else:
                result["error"] = (run.stderr or run.stdout or "").strip()[:200]
        except Exception as e:
            result["error"] = str(e)[:200]

        p = (path or "").lower()
        if p.startswith("c:/yt-dlp") or p.startswith("c:\\yt-dlp"):
            result["source"] = "C-drive"
        elif "yt-dlp.exe" in p and ("_internal" in p or "meipass" in p):
            result["source"] = "bundled"
        elif path in ("yt-dlp", "yt-dlp.exe"):
            result["source"] = "system-path"
        else:
            result["source"] = "custom"
        return result

    def write_auth_state(self, payload: Dict) -> bool:
        try:
            current = {}
            if self.auth_state_file.exists():
                current = json.loads(self.auth_state_file.read_text(encoding="utf-8"))
            current.update(payload or {})
            current["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            self.auth_state_file.write_text(
                json.dumps(current, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            return True
        except Exception:
            return False
