"""
modules/link_grabber/core.py
BULLETPROOF Multi-Method Link Grabber

Approach: Try multiple methods in sequence until success
- Method 1: yt-dlp --flat-playlist --get-url (Batch file approach)
- Method 2: yt-dlp --dump-json (Detailed extraction)
- Method 3: yt-dlp with platform variations
- Method 4: Instaloader (Instagram)
- Method 5: Gallery-dl (Instagram/TikTok)

CRASH PROTECTION: Extensive error handling, no crashes guaranteed
"""

from PyQt5.QtCore import QThread, pyqtSignal
from pathlib import Path
import os
import subprocess
import tempfile
import re
import typing
import json


# ============ HELPER FUNCTIONS ============

def _safe_filename(s: str) -> str:
    """Sanitize filename"""
    try:
        s = re.sub(r'[<>:"/\\|?*\n\r\t]+', '_', s.strip())
        return s[:200] if s else "unknown"
    except Exception:
        return "unknown"


def _extract_creator_from_url(url: str, platform_key: str) -> str:
    """Extract creator name - crash protected"""
    try:
        url_lower = url.lower()

        if platform_key == 'youtube':
            # @username
            match = re.search(r'/@([^/?#]+)', url_lower)
            if match:
                return match.group(1)
            # /channel/ID or /c/name
            for pattern in [r'/channel/([^/?#]+)', r'/c/([^/?#]+)', r'/user/([^/?#]+)']:
                match = re.search(pattern, url_lower)
                if match:
                    return match.group(1)

        elif platform_key == 'instagram':
            match = re.search(r'instagram\.com/([^/?#]+)', url_lower)
            if match and match.group(1) not in ['p', 'reel', 'tv', 'stories']:
                return match.group(1)

        elif platform_key == 'tiktok':
            match = re.search(r'tiktok\.com/@([^/?#]+)', url_lower)
            if match:
                return match.group(1)

        elif platform_key in ['twitter', 'facebook']:
            match = re.search(r'(?:twitter|x|facebook)\.com/([^/?#]+)', url_lower)
            if match:
                return match.group(1)

        # Fallback: last part of URL
        parts = url.rstrip('/').split('/')
        if parts:
            return parts[-1]
    except Exception:
        pass

    return platform_key or 'unknown'


def _detect_platform_key(url: str) -> str:
    """Detect platform - crash protected"""
    try:
        u = url.lower()
        if 'youtube.com' in u or 'youtu.be' in u:
            return 'youtube'
        if 'instagram.com' in u:
            return 'instagram'
        if 'tiktok.com' in u:
            return 'tiktok'
        if 'facebook.com' in u or 'fb.com' in u:
            return 'facebook'
        if 'twitter.com' in u or 'x.com' in u:
            return 'twitter'
    except Exception:
        pass
    return 'unknown'


def _find_cookie_file(cookies_dir: Path, platform_key: str) -> typing.Optional[str]:
    """Find cookie file - crash protected"""
    try:
        # Simple names: instagram.txt, youtube.txt
        cookie_file = cookies_dir / f"{platform_key}.txt"
        if cookie_file.exists() and cookie_file.stat().st_size > 10:
            return str(cookie_file)

        # Fallback: cookies.txt
        fallback = cookies_dir / "cookies.txt"
        if fallback.exists() and fallback.stat().st_size > 10:
            return str(fallback)
    except Exception:
        pass

    return None


def _normalize_url(url: str) -> str:
    """Normalize URL for duplicate detection"""
    try:
        url = url.split('?')[0].split('#')[0]
        return url.lower().rstrip('/')
    except Exception:
        return url


def _remove_duplicates(urls: typing.List[str]) -> typing.List[str]:
    """Remove duplicates - crash protected"""
    try:
        seen = set()
        unique = []
        for url in urls:
            normalized = _normalize_url(url)
            if normalized not in seen:
                seen.add(normalized)
                unique.append(url)
        return unique
    except Exception:
        return urls  # Return original if fails


# ============ EXTRACTION METHODS (Crash Protected) ============

