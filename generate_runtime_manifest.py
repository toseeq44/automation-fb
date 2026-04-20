from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_files(dist_dir: Path) -> Dict[str, str]:
    candidates = [
        "OneSoul.exe",
        "api_config.json",
        "license_endpoints.json",
        "cloudflared.exe",
        "ffmpeg/bin/ffmpeg.exe",
        "ffmpeg/bin/ffprobe.exe",
        "ffmpeg/ffmpeg.exe",
        "ffmpeg/ffprobe.exe",
    ]
    files: Dict[str, str] = {}
    for rel in candidates:
        target = dist_dir / rel
        if target.exists() and target.is_file():
            files[rel.replace("\\", "/")] = sha256_file(target)

    for pattern in ("modules/license/*.pyd", "modules/security/*.pyd"):
        for target in sorted(dist_dir.glob(pattern)):
            if target.is_file():
                rel = target.relative_to(dist_dir).as_posix()
                files[rel] = sha256_file(target)
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate runtime integrity manifest for OneSoul build output.")
    parser.add_argument("--dist-dir", default="dist/OneSoul", help="Path to built OneSoul distribution directory.")
    args = parser.parse_args()

    dist_dir = Path(args.dist_dir).resolve()
    if not dist_dir.exists():
        raise SystemExit(f"Distribution directory not found: {dist_dir}")

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "files": collect_files(dist_dir),
    }
    manifest_path = dist_dir / "onesoul_runtime_manifest.json"
    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Runtime manifest generated: {manifest_path}")
    print(f"Tracked files: {len(payload['files'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
