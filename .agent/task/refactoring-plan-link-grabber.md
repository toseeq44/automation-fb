# Refactoring Plan: Link Grabber (`core.py`)
**Date:** 2026-02-23
**Status:** Planning
**File:** `modules/link_grabber/core.py` (4,748 lines)
**Config:** `modules/link_grabber/config.py`

---

## PHASE 1: CLEANUP — Duplicate Method Removal

### Problem
4 yt-dlp methods are near-identical (95% overlap). OLD Methods 9 & 10 were added as
"proven fallbacks" but are just stripped-down duplicates of Methods 1 & 2.
All 4 run sequentially — wasting 60–120 seconds before reaching working methods.

### Step 1.1 — Methods to DELETE (completely remove)

| Function to DELETE | Duplicate of | Reason |
|--------------------|--------------|--------|
| `_method_old_batch_file()` (~line 3505) | `_method_ytdlp_get_url()` | Same command: `--get-url --flat-playlist`. Old version has NO Chrome headers. Enhanced is strictly better. |
| `_method_old_dump_json()` (~line 3581) | `_method_ytdlp_dump_json()` | Same command: `--dump-json --flat-playlist`. Old version has NO Chrome headers. |
| `_method_old_instaloader()` (~line 3669) | `_method_instaloader()` | Same library. Old version has fewer features and no configurable rate limits. |
| `_method_ytdlp_user_agent()` (~line 1778) | `_method_ytdlp_enhanced()` | Enhanced already rotates UA internally. Separate UA method adds no value. |

**After deletion:** Remove their entries from `all_methods` list in orchestrator (~lines 3974–3049).

---

### Step 1.2 — Methods to KEEP (canonical set)

After cleanup, the yt-dlp method set becomes:

| Canonical Name | Renamed From | Tool | Keep? |
|----------------|-------------|------|-------|
| `_method_ytdlp_enhanced()` | Method 0 | yt-dlp Python API + binary | YES — primary yt-dlp method |
| `_method_ytdlp_dump_json()` | Method 1 | yt-dlp binary `--dump-json` | YES — has dates; good for playlists |
| `_method_ytdlp_get_url()` | Method 2 | yt-dlp binary `--get-url` | YES — fastest; good for TikTok |
| `_method_ytdlp_with_retry()` | Method 3 | yt-dlp binary high-retry | YES — stubborn extractors |

**Total yt-dlp methods: 4** (was 7+).

---

### Step 1.3 — Methods to RENAME (for clarity)

| Old Name | New Name | Reason |
|----------|----------|--------|
| `_method_ytdlp_enhanced()` | `_method_ytdlp_primary()` | "Enhanced" is vague — it's the PRIMARY yt-dlp method |
| `_method_instagram_web_api()` | `_method_instagram_graphql()` | It uses GraphQL; name should reflect this |
| `_method_existing_browser_session()` | `_method_selenium_profile()` | Clarifies it uses Selenium with a Chrome user-data-dir |
| `_method_interactive_browser_session()` | `_method_selenium_manual_login()` | "Interactive" is ambiguous |

---

### Step 1.4 — Final Canonical Method List (after cleanup)

```
YT-DLP METHODS (platforms: YouTube, TikTok, Facebook — NOT Instagram)
  _method_ytdlp_primary()       [was: Method 0 enhanced]
  _method_ytdlp_dump_json()     [was: Method 1]
  _method_ytdlp_get_url()       [was: Method 2]
  _method_ytdlp_with_retry()    [was: Method 3]

INSTAGRAM-SPECIFIC METHODS
  _method_instagram_mobile_api()   [Method B — FASTEST, needs sessionid]
  _method_instagram_graphql()      [was: Method 6b — needs all cookies]
  _method_instaloader()            [Method 5 — opt-in only, slow]

FACEBOOK-SPECIFIC METHODS
  _method_facebook_json()       [Method C — fast, needs c_user+xs]

BROWSER METHODS (all platforms)
  _method_selenium_cdp_attach()    [Method D — best: real Chrome session]
  _method_selenium_profile()       [was: Method A — reuse Chrome profile]
  _method_selenium()               [Method 8 — headless + cookies]
  _method_playwright()             [Method 7 — stealth browser]
  _method_selenium_manual_login()  [was: Interactive — last resort]

UTILITY
  _method_gallery_dl()             [Method 6 — TikTok/Instagram fallback]
```