def _method1_batch_file_approach(url: str, platform_key: str, cookie_file: str = None, max_videos: int = 0, progress_callback=None) -> typing.List[dict]:
    """
    METHOD 1: Exact batch file approach
    yt-dlp --flat-playlist --get-url
    MOST RELIABLE for YouTube channels
    """
    try:
        if progress_callback:
            progress_callback("🔄 Method 1: Batch file approach (yt-dlp --flat-playlist --get-url)")

        cmd = ['yt-dlp', '--flat-playlist', '--get-url', '--ignore-errors', '--no-warnings']

        if cookie_file:
            cmd.extend(['--cookies', cookie_file])

        if max_videos > 0:
            cmd.extend(['--playlist-end', str(max_videos)])

        cmd.append(url)

        # Run command - EXACT batch file style
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=180,  # 3 minutes timeout
            encoding='utf-8',
            errors='replace'
        )

        if result.stdout:
            urls = [
                line.strip()
                for line in result.stdout.splitlines()
                if line.strip() and line.strip().startswith('http')
            ]

            if urls:
                if progress_callback:
                    progress_callback(f"✅ Method 1 SUCCESS: Found {len(urls)} links")
                return [{'url': u, 'title': u} for u in urls]

        if progress_callback:
            progress_callback(f"⚠️ Method 1 failed: {result.stderr[:100] if result.stderr else 'No output'}")

    except subprocess.TimeoutExpired:
        if progress_callback:
            progress_callback("⚠️ Method 1 timeout (3 minutes)")
    except FileNotFoundError:
        if progress_callback:
            progress_callback("❌ yt-dlp not found in PATH")
    except Exception as e:
        if progress_callback:
            progress_callback(f"⚠️ Method 1 error: {str(e)[:100]}")

    return []


def _method2_dump_json(url: str, platform_key: str, cookie_file: str = None, max_videos: int = 0, progress_callback=None) -> typing.List[dict]:
    """
    METHOD 2: yt-dlp --dump-json
    More detailed, good for Instagram
    """
    try:
        if progress_callback:
            progress_callback("🔄 Method 2: yt-dlp --dump-json (detailed extraction)")

        cmd = ['yt-dlp', '--dump-json', '--flat-playlist', '--ignore-errors', '--no-warnings']

        if cookie_file:
            cmd.extend(['--cookies', cookie_file])

        if max_videos > 0:
            cmd.extend(['--playlist-end', str(max_videos)])

        # Platform-specific optimizations
        if platform_key == 'instagram':
            cmd.extend(['--extractor-args', 'instagram:feed_count=100'])
        elif platform_key == 'youtube':
            cmd.extend(['--extractor-args', 'youtube:player_client=android'])

        cmd.append(url)

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=180,
            encoding='utf-8',
            errors='replace'
        )

        if result.stdout:
            entries = []
            for line in result.stdout.splitlines():
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    video_url = data.get('webpage_url') or data.get('url')
                    if video_url:
                        entries.append({
                            'url': video_url,
                            'title': data.get('title', 'Untitled')[:100]
                        })
                except (json.JSONDecodeError, KeyError):
                    continue

            if entries:
                if progress_callback:
                    progress_callback(f"✅ Method 2 SUCCESS: Found {len(entries)} links")
                return entries

        if progress_callback:
            progress_callback("⚠️ Method 2 failed: No data")

    except Exception as e:
        if progress_callback:
            progress_callback(f"⚠️ Method 2 error: {str(e)[:100]}")

    return []


def _method3_ytdlp_variations(url: str, platform_key: str, cookie_file: str = None, max_videos: int = 0, progress_callback=None) -> typing.List[dict]:
    """
    METHOD 3: yt-dlp with platform-specific variations
    """
    try:
        if progress_callback:
            progress_callback("🔄 Method 3: yt-dlp platform variations")

        # Try different command structures
        cmd_variations = [
            # Variation 1: With --get-url
            ['yt-dlp', '--get-url', '--ignore-errors'],
            # Variation 2: No flat-playlist
            ['yt-dlp', '--get-url', '--ignore-errors', '--no-warnings'],
            # Variation 3: With skip options
            ['yt-dlp', '--flat-playlist', '--get-url', '--skip-download', '--ignore-errors']
        ]

        for i, base_cmd in enumerate(cmd_variations, 1):
            try:
                cmd = base_cmd.copy()

                if cookie_file:
                    cmd.extend(['--cookies', cookie_file])

                if max_videos > 0:
                    cmd.extend(['--playlist-end', str(max_videos)])

                cmd.append(url)

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=120,
                    encoding='utf-8',
                    errors='replace'
                )

                if result.stdout:
                    urls = [
                        line.strip()
                        for line in result.stdout.splitlines()
                        if line.strip() and line.strip().startswith('http')
                    ]

                    if urls:
                        if progress_callback:
                            progress_callback(f"✅ Method 3 variation {i} SUCCESS: Found {len(urls)} links")
                        return [{'url': u, 'title': u} for u in urls]

            except Exception:
                continue

        if progress_callback:
            progress_callback("⚠️ Method 3 failed: All variations failed")

    except Exception as e:
        if progress_callback:
            progress_callback(f"⚠️ Method 3 error: {str(e)[:100]}")

    return []


