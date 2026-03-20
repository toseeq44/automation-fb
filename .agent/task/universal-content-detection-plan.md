# Plan: Universal Content Detection & Date Sorting System
**Date:** 2026-02-23
**Status:** In Progress — Step 2.3 complete
**Depends on:** Phase 1 cleanup (complete)

---

## Problem Statement

Current system blindly appends `/videos` to YouTube channel URLs — no tab exists check, no fallback.
Same problem across all platforms: profile URLs are passed directly to extractors that fail silently
when the profile page structure doesn't match expectations.

---

## Component 1: `detect_platform_url_type(url, platform_key)`

### Purpose
Fast classification of what kind of URL was given — before any extraction attempt.

### Signature
```python
def detect_platform_url_type(url: str, platform_key: str) -> str:
    """
    Classify the URL type for a given platform.
    Returns one of: 'profile' | 'video' | 'playlist' | 'tab' | 'unknown'
    Pure regex/URL parsing — no HTTP requests.
    """
```

### Logic per platform

**YouTube**
```
Pattern                               Type
/watch?v=...                          'video'
/shorts/{id}                          'video'
/playlist?list=...                    'playlist'
/@username/videos                     'tab'
/@username/shorts                     'tab'
/@username/streams                    'tab'
/@username/playlists                  'tab'
/@username/community                  'tab'
/@username  (bare, no extra path)     'profile'
/channel/{id}  (bare)                 'profile'
/c/{name}  (bare)                     'profile'
/user/{name}  (bare)                  'profile'
```

**Instagram**
```
/p/{shortcode}                        'video'
/reel/{shortcode}                     'video'
/tv/{shortcode}                       'video'
/{username}/reels                     'tab'
/{username}/tagged                    'tab'
/{username}/igtv                      'tab'
/{username}  (bare)                   'profile'
```

**TikTok**
```
/@{username}/video/{id}               'video'
/@{username}  (bare, no /video/)      'profile'
/tag/{name}                           'unknown'  (hashtag page — not supported)
```

**Facebook**
```
/reel/{id}                            'video'
/watch/?v={id}                        'video'
/share/v/{id}                         'video'
/{username}/videos/{id}               'video'
/{username}/videos  (no id)           'tab'
/{username}/reels                     'tab'
/profile.php?id=...                   'profile'
/people/{name}/{id}                   'profile'
/{username}  (bare, no sub-path)      'profile'
```

**Twitter/X**
```
/status/{id}                          'video'
/{username}/media                     'tab'
/{username}/with_replies              'tab'
/{username}/likes                     'tab'
/{username}  (bare)                   'profile'
```

### Implementation notes
- Pure `urlparse` + `re.search` — no network calls, runs in < 1ms
- Called at the very top of `extract_links_intelligent()`, before any cookie or proxy logic
- Result stored in `url_type` variable, used by URL normalizer (Component 2)

---

## Component 2: `detect_available_tabs(profile_url, platform_key, cookie_file, proxy)`

### Purpose
For a profile URL, probe which content tabs actually exist — lightweight HTTP only.
Avoids launching heavy Selenium just to discover that `/videos` returns 0 results.

### Signature
```python
def detect_available_tabs(
    profile_url: str,
    platform_key: str,
    cookie_file: str = None,
    proxy: str = None,
    timeout: int = 8,
) -> typing.List[str]:
    """
    Returns ordered list of tabs that exist for this profile.
    Uses lightweight HEAD/GET requests — no browser automation.
    Returns empty list on any error (caller falls back to defaults).
    """
```

### Per-platform strategy

**YouTube** — yt-dlp JSON probe (fastest, most reliable)
```
Logic:
  Run: yt-dlp --dump-single-json --flat-playlist {profile_url}
  Parse 'tabs' field from the returned JSON — YouTube includes all available tabs.
  Extract tab names from tabs[].tab_renderer.title.runs[].text
  Normalize to lowercase: 'Videos', 'Shorts', 'Live' -> 'videos', 'shorts', 'live'

Fallback if yt-dlp unavailable:
  GET {profile_url} with Referer + Accept headers
  Parse HTML: look for tab anchor links matching /{username}/videos, /shorts, /streams
  regex: r'href="/@[^/]+/(videos|shorts|streams|playlists|community|live)"'

Returns example: ['videos', 'shorts', 'streams']
Timeout: 8s total
```

**Instagram** — lightweight HTML probe
```
Logic:
  GET https://www.instagram.com/{username}/ with cookie_file loaded into session
  Check HTTP status:
    401/403 -> return [] (no cookies or private account)
    404     -> return [] (account doesn't exist)
    200     -> parse HTML
  Look for tab indicators in page HTML:
    Reels tab:  look for "reels_tab" in JSON blobs or tab nav links
    IGTV tab:   look for "igtv" in JSON blobs
    Tagged tab: look for "tagged" in JSON blobs
  Fallback: return ['posts', 'reels']  (always present for public accounts)

Returns example: ['posts', 'reels', 'igtv', 'tagged']
Timeout: 8s
```