**Total methods: 13** (was ~18). 5 removed.

---

### Step 1.5 — Verification After Phase 1

- [ ] Search codebase for any remaining calls to deleted functions
- [ ] Run `grep -n "_method_old_" core.py` — must return 0 results
- [ ] Confirm `all_methods` list in orchestrator has no deleted function references
- [ ] Check `intelligence.py` learning cache — purge any cached method names that were renamed

---

## PHASE 2: COOKIE SYSTEM FIX

### Problem Summary
- Chrome 127+ cookies cannot be decrypted by `browser_cookie3` (v20 encryption)
- Cookie warnings are shown but never acted on
- TikTok has no `sessionid`/`tt_chain_token` validation
- Temp files can accumulate on crash

---

### Step 2.1 — CDP Cookie Extraction (Chrome 127+ fix)

**Location to add:** After `_extract_browser_cookies_db_copy()` in cookie chain.

Add a new helper `_extract_cookies_via_cdp(platform_key, cookies_dir)`:

```python
# Logic outline (DO NOT code yet):
# 1. Check if Chrome is running with debug port (try 9222, 9223, 9224)
# 2. If yes: use requests to hit http://localhost:9222/json/version
# 3. Use websocket to call Network.getCookies via CDP
# 4. Filter cookies by platform domain tokens
# 5. Write to Netscape format → save to cookies_dir/chrome_cookies.txt
# 6. Return path to file
```

**Where to insert in priority chain** (in `extract_links_intelligent`):

```
Current priority chain:
  1. Browser extraction (bc3)
  2. DB copy (Workflow 1)
  3. Saved file
  4. Auto smart detect

New priority chain:
  1. Saved file (check freshness first — see Step 2.2)
  2. CDP cookie extraction (if Chrome running on debug port)
  3. DB copy (Workflow 1)
  4. Browser extraction (bc3)
  5. Auto smart detect
```

**Why saved file is #1 now:** If user already has a fresh valid file, skip all browser extraction overhead.

---

### Step 2.2 — Cookie Warnings → Blocking Actions

**Current behavior** (lines 3836–3843):
```python
if validation['warnings']:
    for warning in validation['warnings']:
        progress_callback(warning)
# continues extraction regardless
```

**New behavior — 3 severity levels:**

```
LEVEL 1 (warn + continue): age_days > 14, some cookies expired (<50%)
  → Show warning, proceed normally

LEVEL 2 (warn + skip cookie methods): expired > 50% OR file age > 30 days
  → Skip all yt-dlp/API cookie methods
  → Go directly to browser methods (Selenium/CDP)
  → Show: "Cookies too stale. Using browser session instead."

LEVEL 3 (block + prompt): file is empty OR < 10 bytes
  → Stop extraction
  → Show: "Cookie file invalid. Please re-export cookies."
  → Return empty list immediately
```

**Config addition to `config.py`:**
```python
COOKIE_CONFIG = {
    'warn_age_days': 14,        # Warn but continue
    'skip_cookie_methods_age': 30,  # Skip cookie methods; use browser
    'expired_pct_threshold': 50,    # Skip if >50% expired
}
```

---

### Step 2.3 — TikTok Cookie Validation

Add helper `_validate_platform_cookies(cookie_file, platform_key)`:

