# Task: Improve Link Grabber Reliability
**Date:** 2026-02-23
**Scope:** All 4 platforms — Instagram, TikTok, Facebook, YouTube
**Focus:** Reliability & Retry (not UI, not new platforms)

---

## Problem Analysis

### Instagram
- yt-dlp extractor is officially broken (marked by yt-dlp project 2025)
- Method B (Mobile API) is the correct primary path but silently fails when `sessionid` cookie is missing/expired
- No per-attempt error classification — 429 (rate-limit) vs 401 (bad cookie) vs 403 (blocked) all treated the same
- CDP attach (Method D) falls back silently when Chrome has no debug port — no guidance given to user
- No retry-with-backoff on 429; just moves to next method immediately

### TikTok
- yt-dlp works but gets 403 if cookies not supplied
- No platform-specific cookie filtering for TikTok (uses full master cookie file)
- Selenium scroll method has hardcoded stagnant_limit=3 — too aggressive, causes early exit
- No validation that TikTok cookies contain `sessionid` and `tt_chain_token` (minimum required)

### Facebook
- Method C (JSON extraction) regex patterns miss most modern FB page structures (2025+ relay store format)
- fb_profile_shape detection is over-broad — causes Selenium-only path even for reels URLs
- CDP attach (Method D) timeout is 4s page load — too short for heavy FB pages
- No retry on temporary login-redirects

### YouTube
- URL normalization always appends `/videos` — breaks `/shorts` and `/streams` tab users
- yt-dlp Python API fails with `extract_flat` for large channels; binary fallback not always triggered
- No detection of "members-only" or "sign-in required" responses; method is silently skipped
- Timeout of 30s too short for large playlists (1000+ videos)

### General / Orchestrator
- `_method_old_batch_file` and `_method_old_dump_json` both run first for ALL platforms — including Instagram where yt-dlp is broken. This wastes 2 method slots and ~60s before reaching working methods.
- No per-method timeout enforcement — one hanging method can stall the whole run
- `between_methods_delay` of 2-4s random is hardcoded in orchestrator; should use config
- Cookie freshness check issues: warns but never blocks bad-cookie methods
- No structured error classification: 429, 403, 401, network timeout all treated identically
- Progress messages contain garbled emoji (mojibake) in logs

---

## Implementation Plan

### Change 1 — Skip broken yt-dlp methods for Instagram (core.py: ~line 3974)
**What:** Add Instagram to the existing `platform_key == 'instagram'` block that filters `all_methods`.
Currently `_method_old_batch_file` and `_method_old_dump_json` are listed with `allowed=True` for all platforms including Instagram, so they always run first and waste 30-60s each.
**Fix:** Change the `allowed` lambda for OLD Method 9 and OLD Method 10 to `platform_key != 'instagram'`.

```python
# OLD Method 9 — change allowed from: True
# to: platform_key != 'instagram'

# OLD Method 10 — change allowed from: True
# to: platform_key != 'instagram'
```

**File:** `modules/link_grabber/core.py` lines ~3976–3982

---

### Change 2 — Per-method timeout wrapper (core.py: orchestrator loop ~line 4173)
**What:** Wrap each `method_func()` call in a thread with a configurable timeout so a single hanging method doesn't freeze the whole run.
Use `concurrent.futures.ThreadPoolExecutor` with a per-method timeout (default 120s, configurable in `config.py`).

**Add to config.py:**
```python
RETRY_CONFIG = {
    ...
    'per_method_timeout': 120,   # Max seconds per method before abandoning
}
```

**In orchestrator loop replace:**
```python
method_entries = method_func()
```
**With:**
```python
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
per_method_timeout = RETRY_CONFIG.get('per_method_timeout', 120)
with ThreadPoolExecutor(max_workers=1) as executor:
    future = executor.submit(method_func)
    try:
        method_entries = future.result(timeout=per_method_timeout)
    except FuturesTimeout:
        future.cancel()
        method_entries = []
        if progress_callback:
            progress_callback(f"⏱ {method_name} timed out after {per_method_timeout}s")
    except Exception as e:
        method_entries = []
        error_msg = str(e)[:200]
```

**File:** `modules/link_grabber/core.py` lines ~4184–4189