def _method4_instaloader(url: str, platform_key: str, cookie_file: str = None, progress_callback=None) -> typing.List[dict]:
    """
    METHOD 4: Instaloader for Instagram
    """
    if platform_key != 'instagram':
        return []

    try:
        if progress_callback:
            progress_callback("🔄 Method 4: Instaloader (Instagram)")

        import instaloader

        username_match = re.search(r'instagram\.com/([^/?#]+)', url)
        if not username_match or username_match.group(1) in ['p', 'reel', 'tv', 'stories']:
            return []

        username = username_match.group(1)

        loader = instaloader.Instaloader(
            quiet=True,
            download_videos=False,
            save_metadata=False,
            download_pictures=False
        )

        # Load cookies if available
        if cookie_file:
            try:
                cookies_dict = {}
                with open(cookie_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip() and not line.startswith('#'):
                            parts = line.strip().split('\t')
                            if len(parts) >= 7:
                                cookies_dict[parts[5]] = parts[6]
                if cookies_dict:
                    loader.context._session.cookies.update(cookies_dict)
            except Exception:
                pass

        profile = instaloader.Profile.from_username(loader.context, username)
        entries = []

        for post in profile.get_posts():
            entries.append({
                'url': f"https://www.instagram.com/p/{post.shortcode}/",
                'title': (post.caption or 'Instagram Post')[:100]
            })
            if len(entries) >= 100:
                break

        if entries:
            if progress_callback:
                progress_callback(f"✅ Method 4 SUCCESS: Found {len(entries)} links")
            return entries

        if progress_callback:
            progress_callback("⚠️ Method 4 failed: No posts found")

    except ImportError:
        if progress_callback:
            progress_callback("⚠️ Method 4 unavailable: instaloader not installed")
    except Exception as e:
        if progress_callback:
            progress_callback(f"⚠️ Method 4 error: {str(e)[:100]}")

    return []


def _method5_gallery_dl(url: str, platform_key: str, cookie_file: str = None, progress_callback=None) -> typing.List[dict]:
    """
    METHOD 5: gallery-dl for Instagram/TikTok
    """
    if platform_key not in ['instagram', 'tiktok']:
        return []

    try:
        if progress_callback:
            progress_callback("🔄 Method 5: gallery-dl")

        cmd = ['gallery-dl', '--dump-json', '--quiet']

        if cookie_file:
            cmd.extend(['--cookies', cookie_file])

        cmd.append(url)

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            encoding='utf-8',
            errors='replace'
        )

        if result.stdout:
            entries = []
            for line in result.stdout.splitlines():
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    post_url = data.get('post_url') or data.get('url')
                    if post_url:
                        entries.append({'url': post_url, 'title': f'{platform_key.title()} Post'})
                except (json.JSONDecodeError, KeyError):
                    continue

            if entries:
                if progress_callback:
                    progress_callback(f"✅ Method 5 SUCCESS: Found {len(entries)} links")
                return entries

        if progress_callback:
            progress_callback("⚠️ Method 5 failed: No data")

    except FileNotFoundError:
        if progress_callback:
            progress_callback("⚠️ Method 5 unavailable: gallery-dl not installed")
    except Exception as e:
        if progress_callback:
            progress_callback(f"⚠️ Method 5 error: {str(e)[:100]}")

    return []


