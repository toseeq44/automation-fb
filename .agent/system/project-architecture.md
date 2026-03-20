# OneSoul Project Architecture

## 1) System Overview
OneSoul is a desktop-first automation suite built on PyQt5, with a separate Flask-based license server.

- Desktop app entrypoint: `main.py`
- Primary desktop shell/UI: `gui_modern.py`
- Feature modules live under: `modules/`
- Optional server component: `server/` (license APIs + database)
- Persistent runtime data: `config/`, `cookies/`, `data_files/`

The desktop app orchestrates multiple workflows:
- Link grabbing
- Video downloading + creator profile orchestration
- Video editing
- Metadata removal
- Auto uploader
- API config/title-generation related tooling

## 2) Runtime Boot Flow (Desktop)
1. `main.py` starts `QApplication` and selects `VideoToolSuiteGUI` from `gui_modern.py`.
2. `restore_bundled_configs()` restores bundled assets/config when running as a PyInstaller executable.
3. Global config is loaded via `modules.config.get_config()` (`modules/config/config_manager.py`).
4. License validation runs through `modules.license` (`LicenseManager`, `sync_all_plans`).
5. Main window is created and module pages are mounted inside a stacked layout.

Key references:
- `main.py`
- `gui_modern.py`
- `modules/config/config_manager.py`
- `modules/license/*`

## 3) UI Composition
`gui_modern.py` defines a centralized themed shell and loads feature pages:
- `modules.link_grabber.gui.LinkGrabberPage`
- `modules.video_downloader.gui.VideoDownloaderPage`
- `modules.video_editor.integrated_editor.IntegratedVideoEditor`
- `modules.metadata_remover.gui.MetadataRemoverPage`
- `modules.auto_uploader.gui.AutoUploaderPage`
- `modules.api_manager.gui.APIConfigPage`
- `modules.creator_profiles.page.CreatorProfilesPage`

This file is the top-level integration layer for module navigation and visual consistency.

## 4) Core Module Responsibilities

### 4.1 Link Grabber
- UI: `modules/link_grabber/gui.py`
- Engine: `modules/link_grabber/core.py`
- Config helpers: `modules/link_grabber/config.py`
- Method learning/cache: `modules/link_grabber/intelligence.py`

Behavior:
- Multi-method extraction (yt-dlp, Selenium, Playwright, gallery-dl, optional Instaloader)
- Platform normalization and creator inference
- Proxy-aware extraction and fallback sequencing
- Browser session/cookie fallback paths

### 4.2 Video Downloader
- UI: `modules/video_downloader/gui.py`
- Core pipeline: `modules/video_downloader/core.py`
- Worker + manager helpers: `yt_dlp_worker.py`, `download_manager.py`, `history_manager.py`

Behavior:
- yt-dlp driven downloads with retries/proxy/cookies
- FFmpeg path resolution and media post-processing hooks
- URL normalization utilities (`url_utils.py`)

### 4.3 Creator Profiles (Downloading + Editing)
- Page/grid: `modules/creator_profiles/page.py`
- Card widget: `modules/creator_profiles/creator_card.py`
- Per-creator config model: `modules/creator_profiles/config_manager.py`
- Download/edit orchestration: `modules/creator_profiles/download_engine.py`

Behavior:
- Creator card-based control center
- Per-folder `creator_config.json` persisted settings
- Activity telemetry to JSONL log

### 4.4 Video Editor
- Entry UI: `modules/video_editor/integrated_editor.py`
- Effects, presets, timelines, merge workflows under `modules/video_editor/*`
- Uses FFmpeg and additional models/assets where needed

### 4.5 Metadata Remover
- UI/processing under `modules/metadata_remover/*`
- Handles metadata cleaning workflow and progress dialogs

### 4.6 Auto Uploader
- Complex workflow package under `modules/auto_uploader/*`
- Includes browser automation strategies (IXBrowser/NSTBrowser/free automation), session and upload orchestration

### 4.7 Shared Infrastructure
- Paths and runtime locations: `modules/config/paths.py`
- Shared auth/network state: `modules/shared/auth_network_hub.py`
- Browser extraction helpers: `modules/shared/browser_extractor.py`
- Logging: `modules/logging/logger.py`

## 5) Configuration & Storage Architecture
The desktop app primarily uses filesystem-based persistence.

Primary locations:
- `config/`:
  - `config.json` (app settings)
  - `proxy_settings.json`
  - `auth_state.json`
- `cookies/`:
  - `chrome_cookies.txt` + platform cookie files
- `data_files/`:
  - `creator_activity_log.jsonl`
- Creator folders (user workspace):
  - per-creator `creator_config.json`
  - links text files and downloaded/edited media

Path resolution is centralized in `modules/config/paths.py` and supports both dev and EXE modes.

## 6) Server-Side Architecture (License Service)
Separate Flask service under `server/`.

- App factory: `server/app.py`
- API routes: `server/routes.py`
- ORM models: `server/models.py`
- DB backend: SQLAlchemy (default SQLite `licenses.db`)

Main API domains:
- Health
- License activation/validation/deactivation/status
- Admin key generation endpoint

## 7) External Dependencies & Integration Points
- `yt-dlp`: link extraction and downloads (binary + Python API patterns)
- `FFmpeg`: editing/splitting/transcoding
- Browser automation: Selenium, Playwright (module-dependent)
- Flask + SQLAlchemy (server side)

## 8) Notable Engineering Characteristics
- Desktop app is modular but integrated through a single modern shell (`gui_modern.py`).
- Persistence is mostly JSON/JSONL + filesystem folders, not relational DB, for desktop runtime.
- License concerns are isolated in a dedicated server component with relational schema.
- Path and auth/proxy concerns are being centralized via shared helper modules.

## 9) High-Level Directory Map
- `main.py`: desktop launcher
- `gui_modern.py`: shell + page composition
- `modules/`: feature and shared packages
- `server/`: license backend
- `config/`, `cookies/`, `data_files/`: runtime state/data
- `presets/`: editor presets
- `bin/`, `ffmpeg/`: bundled tooling/assets

## 10) Current Boundaries
- Desktop application data model is file-based and distributed across module-owned JSON files.
- Only the license service currently maintains a formal relational schema.