```python
# Logic outline:
# TIKTOK: Required names = {'sessionid', 'tt_chain_token'}
# INSTAGRAM: Required names = {'sessionid'}
# FACEBOOK: Required names = {'c_user', 'xs'}
# YOUTUBE: Required names = {'SID', 'HSID'} (optional — yt-dlp works without login)
#
# Returns: dict {
#   'valid': bool,
#   'missing': list[str],   # missing cookie names
#   'found': list[str],     # found cookie names
# }
```

**Usage in orchestrator:**
```
Before attempting yt-dlp/API methods for TikTok:
  result = _validate_platform_cookies(cookie_file, 'tiktok')
  if not result['valid']:
      progress_callback(f"TikTok cookies missing: {result['missing']} — skipping yt-dlp")
      skip_ytdlp = True
```

---

### Step 2.4 — Temp Cookie File Cleanup

**Current problem:** `temp_cookie_files` list tracked but cleanup unreliable on crash.

**Fix:** Use context manager pattern:

```python
# Logic outline:
# Create a TempCookieManager class or use contextlib.ExitStack:
#
# with TempCookieManager() as tcm:
#     cookie_file = tcm.add(extracted_file)
#     # ... extraction runs ...
# # temp files auto-deleted here even if exception thrown
```

**Or simpler:** Register cleanup with `atexit` + explicit try/finally already in place — just ensure the `finally` block runs `os.remove()` for each path in `temp_cookie_files` even if extraction thread is killed.

---

### Step 2.5 — Verification After Phase 2

- [ ] Test with fresh `chrome_cookies.txt` (< 14 days) — should proceed without warnings
- [ ] Test with file > 30 days old — should skip cookie methods, use browser
- [ ] Test with TikTok URL + cookies without `sessionid` — should show "missing token" message and skip yt-dlp
- [ ] Test CDP extraction — should auto-detect debug port and extract cookies
- [ ] Verify no `.tmp` files remain in `%TEMP%` after extraction finishes/crashes

---

## PHASE 3: ERROR HANDLING IMPROVEMENT

### Problem Summary
- 429/401/403 all caught as generic `Exception`
- `_retry_on_failure()` only used by Instaloader — not by yt-dlp or browser methods
- No per-method timeout — one hanging Playwright session can stall for hours
- Import errors silently make methods unavailable without user notification

---

### Step 3.1 — Error Classifier Function

Add `_classify_error(error_str: str) -> str` after `_mask_proxy()` (~line 264):

```python
# Logic outline:
# Input: exception message string
# Output: one of: 'rate_limit', 'auth_failed', 'not_found', 'network', 'unknown'
#
# Detection rules:
#   rate_limit  → '429' in err OR 'too many' in err OR 'rate limit' in err
#   auth_failed → '401' in err OR '403' in err OR 'login required' in err
#                 OR 'sign in' in err OR 'not logged in' in err
#   not_found   → '404' in err OR 'not found' in err OR 'unavailable' in err
#   network     → 'timeout' in err OR 'connection' in err OR 'network' in err
#                 OR 'socket' in err
#   unknown     → everything else
```

---

### Step 3.2 — Error-Class-Aware Backoff

**Replace** the hardcoded `random.uniform(2.0, 4.0)` between-method delay
(orchestrator ~line 4248) with:

```python
# Backoff table (add to DELAY_CONFIG in config.py):
'error_backoff': {
    'rate_limit':  (10.0, 15.0),   # 429 — wait before next method
    'auth_failed': (0.5,   1.0),   # Bad cookies — no point waiting long
    'not_found':   (0.5,   1.0),   # Content removed — no point retrying
    'network':     (5.0,  10.0),   # Network issue — moderate wait
    'unknown':     (2.0,   4.0),   # Default
}

# Usage in orchestrator loop:
# error_class = _classify_error(error_msg)
# min_d, max_d = DELAY_CONFIG['error_backoff'][error_class]
# delay = random.uniform(min_d, max_d)
# progress_callback(f"[{error_class.upper()}] Waiting {delay:.1f}s...")
```

---

### Step 3.3 — Smart Skip on Auth Failure