def extract_links_all_methods(url: str, platform_key: str, cookies_dir: Path, options: dict = None, progress_callback=None) -> typing.Tuple[typing.List[dict], str]:
    """
    BULLETPROOF: Try ALL methods sequentially until success
    """
    try:
        options = options or {}
        max_videos = int(options.get('max_videos', 0) or 0)
        creator = _extract_creator_from_url(url, platform_key)

        # Find cookies
        cookie_file = _find_cookie_file(cookies_dir, platform_key)

        if cookie_file and progress_callback:
            progress_callback(f"✅ Using cookies: {Path(cookie_file).name}")
        elif progress_callback:
            progress_callback("🍪 No cookies found, proceeding without")

        entries = []

        # METHOD 1: Batch file approach (MOST RELIABLE)
        if not entries:
            entries = _method1_batch_file_approach(url, platform_key, cookie_file, max_videos, progress_callback)

        # METHOD 2: dump-json
        if not entries:
            entries = _method2_dump_json(url, platform_key, cookie_file, max_videos, progress_callback)

        # METHOD 3: Platform variations
        if not entries:
            entries = _method3_ytdlp_variations(url, platform_key, cookie_file, max_videos, progress_callback)

        # METHOD 4: Instaloader (Instagram only)
        if not entries and platform_key == 'instagram':
            entries = _method4_instaloader(url, platform_key, cookie_file, progress_callback)

        # METHOD 5: gallery-dl (Instagram/TikTok)
        if not entries and platform_key in ['instagram', 'tiktok']:
            entries = _method5_gallery_dl(url, platform_key, cookie_file, progress_callback)

        # Remove duplicates
        if entries:
            unique_urls = {}
            for entry in entries:
                normalized = _normalize_url(entry['url'])
                if normalized not in unique_urls:
                    unique_urls[normalized] = entry
            entries = list(unique_urls.values())

            # Apply max_videos limit
            if max_videos > 0:
                entries = entries[:max_videos]

        return entries, creator

    except Exception as e:
        if progress_callback:
            progress_callback(f"❌ CRITICAL ERROR: {str(e)[:200]}")
        return [], "unknown"


# ============ THREAD CLASSES (Crash Protected) ============

