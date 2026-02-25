# OneSoul Database Schema

## 1) Scope
This repository has two data layers:

1. Relational database schema used by the license server (`server/`).
2. File-based schemas (JSON/JSONL) used by the desktop app (`modules/`, `config/`, `data_files/`).

The only true SQL schema is in `server/models.py`.

## 2) Relational Schema (License Server)
Source: `server/models.py` and `server/app.py`

Default DB URI:
- `sqlite:///licenses.db` (configurable via `DATABASE_URL`)

### 2.1 Table: `licenses`
Purpose: master license record and device binding state.

Columns:
- `id` INTEGER PK
- `license_key` VARCHAR(100), UNIQUE, NOT NULL, indexed
- `email` VARCHAR(255), NOT NULL
- `plan_type` VARCHAR(20), NOT NULL
- `purchase_date` DATETIME, NOT NULL, default `datetime.utcnow`
- `expiry_date` DATETIME, NOT NULL
- `hardware_id` VARCHAR(255), nullable
- `device_name` VARCHAR(255), nullable
- `is_active` BOOLEAN, NOT NULL, default `True`
- `is_suspended` BOOLEAN, NOT NULL, default `False`
- `activation_count` INTEGER, NOT NULL, default `0`
- `last_validation` DATETIME, nullable
- `created_at` DATETIME, NOT NULL, default `datetime.utcnow`
- `updated_at` DATETIME, NOT NULL, default `datetime.utcnow`, auto-updated

Relationships:
- One-to-many with `validation_logs` via `license_key`
- One-to-many with `security_alerts` via `license_key`

### 2.2 Table: `validation_logs`
Purpose: audit log of license operations.

Columns:
- `id` INTEGER PK
- `license_key` VARCHAR(100), FK -> `licenses.license_key`, indexed, NOT NULL
- `hardware_id` VARCHAR(255), nullable
- `ip_address` VARCHAR(50), nullable
- `action` VARCHAR(20), NOT NULL
- `status` VARCHAR(20), NOT NULL
- `message` TEXT, nullable
- `timestamp` DATETIME, NOT NULL, default `datetime.utcnow`, indexed

### 2.3 Table: `security_alerts`
Purpose: records suspicious/high-risk events.

Columns:
- `id` INTEGER PK
- `license_key` VARCHAR(100), FK -> `licenses.license_key`, indexed, NOT NULL
- `alert_type` VARCHAR(50), NOT NULL
- `description` TEXT, NOT NULL
- `severity` VARCHAR(20), NOT NULL
- `is_resolved` BOOLEAN, NOT NULL, default `False`
- `created_at` DATETIME, NOT NULL, default `datetime.utcnow`, indexed

## 3) Entity Relationship Summary
- `licenses (1) -> (many) validation_logs`
- `licenses (1) -> (many) security_alerts`

Join key is `license_key` (string token), not numeric `id`.

## 4) API-to-DB Usage Mapping
Routes in `server/routes.py` manipulate schema as follows:
- `/api/license/activate`: reads/writes `licenses`, inserts `validation_logs`, may insert `security_alerts`
- `/api/license/validate`: reads/writes `licenses`, inserts `validation_logs`, may insert `security_alerts`
- `/api/license/deactivate`: writes `licenses`, inserts `validation_logs`, may insert `security_alerts`
- `/api/admin/generate`: inserts `licenses` records

## 5) Desktop File-Based Data Schemas
The desktop app does not use a relational DB for core workflows. It stores state in JSON/JSONL.

### 5.1 `config/config.json`
Managed by: `modules/config/config_manager.py`

Top-level sections:
- `app`
- `license`
- `paths`
- `rate_limiting`
- `downloader`
- `editor`
- `logging`
- `link_grabber`
- `folder_mapping`

### 5.2 `config/proxy_settings.json`
Managed by: `modules/shared/auth_network_hub.py`

Fields:
- `proxy1` string
- `proxy2` string
- `last_updated` string datetime

### 5.3 `config/auth_state.json`
Managed by: `modules/shared/auth_network_hub.py`

Observed structure includes:
- `cookies.master_file`
- `cookies.cookie_count`
- `cookies.platforms[]`
- `updated_at`

### 5.4 Per-creator config: `creator_config.json`
Managed by: `modules/creator_profiles/config_manager.py`

Key fields:
- `creator_url`
- `n_videos`
- `editing_mode` (`none|preset|split`)
- `preset_name`
- `split_duration`
- `duplication_control`
- `popular_fallback`
- `prefer_popular_first`
- `randomize_links`
- `keep_original_after_edit`
- `downloaded_ids[]`
- `last_activity{ date, result, tier_used, videos_downloaded }`

### 5.5 Activity log: `data_files/creator_activity_log.jsonl`
Appends event records, one JSON object per line.

Observed event model:
- `timestamp`
- `creator_folder`
- `creator_url`
- `event`
- `payload` (event-specific object)

## 6) Notes
- SQL migrations are not present; schema is created via `db.create_all()` in `server/app.py`.
- Desktop data stores are schemaless JSON/JSONL with implicit contracts enforced in Python code.