**TikTok**
```
Logic:
  TikTok profile pages always show videos — no tab concept.
  Return fixed list: ['videos']
  (No HTTP call needed.)
```

**Facebook**
```
Logic:
  GET {profile_url}/videos with cookies
  Check if response is login-redirected (url contains 'login' -> not logged in)
  Check if response has video content vs "no videos" indicator
  Probe {profile_url}/reels similarly

Returns example: ['videos', 'reels']
Timeout: 8s per probe (2 probes max = 16s max)
```

**Twitter/X**
```
Logic:
  Twitter aggressively blocks bot traffic — no lightweight probe possible.
  Return fixed defaults: ['tweets', 'media']
```

### Caching
Results are cached in-memory for the current run (not persisted):
```python
_tab_detection_cache: typing.Dict[str, typing.List[str]] = {}
# Key: f"{platform_key}:{profile_url}"
# Valid for the duration of one extraction session only
```

### Error handling
- Any exception or timeout → return `[]`
- Caller (`_normalize_source_url_intelligent`) always has hardcoded defaults to fall back to
- Never raises — always returns a list

---

## Component 3: `_normalize_source_url_intelligent(url, platform_key, options, cookie_file, proxy, learning_system, creator)`

### Purpose
Replaces current `_normalize_source_url()`. Smarter: detects URL type first, probes tabs for profiles,
uses learning cache if available, stores chosen tab back into `options`.

### Signature
```python
def _normalize_source_url_intelligent(
    url: str,
    platform_key: str,
    options: dict,
    cookie_file: str = None,
    proxy: str = None,
    learning_system = None,
    creator: str = None,
    progress_callback = None,
) -> typing.Tuple[str, str]:
    """
    Returns: (normalized_url, chosen_tab)
    chosen_tab is the tab suffix used (e.g. 'videos', 'shorts', '') — empty string = bare profile.
    """
```

### Logic flow

```
Step 1: Classify URL type
  url_type = detect_platform_url_type(url, platform_key)

Step 2: If url_type != 'profile' → return url unchanged, chosen_tab = ''
  (video, playlist, tab URLs are already fully specified — don't touch them)

Step 3: Profile URL — find best tab
  a) Check learning cache first:
       cached_tab = learning_system.get_best_tab(creator, platform_key)
       if cached_tab is not None: use it (skip probe)

  b) Probe available tabs:
       available = detect_available_tabs(url, platform_key, cookie_file, proxy)
       if available is empty: use platform defaults (see table below)

  c) Select tab by priority:
       use PLATFORM_TAB_PRIORITY table to pick best from available

  d) Build final URL:
       if chosen_tab: final_url = f"{base_profile_url}/{chosen_tab}"
       else:          final_url = base_profile_url  (bare profile)

Step 4: Store in options for reference:
  options['_chosen_tab'] = chosen_tab
  options['_available_tabs'] = available

Step 5: Log to progress_callback:
  "Profile detected. Available tabs: [videos, shorts]. Using: videos"
```

### Platform Tab Priority Table
```python
PLATFORM_TAB_PRIORITY = {
    'youtube':   ['videos', 'shorts', 'streams', 'live', 'playlists'],
    'instagram': ['reels', 'posts', 'igtv', 'tagged'],
    'facebook':  ['videos', 'reels'],
    'tiktok':    ['videos'],
    'twitter':   ['media', 'tweets'],
}
```

### Tab Fallback Strategy (for extraction loop, not here)
The chosen tab is the *starting point*. If extraction returns 0 results,
the orchestrator will try the next tabs from `options['_available_tabs']`.
This logic lives in **Component 3b** (tab retry loop in orchestrator).

---

## Component 3b: Tab Retry Loop (in orchestrator)

### Where
After the main method loop in `extract_links_intelligent()`, before the proxy retry block.

### Logic
```python
# After main method loop:
if not entries and url_type == 'profile':
    available_tabs = options.get('_available_tabs', [])
    tried_tab = options.get('_chosen_tab', '')

    remaining_tabs = [t for t in available_tabs if t != tried_tab]
    # Only try fast methods for tab fallback (no Selenium — too slow)
    fast_methods = ['ytdlp_primary', 'ytdlp_dump_json', 'ytdlp_get_url']

    for alt_tab in remaining_tabs:
        alt_url = f"{base_profile_url}/{alt_tab}"
        if progress_callback:
            progress_callback(f"Tab '{tried_tab}' returned 0 — trying '{alt_tab}'")

        for method_name, method_func in _build_fast_methods(alt_url, ...):
            method_entries = method_func()
            if method_entries:
                entries = method_entries
                # Update learning cache with successful tab
                if learning_system:
                    learning_system.record_best_tab(creator, platform_key, alt_tab)
                break

        if entries:
            break
```