---

### Change 3 — Error classification helper (core.py: new helper function)
**What:** Add `_classify_error(error_str)` that returns one of: `'rate_limit'`, `'auth_failed'`, `'not_found'`, `'network'`, `'unknown'`.
Use this in the orchestrator to:
- Skip remaining yt-dlp methods immediately on `auth_failed` (bad cookies) and jump to browser methods
- Apply longer backoff (10-15s) on `rate_limit` instead of the current 2-4s
- Log the category so users see "Rate limited (429) — waiting 12s" rather than generic failure

```python
def _classify_error(error_str: str) -> str:
    err = (error_str or '').lower()
    if '429' in err or 'rate limit' in err or 'too many requests' in err:
        return 'rate_limit'
    if '401' in err or '403' in err or 'login required' in err or 'sign in' in err or 'not logged in' in err:
        return 'auth_failed'
    if '404' in err or 'not found' in err:
        return 'not_found'
    if 'timeout' in err or 'connection' in err or 'network' in err:
        return 'network'
    return 'unknown'
```

**File:** `modules/link_grabber/core.py` — add after `_mask_proxy` (~line 264)

---

### Change 4 — TikTok cookie validation (core.py: new helper function)
**What:** Add `_validate_tiktok_cookies(cookie_file)` that checks for the presence of at minimum `sessionid` and `tt_chain_token` fields.
Called before any TikTok yt-dlp method. If missing, skip directly to Selenium/CDP methods.

```python
def _validate_tiktok_cookies(cookie_file: str) -> bool:
    """Returns True if cookie file contains minimum required TikTok session tokens."""
    required = {'sessionid', 'tt_chain_token'}
    if not cookie_file or not os.path.exists(cookie_file):
        return False
    try:
        found = set()
        with open(cookie_file, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                if line.startswith('#') or not line.strip():
                    continue
                parts = line.strip().split('\t')
                if len(parts) >= 6:
                    name = parts[5]
                    if name in required:
                        found.add(name)
        return required.issubset(found)
    except Exception:
        return False
```

**File:** `modules/link_grabber/core.py` — add after `_validate_cookie_file` (~line 372)

**Usage in orchestrator:** Before the method loop, compute `tiktok_cookies_valid = _validate_tiktok_cookies(cookie_file) if platform_key == 'tiktok' else True`. Then in `all_methods`, for OLD Method 9/10 with TikTok: set `allowed` to `tiktok_cookies_valid`.

---

### Change 5 — Fix YouTube URL normalization (core.py: ~line 3872)
**What:** The current logic always appends `/videos` to channel URLs with no tab. This breaks users who want `/shorts` or `/streams`.
**Fix:** Only append `/videos` if the URL has no recognizable video content already. And when the user's URL contains `/shorts` or `/streams` anywhere, don't change it.

```python
# Current (broken for /shorts, /streams):
if platform_key == 'youtube' and '@' in url:
    if not any(suffix in url for suffix in ['/videos', '/shorts', '/streams', ...]):
        url = f"{url.rstrip('/')}/videos"  # Always defaults to /videos

# Fixed:
if platform_key == 'youtube' and '@' in url:
    has_tab = any(suffix in url for suffix in ['/videos', '/shorts', '/streams', '/playlists', '/community', '/channels', '/about'])
    # Only auto-append /videos when no tab is present AND URL looks like a bare channel
    if not has_tab:
        url = f"{url.rstrip('/')}/videos"
        # Additionally try /videos then /shorts as separate attempts if /videos returns 0
        # This is handled by the retry logic in Change 6
```

No functional change to this block — the logic is already correct as written. **The actual fix is in Change 6**: retry with `/shorts` if `/videos` returns 0 results.

---

### Change 6 — YouTube tab fallback retry (core.py: after main method loop, ~line 4255)
**What:** If YouTube extraction returns 0 results and the URL was auto-normalized to `/videos`, retry once with `/shorts` and once with the bare channel URL (no tab).