If `error_class == 'auth_failed'` and the failing method was a cookie-based method:

```python
# In orchestrator loop, after classifying error:
if error_class == 'auth_failed' and cookie_file:
    progress_callback("Auth failure detected — cookies may be invalid.")
    progress_callback("Skipping remaining cookie-based methods.")
    # Filter available_methods to keep only browser methods
    available_methods = [
        (n, f) for n, f in available_methods
        if 'selenium' in n.lower() or 'playwright' in n.lower()
           or 'cdp' in n.lower() or 'browser' in n.lower()
    ]
```

---

### Step 3.4 — Per-Method Timeout Wrapper

Add to `config.py`:
```python
RETRY_CONFIG = {
    ...existing...,
    'per_method_timeout': 120,   # seconds; 0 = no timeout
}
```

Add helper `_run_with_timeout(func, timeout_seconds)`:

```python
# Logic outline:
# Use concurrent.futures.ThreadPoolExecutor(max_workers=1)
# Submit func to executor
# Call future.result(timeout=timeout_seconds)
# On TimeoutError: cancel future, return ([], 'timeout')
# On success: return (result, None)
# On exception: return ([], str(exception))
```

**Usage in orchestrator loop:**

```python
# Replace:
method_entries = method_func()

# With:
method_entries, err = _run_with_timeout(method_func, per_method_timeout)
if err == 'timeout':
    progress_callback(f"⏱ {method_name} timed out after {per_method_timeout}s — skipping")
    error_class = 'network'
    continue
```

---

### Step 3.5 — Import Error Notification at Startup

Add `_check_optional_dependencies()` function — called once when module loads:

```python
# Logic outline:
# Check imports: yt_dlp, selenium, playwright, instaloader, gallery_dl
# For each: try import, record True/False
# Store in module-level dict: AVAILABLE_TOOLS = {'yt_dlp': True, 'selenium': False, ...}
#
# Usage in orchestrator:
# When building all_methods, set allowed=False for methods
# whose required tool is not in AVAILABLE_TOOLS
# Show one-time warning: "Selenium not installed — browser methods unavailable"
```

**Add availability check to `all_methods` list:**

```python
# Example:
("Method 7: Playwright",
 lambda: _method_playwright(...),
 AVAILABLE_TOOLS.get('playwright', False) and platform_key in [...]  # was: just platform check
),
```

---

### Step 3.6 — Verification After Phase 3

- [ ] Simulate 429: Check that 10–15s delay applied and message shown
- [ ] Simulate 401 with bad cookie file: Check remaining cookie methods are skipped
- [ ] Kill Selenium mid-run: Check timeout fires at 120s and next method runs
- [ ] Remove Selenium from venv: Check "Selenium not installed" shown at startup and all Method 8/A entries removed from list

---

## PHASE 4: ORCHESTRATOR REWRITE

### Problem Summary
- `extract_links_intelligent()` is 700 lines — too large to maintain
- `all_methods` list is a hardcoded lambda list — no dynamic filtering
- Learning cache can point to deleted/filtered methods
- Facebook profile URL detection is over-broad
- Proxy retry is blind (no connectivity test)

---

### Step 4.1 — Split Orchestrator into Sub-Functions

Break `extract_links_intelligent()` into 5 smaller functions:

```
extract_links_intelligent()        ← thin coordinator (< 80 lines)
  │
  ├── _resolve_cookies()           ← all cookie logic (Phase 2 code)
  │     Returns: cookie_file, cookie_source_description
  │
  ├── _build_method_list()         ← dynamic method list builder
  │     Input: platform_key, options, available_tools, cookie_file
  │     Returns: [(name, func), ...]  ordered list
  │
  ├── _run_methods_loop()          ← the execution + dedup loop
  │     Input: methods, entries, max_videos, exhaustive_mode, progress_cb
  │     Returns: entries, successful_method
  │
  ├── _run_proxy_retry()           ← proxy fallback logic
  │     Input: platform_key, url, cookie_file, active_proxy, progress_cb
  │     Returns: entries
  │
  └── _run_workflow_fallbacks()    ← Workflow 2 (auto-login) + Workflow 3 (manual)
        Input: platform_key, url, cookies_dir, options, progress_cb
        Returns: entries
```