### Key constraint
Tab retry only uses fast (non-browser) methods to avoid 5-minute Selenium runs
for each tab variant. Browser methods are reserved for the full proxy-retry and
workflow fallback stages.

---

## Component 4: Universal Date Sorting

### Problem
Current state:
- `_method_ytdlp_dump_json` → date from JSON `upload_date` field (YYYYMMDD) ✓
- `_method_ytdlp_get_url` → date = `'00000000'` always ✗
- `_method_selenium` → date = `'00000000'` always ✗
- `_method_instagram_mobile_api` → date from `taken_at` Unix timestamp ✓
- `_method_facebook_json` → date = `'00000000'` ✗
- `_method_instagram_graphql` → date from `taken_at_timestamp` ✓

### Part A: `_normalize_date(raw_date)` helper

```python
def _normalize_date(raw_date) -> str:
    """
    Convert any date representation to YYYYMMDD string.
    Returns '00000000' if conversion fails.

    Accepts:
      - int/float  → Unix timestamp (e.g. 1706745600)
      - str '20240201'       → YYYYMMDD (pass-through)
      - str '2024-02-01'     → ISO date
      - str '2024-02-01T...' → ISO datetime
      - str '00000000'       → sentinel (pass-through)
      - None / ''            → '00000000'
    """
```

Logic:
```
if isinstance(raw_date, (int, float)) and raw_date > 0:
    return datetime.utcfromtimestamp(raw_date).strftime('%Y%m%d')

if isinstance(raw_date, str):
    s = raw_date.strip()
    if len(s) == 8 and s.isdigit():
        return s   # already YYYYMMDD
    if re.match(r'^\d{4}-\d{2}-\d{2}', s):
        return s[:10].replace('-', '')   # ISO -> YYYYMMDD
    if s == '00000000' or not s:
        return '00000000'

return '00000000'
```

### Part B: `_sort_entries(entries)` — canonical sort function

```python
def _sort_entries(entries: typing.List[dict]) -> typing.List[dict]:
    """
    Sort entries newest-first by date.
    Entries with date='00000000' are placed at the END, preserving
    their relative order (stable sort).
    """
    # Separate dated vs undated
    dated   = [e for e in entries if e.get('date', '00000000') != '00000000']
    undated = [e for e in entries if e.get('date', '00000000') == '00000000']

    dated.sort(key=lambda e: e.get('date', '00000000'), reverse=True)
    return dated + undated
```

### Part C: Update `_parse_upload_date()` — display formatting only

Current `_parse_upload_date()` is used only for display (in `_save_links_to_file`).
Extend it to accept the same formats as `_normalize_date()`:
```python
def _parse_upload_date(date_str: str) -> str:
    """Format YYYYMMDD -> YYYY-MM-DD for display. Also handles ISO strings."""
    normalized = _normalize_date(date_str)
    if normalized == '00000000':
        return 'Unknown'
    return f"{normalized[:4]}-{normalized[4:6]}-{normalized[6:8]}"
```

### Part D: Enforce date normalization at entry creation

Every method that builds entries already has:
```python
entries.append({'url': ..., 'title': ..., 'date': ...})
```

Add a pass-through `_make_entry(url, title='', date=None)` factory:
```python
def _make_entry(url: str, title: str = '', date=None) -> dict:
    return {
        'url': url.strip(),
        'title': (title or '')[:100],
        'date': _normalize_date(date),
    }
```

Methods updated to use `_make_entry`:
- `_method_ytdlp_get_url()` — currently sets `date='00000000'`, will remain so (no date available from `--get-url`)
- `_method_facebook_json()` — same
- `_method_selenium()` / `_method_playwright()` — same (no dates from browser scroll)
- `_method_instagram_mobile_api()` — passes `taken_at` Unix timestamp to `_make_entry` → auto-converted
- `_method_instagram_graphql()` — passes `taken_at_timestamp` → auto-converted

### Part E: Final sort in orchestrator

In `extract_links_intelligent()`, the final `_remove_duplicate_entries()` call becomes:
```python
entries = _remove_duplicate_entries(entries)
entries = _sort_entries(entries)           # NEW: universal date sort
if max_videos > 0:
    entries = entries[:max_videos]
```

---

## Component 5: Learning System Extension

### Current cache schema (per creator key)
```json
{
  "youtube:mrbeast": {
    "best_method": "Method 1: yt-dlp --dump-json",
    "performance_history": { ... }
  }
}
```

### New fields to add
```json
{
  "youtube:mrbeast": {
    "best_method": "Method 1: yt-dlp --dump-json",
    "best_tab": "videos",
    "available_tabs": ["videos", "shorts", "streams"],
    "tabs_last_checked": "2026-02-23T10:00:00",
    "performance_history": { ... }
  }
}
```