```python
# After the main method loop, before the proxy-retry block:
if not entries and platform_key == 'youtube' and url != original_url:
    # Try /shorts tab
    for alt_tab in ['/shorts', '']:
        if entries:
            break
        alt_url = original_url.rstrip('/') + alt_tab if alt_tab else original_url.rstrip('/')
        if progress_callback:
            progress_callback(f"YouTube: Retrying with tab: {alt_url}")
        for method_name, method_func_orig in available_methods[:3]:  # top 3 methods only
            # rebuild lambda with alt_url bound
            ...
```

**Implementation detail:** Build a small `_youtube_tab_retry(original_url, tabs, cookie_file, max_videos, cookie_browser, active_proxy)` helper that loops over `['/shorts', '/streams', '']` and calls `_method_old_dump_json` / `_method_ytdlp_dump_json` with each.

---

### Change 7 — Facebook JSON method regex update (core.py: `_method_facebook_json` ~line 3278)
**What:** The current regex patterns are too specific for old FB HTML. Add patterns for the modern Relay store format used since 2024.

**Add these patterns:**
```python
# Modern Facebook Relay / __SSR_INITIAL_DATA__ patterns (2024+)
r'"video_id":"(\d{10,20})"',         # raw video_id in relay JSON → /watch/?v={id}
r'"story_id":"(\d{10,20})"',         # story IDs
r'\"permalink_url\":\"(https://www\\.facebook\\.com/[^"]+)\"',  # full permalink
r'"url":"(https:\\\\/\\\\/www\\.facebook\\.com\\\\/reel\\\\/[^"]+)"',  # escaped
```

Post-process `video_id` matches as `https://www.facebook.com/watch/?v={video_id}`.

---

### Change 8 — CDP attach page load timeout (core.py: `_method_selenium_cdp_attach` ~line 3371)
**What:** Current `driver.get(url)` + `time.sleep(4)` is too short for heavy FB pages.
**Fix:** Increase page load timeout to 45s and use explicit wait for page body instead of `time.sleep`.

```python
driver.set_page_load_timeout(45)  # was 30
driver.get(url)
# Replace time.sleep(4) with explicit wait:
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
try:
    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.TAG_NAME, "body"))
    )
except Exception:
    time.sleep(6)
```

**File:** `modules/link_grabber/core.py` ~line 3370–3374

---

### Change 9 — Rate-limit aware backoff in orchestrator (core.py: ~line 4248)
**What:** Replace the fixed `random.uniform(2.0, 4.0)` delay between failed methods with error-class-aware backoff.

```python
# Current:
delay = random.uniform(2.0, 4.0)

# Fixed (using _classify_error result stored from method failure):
if error_class == 'rate_limit':
    delay = random.uniform(10.0, 15.0)
    if progress_callback:
        progress_callback(f"Rate limited — waiting {delay:.0f}s before retry...")
elif error_class == 'auth_failed':
    delay = 1.0  # No point waiting long; credentials are bad
else:
    delay = random.uniform(2.0, 4.0)
```

---

## Files to Modify

| File | Changes |
|------|---------|
| `modules/link_grabber/core.py` | Changes 1, 2, 3, 4, 5 (line ~3872), 6, 7, 8, 9 |
| `modules/link_grabber/config.py` | Change 2: add `per_method_timeout` to `RETRY_CONFIG` |

## Estimated Change Size
- `core.py`: ~150-200 lines changed/added (across many locations)
- `config.py`: ~3 lines

## Order of Implementation
1. Change 1 (easiest, highest impact for Instagram)
2. Change 3 (error classifier — needed by Changes 9 and others)
3. Change 9 (use classifier in backoff)
4. Change 2 (per-method timeout)
5. Change 4 (TikTok cookie validation)
6. Change 7 (Facebook JSON regex)
7. Change 8 (CDP timeout fix)
8. Change 6 (YouTube tab fallback)
9. Change 5 (YouTube URL — verify no regression)

## Testing Checklist
- [ ] Instagram profile URL → Method B succeeds with sessionid cookie
- [ ] TikTok profile URL with cookies → OLD Method 9 works; without TikTok cookies → skips to Selenium
- [ ] Facebook profile URL → Method C finds reels; falls back to CDP if not
- [ ] YouTube channel URL → `/videos` tab, then `/shorts` fallback
- [ ] Hanging method (simulated) → aborted after `per_method_timeout` seconds
- [ ] 429 response → longer backoff applied, next method gets correct delay
