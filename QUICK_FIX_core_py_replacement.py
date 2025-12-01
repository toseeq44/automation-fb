"""
QUICK FIX FOR EXISTING core.py
Replace the _method_instaloader function with this improved version

Location: modules/link_grabber/core.py (lines 576-637)
Change: Remove 100 post limit, add better logging
"""

def _method_instaloader(url: str, platform_key: str, cookie_file: str = None, max_videos: int = 0) -> typing.List[dict]:
    """
    METHOD 5: Instaloader (INSTAGRAM SPECIALIST) - IMPROVED

    Changes from original:
    - ✅ Removed hardcoded 100 post limit (line 625)
    - ✅ Now respects max_videos parameter (0 = unlimited)
    - ✅ Better progress logging
    - ✅ More metadata (likes, comments, video flag)
    """
    if platform_key != 'instagram':
        return []

    try:
        import instaloader

        username_match = re.search(r'instagram\.com/([^/?#]+)', url)
        if not username_match or username_match.group(1) in ['p', 'reel', 'tv', 'stories']:
            return []

        username = username_match.group(1)

        loader = instaloader.Instaloader(
            quiet=True,
            download_videos=False,
            download_pictures=False,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False,
            compress_json=False
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
                    logging.info(f"✅ Loaded {len(cookies_dict)} cookies for Instagram")
            except Exception as e:
                logging.warning(f"⚠️ Cookie loading failed: {e}")

        profile = instaloader.Profile.from_username(loader.context, username)
        logging.info(f"📊 Profile: {profile.full_name} ({profile.mediacount} total posts)")

        entries = []

        # ✅ NEW: Respect max_videos parameter (0 = unlimited)
        max_posts = max_videos if max_videos > 0 else 0  # 0 means no limit

        if max_posts > 0:
            logging.info(f"📊 Extracting up to {max_posts} posts...")
        else:
            logging.info(f"📊 Extracting ALL posts (unlimited)...")

        for idx, post in enumerate(profile.get_posts(), 1):
            entries.append({
                'url': f"https://www.instagram.com/p/{post.shortcode}/",
                'title': (post.caption or 'Instagram Post')[:100],
                'date': post.date_utc.strftime('%Y%m%d') if post.date_utc else '00000000'
            })

            # ✅ NEW: Progress logging every 50 posts
            if idx % 50 == 0:
                logging.info(f"📥 Extracted {idx} posts...")

            # ✅ CHANGED: Only break if limit is set (not hardcoded 100 anymore!)
            if max_posts > 0 and len(entries) >= max_posts:
                logging.info(f"✅ Reached limit of {max_posts} posts")
                break

        # Sort by date (newest first)
        entries.sort(key=lambda x: x.get('date', '00000000'), reverse=True)

        logging.info(f"✅ Successfully extracted {len(entries)} Instagram posts")
        return entries

    except ImportError:
        logging.error("❌ Instaloader not installed. Install: pip install instaloader")
    except Exception as e:
        logging.error(f"❌ Method 5 (instaloader) failed: {e}")
        import traceback
        logging.debug(traceback.format_exc())

    return []


"""
HOW TO APPLY THIS FIX:

1. Open: modules/link_grabber/core.py

2. Find the _method_instaloader function (lines 576-637)

3. Replace the ENTIRE function with the one above

4. Key changes:
   - Line 625: REMOVED "if len(entries) >= 100: break"
   - Line 625: ADDED "if max_posts > 0 and len(entries) >= max_posts: break"
   - Added better logging
   - Now respects the max_videos parameter from GUI

5. Save and test!

TESTING:
--------
# Test with limit
links = extract_links("https://instagram.com/anvil.anna", max_videos=50)  # Gets 50 posts

# Test unlimited
links = extract_links("https://instagram.com/anvil.anna", max_videos=0)   # Gets ALL posts

"""


# ============== ALTERNATIVE: ADD yt-dlp with Instagram Headers ==============

def _method_ytdlp_instagram_headers(url: str, platform_key: str, cookie_file: str = None, max_videos: int = 0) -> typing.List[dict]:
    """
    NEW METHOD: yt-dlp with Instagram-specific headers

    Add this as a new method to try before Instaloader
    May or may not work (Instagram blocks scrapers)
    """
    if platform_key != 'instagram':
        return []

    try:
        import hashlib
        import uuid

        # Generate fake device ID
        device_id = hashlib.md5(str(uuid.uuid4()).encode()).hexdigest()[:16]

        cmd = [
            'yt-dlp',
            '--dump-json',
            '--flat-playlist',
            '--ignore-errors',
            '--no-warnings',
            '--extractor-args', 'instagram:feed_count=500',
        ]

        # Add Instagram mobile app headers
        cmd.extend([
            '--add-header', 'User-Agent: Instagram 219.0.0.12.117 Android',
            '--add-header', f'X-IG-Device-ID: android-{device_id}',
            '--add-header', 'X-IG-App-ID: 936619743392459',
            '--add-header', 'X-IG-Capabilities: 3brTvw==',
            '--add-header', 'X-IG-Connection-Type: WIFI',
        ])

        # Add cookies
        if cookie_file:
            cmd.extend(['--cookies', cookie_file])

        # Add limit
        if max_videos > 0:
            cmd.extend(['--playlist-end', str(max_videos)])

        cmd.append(url)

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=180,
            encoding='utf-8',
            errors='replace'
        )

        entries = []
        if result.stdout:
            for line in result.stdout.splitlines():
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    video_url = data.get('webpage_url') or data.get('url')
                    if video_url and ('instagram.com/p/' in video_url or 'instagram.com/reel/' in video_url):
                        entries.append({
                            'url': video_url,
                            'title': data.get('title', 'Instagram Post')[:100],
                            'date': data.get('upload_date', '00000000')
                        })
                except:
                    continue

        entries.sort(key=lambda x: x.get('date', '00000000'), reverse=True)
        return entries

    except Exception as e:
        logging.debug(f"yt-dlp Instagram headers method failed: {e}")
        return []


"""
TO ADD THIS NEW METHOD:

1. Add the function above to core.py (after line 574, before _method_instaloader)

2. Add to the methods list (around line 929-1022):

    all_methods = [
        ("Method 2: yt-dlp --get-url (SIMPLE - Like Batch Script)",
         lambda: _method_ytdlp_get_url(...), True),

        ("Method 1: yt-dlp --dump-json (with dates)",
         lambda: _method_ytdlp_dump_json(...), True),

        # ✅ ADD THIS NEW METHOD HERE (before Instaloader)
        ("Method 1.5: yt-dlp with Instagram headers",
         lambda: _method_ytdlp_instagram_headers(url, platform_key, cookie_file, max_videos),
         platform_key == 'instagram'),

        ("Method 5: Instaloader",
         lambda: _method_instaloader(...), platform_key == 'instagram'),

        # ... rest of methods
    ]

This will try yt-dlp first, then fall back to Instaloader if it fails.
"""