### New methods on `MethodLearningSystem`

```python
def get_best_tab(self, creator: str, platform: str) -> typing.Optional[str]:
    """
    Return the last known best tab for this creator.
    Returns None if no tab data yet.
    """
    creator_key = self._make_creator_key(creator, platform)
    entry = self.cache.get(creator_key, {})
    return entry.get('best_tab')   # e.g. 'shorts', 'videos', or None

def record_best_tab(self, creator: str, platform: str, tab: str,
                    available_tabs: typing.List[str] = None):
    """
    Store the tab that successfully returned results.
    Also stores the full list of available tabs if provided.
    """
    creator_key = self._make_creator_key(creator, platform)
    if creator_key not in self.cache:
        self.cache[creator_key] = {
            'creator': creator,
            'platform': platform,
            'best_method': None,
            'total_extractions': 0,
            'first_seen': datetime.now().isoformat(),
            'last_extraction': None,
            'performance_history': {}
        }
    self.cache[creator_key]['best_tab'] = tab
    self.cache[creator_key]['tabs_last_checked'] = datetime.now().isoformat()
    if available_tabs:
        self.cache[creator_key]['available_tabs'] = available_tabs
    self.save_cache()
```

### Cache invalidation
Tab data goes stale (creator may add a Shorts tab later).
Add `tabs_max_age_days = 14` — if `tabs_last_checked` is older than 14 days,
`get_best_tab()` returns None (forces re-probe).

```python
def get_best_tab(self, creator: str, platform: str) -> typing.Optional[str]:
    creator_key = self._make_creator_key(creator, platform)
    entry = self.cache.get(creator_key, {})

    last_checked = entry.get('tabs_last_checked')
    if last_checked:
        age = (datetime.now() - datetime.fromisoformat(last_checked)).days
        if age > 14:
            return None   # Stale — re-probe

    return entry.get('best_tab')
```

---

## Integration into Orchestrator

### Current flow (simplified)
```
1. Normalize URL  (_normalize_source_url)
2. Resolve cookies
3. Hard-code /videos for YouTube
4. Run all_methods loop
5. Remove duplicates
6. Sort by date
7. Return
```

### New flow (with all 5 components)
```
1. detect_platform_url_type(url)            ← Component 1
2. _normalize_source_url_intelligent(...)   ← Component 3
   - probes available tabs                  ← Component 2
   - picks best tab from learning cache or probe
   - stores _chosen_tab, _available_tabs in options
3. Resolve cookies
4. Run all_methods loop
5. If 0 results AND url_type=='profile':
   - Tab fallback retry (Components 3b)
6. Remove duplicates
7. _sort_entries()                          ← Component 4B
8. If tab retry succeeded: record_best_tab  ← Component 5
9. Return
```

### Changes to `extract_links_intelligent()` signature
No signature change. Options dict gains two new internal keys (`_chosen_tab`, `_available_tabs`)
that are set by the normalizer and read by the tab retry logic. These are internal and not
exposed to the GUI.

---

## File Impact Summary

| File | Change |
|------|--------|
| `core.py` | Add Components 1, 2, 3, 3b, 4A-E as new helper functions. Replace `_normalize_source_url` call in orchestrator with `_normalize_source_url_intelligent`. Remove YouTube-specific `/videos` hard-code block (~lines 3540-3550). |
| `intelligence.py` | Add `get_best_tab()`, `record_best_tab()` methods + new cache fields |
| `config.py` | Add `PLATFORM_TAB_PRIORITY` dict and `tabs_max_age_days = 14` |

**New functions to add to `core.py` (~120 lines total):**
- `detect_platform_url_type()` — ~40 lines
- `detect_available_tabs()` — ~60 lines
- `_normalize_source_url_intelligent()` — ~50 lines
- `_normalize_date()` — ~20 lines
- `_sort_entries()` — ~10 lines
- `_make_entry()` — ~8 lines
- Tab retry block in orchestrator — ~25 lines

**Modified in `core.py`:**
- `_parse_upload_date()` — 5 lines changed
- All `entries.append({...})` calls → `_make_entry(...)` factory (across ~10 methods)

---

## Constraints

1. `detect_available_tabs()` must complete in < 10s total per platform. If timeout → return `[]` and fall back to defaults.
2. Tab probe is **skipped entirely** if `url_type != 'profile'` — never probe video or playlist URLs.
3. Tab probe is **skipped** if `learning_system.get_best_tab()` returns a non-stale cached value.
4. `_make_entry()` factory is additive — methods that already provide dates correctly continue to work unchanged.
5. The `_sort_entries()` function must use a **stable sort** so that undated entries preserve their extraction order relative to each other.