**Result:** Main function becomes a clean coordinator:
```python
def extract_links_intelligent(url, platform_key, cookies_dir, options, progress_callback):
    cookie_file, source = _resolve_cookies(...)
    methods = _build_method_list(...)
    entries, method_used = _run_methods_loop(...)
    if not entries:
        entries = _run_proxy_retry(...)
    if not entries:
        entries = _run_workflow_fallbacks(...)
    return _finalize_results(entries, method_used)
```

---

### Step 4.2 — Dynamic Method List Builder

Replace the hardcoded `all_methods = [...]` lambda list with `_build_method_list()`:

```python
# Logic outline for _build_method_list(platform_key, options, avail_tools, cookie_file):
#
# Step 1: Build base list from PLATFORM_METHOD_MAP:
PLATFORM_METHOD_MAP = {
    'instagram': [
        'instagram_mobile_api',   # fastest — needs sessionid
        'selenium_cdp_attach',    # needs running Chrome on :9222
        'selenium_profile',       # needs Chrome profile
        'selenium_headless',      # universal fallback
        'playwright',             # stealth browser
        'instagram_graphql',      # needs full cookie set
        'instaloader',            # opt-in only
    ],
    'tiktok': [
        'ytdlp_primary',          # fast when cookies valid
        'ytdlp_dump_json',
        'ytdlp_get_url',
        'selenium_cdp_attach',
        'selenium_headless',
        'playwright',
        'gallery_dl',
    ],
    'facebook': [
        'facebook_json',          # fastest — needs c_user+xs
        'selenium_cdp_attach',
        'selenium_profile',
        'selenium_headless',
        'playwright',
        'ytdlp_dump_json',        # last resort
        'ytdlp_get_url',
    ],
    'youtube': [
        'ytdlp_primary',
        'ytdlp_dump_json',
        'ytdlp_get_url',
        'ytdlp_with_retry',
        'selenium_cdp_attach',
        'selenium_headless',
        'playwright',
    ],
}
#
# Step 2: Filter by availability (AVAILABLE_TOOLS dict from Phase 3)
# Step 3: Filter by cookie validity (Phase 2 validation results)
# Step 4: Apply learning system reordering (promote cached best method)
# Step 5: Return filtered, ordered list of (name, lambda) pairs
```

**Benefits:**
- Adding a new platform = add one entry to `PLATFORM_METHOD_MAP`
- Filtering logic is clean and testable in isolation
- No more 15+ lambdas in one giant list

---

### Step 4.3 — Learning System Cache Validation

**Current problem:** Cache can store a method name that was deleted/renamed.

**Fix in `_build_method_list()`:**

```python
# After getting best_method_name from learning system:
available_names = {name for name, _ in method_list}

if best_method_name and best_method_name not in available_names:
    progress_callback(f"⚠ Cached best method '{best_method_name}' is no longer available — ignoring cache")
    best_method_name = None
    # Optionally: clear the stale cache entry
    if learning_system:
        learning_system.clear_method(creator, platform_key)
```

---

### Step 4.4 — Facebook URL Detection Fix

**Current problem** (`fb_profile_shape` at ~line 4139):
A URL like `https://www.facebook.com/pagename/reels` contains `/reels` in `fb_parts`
but the check sees `fb_parts = ['pagename', 'reels']` where `'pagename'` is not in
`is_direct_video_url` check, so `fb_profile_shape=True` triggers Selenium-only path.

**Fix — stricter URL classification:**

