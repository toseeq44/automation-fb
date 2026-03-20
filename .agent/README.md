# Automation Project Documentation Index

## System Docs
- project-architecture.md
- database-schema.md

## Tasks
(Feature implementation plans stored here)

## SOPs
(Standard operating procedures stored here)

---

Before implementing any feature:
1. Read this file
2. Check related system docs
3. Check previous tasks

---

## Current Project Status
**Last Updated:** 2026-02-23

### Phase 1 (CLEANUP) - COMPLETED ✓
- Deleted 4 duplicate functions:
  - `_method_old_batch_file()`
  - `_method_old_dump_json()`
  - `_method_old_instaloader()`
  - `_method_ytdlp_user_agent()`
- Renamed 3 functions:
  - `_method_ytdlp_enhanced()` → `_method_ytdlp_primary()`
  - `_method_instagram_web_api()` → `_method_instagram_graphql()`
  - `_method_existing_browser_session()` → `_method_selenium_profile()`
- `all_methods` list cleaned, now 13 methods total
- File size reduced from 4748 to 4391 lines

### Phase 2 (Content Detection) - IN PROGRESS
**Step 2.1 Completed** - `detect_platform_url_type()` function added
- Classifies URLs into: 'profile', 'video', 'playlist', 'tab', 'unknown'
- Supports YouTube, Instagram, TikTok, Facebook, Twitter
- Tested with 38 test cases, all passed

**Step 2.2 Completed** - `detect_available_tabs()` added to `core.py` (line ~350)
- Uses yt-dlp `--dump-single-json --flat-playlist` to fetch channel metadata
- Parses `tabs[].title` field, returns lowercase list e.g. `['videos', 'shorts', 'streams']`
- 8-second subprocess timeout; returns `[]` on any error or timeout
- Supports `cookie_file` and `proxy` passthrough
- Platform guard: non-YouTube platforms return `[]` immediately

**Step 2.3 Completed** - Tab detection integrated into `extract_links_intelligent()`
- Replaced hardcoded `/videos` append with `detect_platform_url_type()` + `detect_available_tabs()` call
- Learning cache checked first (skips probe if fresh cached tab exists)
- Tab selected by `PLATFORM_TAB_PRIORITY` order; defaults to 'videos' if probe fails
- Tab fallback retry loop added (fast yt-dlp methods only, no browser) when primary tab returns 0
- Successful tab recorded into learning system via `record_best_tab()`
- `PLATFORM_TAB_PRIORITY` + `TABS_MAX_AGE_DAYS` added to `config.py`

**Step 2.5 Completed** - 3-layer bulletproof tab detection added to `core.py`
- `is_chrome_running_with_debug()` (line ~448) — TCP probe on ports 9222/9223/9224/9229, returns open port or 0
- `detect_tabs_via_cdp()` (line ~473) — Selenium CDP attach, 3-strategy DOM parse (tp-yt-paper-tab → yt-tab-group-shape → href slugs)
- `detect_available_tabs_bulletproof()` (line ~592) — L1: yt-dlp, L2: HTTP HEAD probe, L3: CDP DOM; falls back to [] on all failures
- Orchestrator now calls `detect_available_tabs_bulletproof()` instead of bare `detect_available_tabs()`

**Next Step:** Step 2.4 - Add `get_best_tab()` / `record_best_tab()` to `intelligence.py`

### Files to reference:
- `modules/link_grabber/core.py` (main file)
- `modules/link_grabber/config.py` (config)
- `modules/link_grabber/intelligence.py` (learning system)

### Key decisions:
- Universal content detection system for all platforms
- Date sorting to be implemented after tab detection
- Learning system to remember best tabs per creator