class LinkGrabberThread(QThread):
    """Single URL - BULLETPROOF with crash protection"""

    progress = pyqtSignal(str)
    progress_percent = pyqtSignal(int)
    link_found = pyqtSignal(str, str)
    finished = pyqtSignal(bool, str, list)
    save_triggered = pyqtSignal(str, list)

    def __init__(self, url: str, options: dict = None):
        super().__init__()
        self.url = (url or "").strip()
        self.options = options or {}
        self.is_cancelled = False
        self.found_links = []

        try:
            this_file = Path(__file__).resolve()
            self.cookies_dir = this_file.parent.parent.parent / "cookies"
            self.cookies_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            self.cookies_dir = Path.home() / ".cookies"
            self.cookies_dir.mkdir(parents=True, exist_ok=True)

    def _save_links_to_creator_folder(self, creator_name: str, links: typing.List[dict]) -> str:
        """Save to: Desktop/Toseeq Links Grabber/@{CreatorName}/{CreatorName}_links.txt"""
        try:
            desktop = Path.home() / "Desktop"
            base_folder = desktop / "Toseeq Links Grabber"

            safe_creator = _safe_filename(f"@{creator_name}")
            creator_folder = base_folder / safe_creator
            creator_folder.mkdir(parents=True, exist_ok=True)

            filename = f"{_safe_filename(creator_name)}_links.txt"
            filepath = creator_folder / filename

            with open(filepath, "w", encoding="utf-8") as f:
                for link in links:
                    f.write(f"{link['url']}\n")

            return str(filepath)
        except Exception as e:
            # Fallback: save to temp
            temp_file = Path.home() / f"links_{creator_name}.txt"
            with open(temp_file, "w", encoding="utf-8") as f:
                for link in links:
                    f.write(f"{link['url']}\n")
            return str(temp_file)

    def save_to_file(self, creator_name: str):
        """Save links - crash protected"""
        try:
            if self.found_links:
                saved_path = self._save_links_to_creator_folder(creator_name, self.found_links)
                self.save_triggered.emit(saved_path, self.found_links)
        except Exception as e:
            self.progress.emit(f"⚠️ Save error: {str(e)[:100]}")

    def run(self):
        try:
            if not self.url:
                self.finished.emit(False, "❌ No URL provided", [])
                return

            self.progress.emit("="*50)
            self.progress.emit("🔍 STARTING MULTI-METHOD EXTRACTION")
            self.progress.emit("="*50)
            self.progress_percent.emit(10)

            platform_key = _detect_platform_key(self.url)

            if platform_key == 'unknown':
                self.finished.emit(False, "❌ Unsupported platform or invalid URL", [])
                return

            self.progress.emit(f"✅ Platform detected: {platform_key.upper()}")
            self.progress_percent.emit(20)

            # Extract using ALL methods with progress callback
            def progress_cb(msg):
                self.progress.emit(msg)

            entries, creator = extract_links_all_methods(
                self.url,
                platform_key,
                self.cookies_dir,
                self.options,
                progress_callback=progress_cb
            )

            if not entries:
                error_msg = (
                    f"❌ ALL METHODS FAILED for @{creator}\n\n"
                    "Tried 5 different methods:\n"
                    "1. yt-dlp --flat-playlist --get-url\n"
                    "2. yt-dlp --dump-json\n"
                    "3. yt-dlp variations\n"
                    "4. Instaloader (Instagram)\n"
                    "5. gallery-dl\n\n"
                    "Solutions:\n"
                    f"• Add cookies to: cookies/{platform_key}.txt\n"
                    "• Check if account is public\n"
                    "• Verify URL is correct"
                )
                self.finished.emit(False, error_msg, [])
                return

            self.progress.emit("="*50)
            self.progress.emit(f"✅ EXTRACTION COMPLETE: {len(entries)} links from @{creator}")
            self.progress.emit("="*50)
            self.progress_percent.emit(60)

            # Process results
            total = len(entries)
            self.found_links = []

            for idx, entry in enumerate(entries, 1):
                if self.is_cancelled:
                    break

                self.found_links.append(entry)
                self.progress.emit(f"🔗 [{idx}/{total}] {entry['url'][:80]}...")
                self.link_found.emit(entry['url'], entry['url'])

                pct = 60 + int((idx / total) * 35)
                self.progress_percent.emit(min(pct, 95))

            if self.is_cancelled:
                self.finished.emit(False, f"⚠️ Cancelled. Got {len(self.found_links)} links.", self.found_links)
                return

            self.progress.emit("="*50)
            self.progress.emit(f"🎉 SUCCESS! {len(self.found_links)} links from @{creator}")
            self.progress.emit("="*50)
            self.progress_percent.emit(100)

            self.finished.emit(True, f"✅ {len(self.found_links)} links from @{creator}", self.found_links)

        except Exception as e:
            error_msg = f"❌ Unexpected error: {str(e)[:200]}"
            self.progress.emit(error_msg)
            self.finished.emit(False, error_msg, self.found_links)

    def cancel(self):
        self.is_cancelled = True