```python
# Logic outline for _classify_facebook_url(url):
# Returns: 'direct_video' | 'reels_tab' | 'profile' | 'unknown'
#
# 'direct_video': URL contains /reel/{id}/, /videos/{id}/, /watch/?v=, /share/v/
# 'reels_tab':    URL ends with /reels or /reels/ (tab, not single reel)
# 'profile':      URL is /username or /profile.php?id=
# 'unknown':      anything else
#
# Method selection:
#   'direct_video' → yt-dlp methods first (they handle single video URLs)
#   'reels_tab'    → Facebook JSON + CDP + Selenium
#   'profile'      → Selenium-only (profile pages are behind auth wall)
```

---

### Step 4.5 — Intelligent Proxy Retry

**Current problem:** If all methods fail + proxy exists → blindly retry without proxy.
May waste 5 minutes if real issue is stale cookies, not the proxy.

**Fix — add proxy connectivity test before retry decision:**

```python
# Logic outline for _test_proxy_connectivity(proxy_url, platform_key):
# 1. Quick HEAD request to platform homepage through proxy (timeout: 5s)
# 2. If status 200: proxy works → problem is auth/cookies
# 3. If timeout/connection error: proxy is dead → retry without proxy makes sense
# 4. If 403: proxy is blocked on this platform → retry without proxy makes sense
#
# Returns: 'ok' | 'dead' | 'blocked'
#
# In _run_proxy_retry():
# proxy_status = _test_proxy_connectivity(active_proxy, platform_key)
# if proxy_status == 'ok':
#     progress_callback("Proxy is working — problem is auth/cookies, not proxy")
#     progress_callback("Skipping proxy retry. Try refreshing cookies instead.")
#     return []   # Don't waste time retrying without proxy
# else:
#     progress_callback(f"Proxy {proxy_status} — retrying without proxy")
#     # run no-proxy methods
```

---

### Step 4.6 — YouTube Tab Fallback

**Current problem:** If `/videos` returns 0, never tries `/shorts` or `/streams`.

**Add `_youtube_tab_retry()` in `_run_methods_loop()` or as separate pass:**

```python
# Logic outline:
# If platform == 'youtube' AND url was auto-normalized (had /videos appended)
# AND results == 0:
#
# For alt_tab in ['/shorts', '/streams', '']:
#     alt_url = original_url.rstrip('/') + alt_tab
#     progress_callback(f"YouTube: trying tab {alt_tab or 'default'}")
#     entries = _method_ytdlp_dump_json(alt_url, ...)
#     if entries: break
```

---

### Step 4.7 — Verification After Phase 4

- [ ] Verify `extract_links_intelligent()` is < 100 lines after split
- [ ] Verify each sub-function works independently (call with test params)
- [ ] Test Facebook reels tab URL → should NOT trigger Selenium-only path
- [ ] Test dead proxy → proxy connectivity test returns 'dead' → no-proxy retry runs
- [ ] Test working proxy + bad cookies → proxy test returns 'ok' → no-proxy retry SKIPPED
- [ ] Test YouTube channel → `/videos` fails → `/shorts` tried automatically
- [ ] Test stale learning cache → warning shown, cache entry cleared

---

## PHASE 5: TESTING STRATEGY

### After Each Phase — Quick Smoke Tests

```
Test URLs (use these consistently across all phases):
  YouTube:   https://www.youtube.com/@MrBeast/videos
  Instagram: https://www.instagram.com/natgeo/
  TikTok:    https://www.tiktok.com/@khaby.lame
  Facebook:  https://www.facebook.com/NASA/reels
```

---

### Phase 1 Tests (After Cleanup)

| Test | Expected Result |
|------|----------------|
| Count methods in `all_methods` list | Must be ≤ 13 entries |
| `grep "_method_old_" core.py` | Must return 0 matches |
| YouTube extraction | Returns links (yt-dlp methods still work) |
| Instagram extraction | Returns links (Mobile API / CDP / Selenium) |
| Check log output for Instagram | Must NOT show "Trying OLD Method 9/10" |

---

### Phase 2 Tests (After Cookie Fix)

| Test | Expected Result |
|------|----------------|
| Fresh cookie file (< 14 days) | No warnings; extraction proceeds |
| Old cookie file (> 30 days) | "Cookies too stale" shown; browser method used |
| Empty cookie file | "Cookie file invalid" shown; extraction STOPS |
| TikTok without `sessionid` | "Missing token" shown; yt-dlp skipped |
| Chrome running on port 9222 | CDP extraction runs; cookies fetched automatically |
| Crash during extraction | No `.tmp` files remain in temp folder |

---

### Phase 3 Tests (After Error Handling)

| Test | Expected Result |
|------|----------------|
| 429 response | 10–15s delay before next method; "[RATE_LIMIT] Waiting..." shown |
| Bad cookie file → 401 | Cookie methods skipped; browser methods used |
| Method hangs > 120s | Timeout fires; "timed out after 120s" shown; next method runs |
| Selenium not installed | "Selenium not available" at startup; no Method 8/A in list |

---

### Phase 4 Tests (After Orchestrator Rewrite)

| Test | Expected Result |
|------|----------------|
| `extract_links_intelligent` line count | Must be < 100 lines |
| Facebook reels tab URL | Goes through JSON/CDP path, NOT Selenium-only |
| Facebook profile URL | Goes through Selenium-only path |
| Working proxy + bad cookies | Proxy retry SKIPPED (proxy_status='ok') |
| Dead proxy | Proxy retry RUNS with no-proxy methods |
| YouTube `/videos` → 0 results | Auto-retries `/shorts` then `/streams` |
| Stale learning cache | Warning + cache cleared; default order used |

---

### Full Integration Test (After All Phases)

Run end-to-end extraction for all 4 platforms:

```
Platform    | URL Type      | With Cookies | Expected
------------|---------------|--------------|------------------
YouTube     | Channel       | Optional     | Links returned, dates present
Instagram   | Profile       | Yes          | Mobile API or Selenium
TikTok      | Profile       | Yes          | yt-dlp or Selenium
Facebook    | /reels tab    | Yes          | JSON method or CDP
Instagram   | No cookies    | No           | Workflow 2/3 attempted
```

---

## IMPLEMENTATION ORDER

```
Phase 1 (1–2 hours)  → Safest, biggest immediate impact
Phase 3, Step 3.1    → Error classifier needed by all later steps
Phase 3, Step 3.4    → Per-method timeout (prevents hangs during testing)
Phase 2 (2–3 hours)  → Cookie system (depends on Phase 3 classifier)
Phase 3 remainder    → Now that cookie system is clean
Phase 4 (3–4 hours)  → Orchestrator rewrite (biggest structural change)
Phase 5              → Runs in parallel with each phase
```

---

## CONFIG CHANGES SUMMARY

All changes to `config.py`:

```python
# Add to RETRY_CONFIG:
'per_method_timeout': 120,

# New section:
COOKIE_CONFIG = {
    'warn_age_days': 14,
    'skip_cookie_methods_age': 30,
    'expired_pct_threshold': 50,
}

# Add to DELAY_CONFIG:
'error_backoff': {
    'rate_limit':  (10.0, 15.0),
    'auth_failed': (0.5,   1.0),
    'not_found':   (0.5,   1.0),
    'network':     (5.0,  10.0),
    'unknown':     (2.0,   4.0),
}
```

---

## RISK ASSESSMENT

| Phase | Risk | Mitigation |
|-------|------|-----------|
| Phase 1 (Delete methods) | Breaking existing working paths | Verify `all_methods` has no references to deleted functions before deleting code |
| Phase 2 (Cookie validation) | Blocking valid extractions | Level 2 uses browser methods (still works); only Level 3 fully blocks |
| Phase 3 (Timeout) | ThreadPoolExecutor overhead | Small overhead; 120s timeout only applies to slow methods |
| Phase 4 (Orchestrator split) | Regression in fallback chain | Test all 5 URL types before and after |