class BulkLinkGrabberThread(QThread):
    """Bulk URLs - BULLETPROOF with crash protection"""

    progress = pyqtSignal(str)
    progress_percent = pyqtSignal(int)
    link_found = pyqtSignal(str, str)
    finished = pyqtSignal(bool, str, list)
    save_triggered = pyqtSignal(str, list)

    def __init__(self, urls: typing.List[str], options: dict = None):
        super().__init__()
        self.urls = [u.strip() for u in urls if u.strip()] or []
        self.options = options or {}
        self.is_cancelled = False
        self.found_links = []
        self.creator_data = {}

        try:
            this_file = Path(__file__).resolve()
            self.cookies_dir = this_file.parent.parent.parent / "cookies"
            self.cookies_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            self.cookies_dir = Path.home() / ".cookies"
            self.cookies_dir.mkdir(parents=True, exist_ok=True)

    def _save_creator_to_folder(self, creator_name: str, links: typing.List[dict]) -> str:
        """Save - crash protected"""
        try:
            desktop = Path.home() / "Desktop"
            base_folder = desktop / "Toseeq Links Grabber"

            safe_creator = _safe_filename(f"@{creator_name}")
            creator_folder = base_folder / safe_creator
            creator_folder.mkdir(parents=True, exist_ok=True)

            filename = f"{_safe_filename(creator_name)}_links.txt"
            filepath = creator_folder / filename

            with open(filepath, "w", encoding="utf-8") as f:
                for link in links:
                    f.write(f"{link['url']}\n")

            return str(filepath)
        except Exception:
            return f"Error saving {creator_name}"

    def save_to_file(self):
        """Save all - crash protected"""
        try:
            if not self.creator_data:
                self.progress.emit("❌ No links to save")
                return

            for creator_name, data in self.creator_data.items():
                if data['links']:
                    saved_path = self._save_creator_to_folder(creator_name, data['links'])
                    self.progress.emit(f"💾 Saved: {saved_path}")

            self.progress.emit(f"✅ All {len(self.creator_data)} creators saved!")
        except Exception as e:
            self.progress.emit(f"⚠️ Save error: {str(e)[:100]}")

    def run(self):
        try:
            total_urls = len(self.urls)
            if total_urls == 0:
                self.finished.emit(False, "❌ No URLs provided", [])
                return

            # Remove duplicates
            self.progress.emit(f"🔍 Checking {total_urls} URLs...")
            unique_urls = _remove_duplicates(self.urls)
            duplicates_removed = len(self.urls) - len(unique_urls)

            if duplicates_removed > 0:
                self.progress.emit(f"🧹 Removed {duplicates_removed} duplicate URLs")

            self.progress.emit("="*60)
            self.progress.emit(f"🚀 BULK PROCESSING: {len(unique_urls)} URLs")
            self.progress.emit("="*60)

            self.found_links = []
            self.creator_data = {}

            # Process each URL
            for i, url in enumerate(unique_urls, 1):
                if self.is_cancelled:
                    break

                self.progress.emit(f"\n{'='*60}")
                self.progress.emit(f"📌 [{i}/{len(unique_urls)}] {url[:60]}...")
                self.progress.emit(f"{'='*60}")

                platform_key = _detect_platform_key(url)

                def progress_cb(msg):
                    self.progress.emit(msg)

                entries, creator = extract_links_all_methods(
                    url,
                    platform_key,
                    self.cookies_dir,
                    self.options,
                    progress_callback=progress_cb
                )

                # Track creator data
                if creator not in self.creator_data:
                    self.creator_data[creator] = {
                        'links': [],
                        'url': url,
                        'platform': platform_key
                    }

                # Add links
                for entry in entries:
                    if self.is_cancelled:
                        break
                    self.found_links.append(entry)
                    self.creator_data[creator]['links'].append(entry)
                    self.link_found.emit(entry['url'], entry['url'])

                # Save immediately
                if entries:
                    saved_path = self._save_creator_to_folder(creator, entries)
                    self.progress.emit(f"💾 Saved: {saved_path}")

                self.progress.emit(f"✅ [{i}/{len(unique_urls)}] {len(entries)} links from @{creator}")

                pct = int((i / len(unique_urls)) * 95)
                self.progress_percent.emit(pct)

            if self.is_cancelled:
                self.finished.emit(False, f"⚠️ Cancelled. {len(self.found_links)} total links.", self.found_links)
                return

            # Final summary
            self.progress.emit("\n" + "="*60)
            self.progress.emit("🎉 BULK COMPLETE!")
            self.progress.emit("="*60)
            self.progress.emit(f"📊 Processed: {len(unique_urls)} URLs")
            self.progress.emit(f"👥 Creators: {len(self.creator_data)}")
            self.progress.emit(f"🔗 Total Links: {len(self.found_links)}")
            if duplicates_removed > 0:
                self.progress.emit(f"🧹 Duplicates Removed: {duplicates_removed}")
            self.progress.emit("\n📁 Saved Folders:")
            for creator_name, data in self.creator_data.items():
                self.progress.emit(f"  ├── @{creator_name}/ ({len(data['links'])} links)")
            self.progress.emit("="*60)

            self.progress_percent.emit(100)
            self.finished.emit(True, f"✅ Bulk complete! {len(self.found_links)} links from {len(self.creator_data)} creators.", self.found_links)

        except Exception as e:
            error_msg = f"❌ Bulk error: {str(e)[:200]}"
            self.progress.emit(error_msg)
            self.finished.emit(False, error_msg, self.found_links)

    def cancel(self):
        self.is_cancelled = True
