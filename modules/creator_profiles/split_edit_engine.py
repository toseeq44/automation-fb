"""
FFmpeg-based split-edit processing for Creator Profiles.
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Callable, Optional, Sequence

from .config_manager import merge_split_edit_settings


_DEMUCS_CACHE_UNSET = object()
_DEMUCS_COMMAND_CACHE: object = _DEMUCS_CACHE_UNSET
_DEFAULT_DEMUCS_MODEL = "htdemucs"


def _emit(progress_cb: Optional[Callable[[str], None]], message: str) -> None:
    if progress_cb:
        progress_cb(message)


def _creationflags() -> int:
    return subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def _ffprobe_path(ffmpeg_path: str) -> str:
    ffmpeg = Path(ffmpeg_path)
    probe_name = "ffprobe.exe" if ffmpeg.suffix.lower() == ".exe" else "ffprobe"
    probe_path = ffmpeg.with_name(probe_name)
    return str(probe_path if probe_path.exists() else probe_name)


def _has_audio_stream(input_path: Path, ffmpeg_path: str) -> bool:
    ffprobe = _ffprobe_path(ffmpeg_path)
    flags = _creationflags()
    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-select_streams",
                "a",
                "-show_entries",
                "stream=index",
                "-of",
                "csv=p=0",
                str(input_path),
            ],
            capture_output=True,
            text=True,
            timeout=12,
            creationflags=flags,
        )
        if bool((result.stdout or "").strip()):
            return True
    except Exception:
        pass

    try:
        result = subprocess.run(
            [ffmpeg_path, "-hide_banner", "-i", str(input_path)],
            capture_output=True,
            text=True,
            timeout=12,
            creationflags=flags,
        )
        probe_text = f"{result.stdout or ''}\n{result.stderr or ''}"
        if "Audio:" in probe_text:
            return True
        if "Video:" in probe_text:
            return False
    except Exception:
        pass

    # Preserve audio by default if probing is inconclusive.
    return True


def _build_demucs_candidates() -> list[list[str]]:
    candidates: list[list[str]] = []
    env_cmd = (
        os.environ.get("CREATOR_PROFILE_DEMUCS_CMD")
        or os.environ.get("DEMUSCS_CMD")
        or ""
    ).strip()
    if env_cmd:
        try:
            candidates.append(shlex.split(env_cmd, posix=os.name != "nt"))
        except Exception:
            candidates.append([env_cmd])

    demucs_cli = shutil.which("demucs")
    if demucs_cli:
        candidates.append([demucs_cli])

    repo_root = Path(__file__).resolve().parents[2]
    venv_python = repo_root / ".venv" / "Scripts" / "python.exe"
    if venv_python.exists():
        candidates.append([str(venv_python), "-m", "demucs"])

    scripts_dir = Path(sys.executable).resolve().parent
    demucs_exe = scripts_dir / ("demucs.exe" if os.name == "nt" else "demucs")
    if demucs_exe.exists():
        candidates.append([str(demucs_exe)])

    if sys.executable:
        candidates.append([sys.executable, "-m", "demucs"])

    py_launcher = shutil.which("py")
    if py_launcher:
        candidates.append([py_launcher, "-m", "demucs"])

    unique: list[list[str]] = []
    seen = set()
    for parts in candidates:
        key = tuple(str(p) for p in parts if str(p).strip())
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(list(key))
    return unique


def _detect_demucs_command() -> Optional[list[str]]:
    global _DEMUCS_COMMAND_CACHE
    if _DEMUCS_COMMAND_CACHE is not _DEMUCS_CACHE_UNSET:
        cached = _DEMUCS_COMMAND_CACHE
        return list(cached) if isinstance(cached, list) else None

    flags = _creationflags()
    for candidate in _build_demucs_candidates():
        try:
            result = subprocess.run(
                candidate + ["--help"],
                capture_output=True,
                text=True,
                timeout=20,
                creationflags=flags,
            )
            help_text = f"{result.stdout or ''}\n{result.stderr or ''}".lower()
            if result.returncode == 0 or "demucs" in help_text or "two-stems" in help_text:
                _DEMUCS_COMMAND_CACHE = list(candidate)
                return list(candidate)
        except Exception:
            continue

    _DEMUCS_COMMAND_CACHE = None
    return None


def _resolve_demucs_repo() -> Optional[Path]:
    candidates: list[Path] = []

    repo_root = Path(__file__).resolve().parents[2]
    candidates.append(repo_root / "demucs_models")
    candidates.append(Path.cwd() / "demucs_models")

    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        candidates.extend(
            [
                exe_dir / "_internal" / "demucs_models",
                exe_dir / "demucs_models",
            ]
        )
        meipass = getattr(sys, "_MEIPASS", "")
        if meipass:
            candidates.append(Path(meipass) / "demucs_models")

    for candidate in candidates:
        try:
            if candidate.is_dir():
                if (candidate / "htdemucs.yaml").exists() or (candidate / "mdx_q.yaml").exists():
                    return candidate
        except Exception:
            continue
    return None


def _load_demucs_model(model_name: str, repo_dir: Path):
    import torch as th
    from demucs.pretrained import get_model

    original_load = th.load

    def _compat_load(*args, **kwargs):
        kwargs.setdefault("weights_only", False)
        return original_load(*args, **kwargs)

    th.load = _compat_load
    try:
        return get_model(name=model_name, repo=repo_dir)
    finally:
        th.load = original_load


def _resolve_demucs_segment(model, requested_segment: Optional[int]) -> Optional[int]:
    if hasattr(model, "models"):
        return None
    return requested_segment


def _prefer_demucs_helper(repo_dir: Optional[Path]) -> bool:
    if not repo_dir or getattr(sys, "frozen", False):
        return False
    if os.name != "nt":
        return False
    repo_root = Path(__file__).resolve().parents[2]
    return (repo_root / ".venv" / "Scripts" / "python.exe").exists()


def _run_demucs_helper(
    input_path: Path,
    output_folder: Path,
    repo_dir: Path,
    model_name: str,
    ffmpeg_path: str,
    progress_cb: Optional[Callable[[str], None]] = None,
) -> Optional[Path]:
    repo_root = Path(__file__).resolve().parents[2]
    helper_module = "modules.creator_profiles.demucs_runner"
    helper_root = output_folder / f".split_edit_demucs_{uuid.uuid4().hex[:8]}"
    helper_output = helper_root / "vocals.wav"
    helper_output.parent.mkdir(parents=True, exist_ok=True)
    helper_input = input_path
    created_input = False

    if input_path.suffix.lower() != ".wav":
        helper_input = helper_root / "input.wav"
        if not _extract_audio_to_wav(input_path, helper_input, ffmpeg_path):
            _cleanup_temp_paths([helper_root])
            _emit(progress_cb, "  Split+Edit: Demucs helper audio prep failed.")
            return None
        created_input = True

    candidates: list[list[str]] = []
    venv_python = repo_root / ".venv" / "Scripts" / "python.exe"
    if venv_python.exists():
        candidates.append([str(venv_python), "-m", helper_module])
    if sys.executable:
        candidates.append([sys.executable, "-m", helper_module])

    flags = _creationflags()
    for candidate in candidates:
        try:
            result = subprocess.run(
                candidate + [
                    "--input",
                    str(helper_input),
                    "--output",
                    str(helper_output),
                    "--repo",
                    str(repo_dir),
                    "--model",
                    model_name,
                ],
                capture_output=True,
                text=True,
                timeout=3600,
                creationflags=flags,
                cwd=str(repo_root),
            )
            if result.returncode == 0 and helper_output.exists() and helper_output.stat().st_size > 4096:
                if created_input:
                    _cleanup_temp_paths([helper_input])
                return helper_output
            err = (result.stderr or result.stdout or "").strip()
            if err:
                _emit(progress_cb, f"  Split+Edit: Demucs helper fallback ({err[:160]})")
        except Exception as exc:
            _emit(progress_cb, f"  Split+Edit: Demucs helper exception ({str(exc)[:140]})")

    if created_input:
        _cleanup_temp_paths([helper_input])
    _cleanup_temp_paths([helper_output.parent])
    return None


def _extract_audio_to_wav(input_path: Path, output_wav: Path, ffmpeg_path: str) -> bool:
    flags = _creationflags()
    try:
        result = subprocess.run(
            [
                ffmpeg_path,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(input_path),
                "-map",
                "0:a:0",
                "-vn",
                "-ac",
                "2",
                "-ar",
                "44100",
                "-c:a",
                "pcm_s16le",
                str(output_wav),
            ],
            capture_output=True,
            text=True,
            timeout=1800,
            creationflags=flags,
        )
        return result.returncode == 0 and output_wav.exists() and output_wav.stat().st_size > 0
    except Exception:
        return False


def _find_demucs_vocals(output_root: Path) -> Optional[Path]:
    preferred = []
    preferred.extend(output_root.rglob("vocals.wav"))
    preferred.extend(output_root.rglob("*vocals*.wav"))
    preferred.extend(output_root.rglob("*voice*.wav"))

    for candidate in preferred:
        name = candidate.name.lower()
        if "no_vocals" in name or "instrument" in name:
            continue
        if candidate.is_file():
            return candidate
    return None


def _cleanup_temp_paths(paths: Sequence[Path]) -> None:
    for path in paths:
        try:
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            elif path.exists():
                path.unlink()
        except Exception:
            pass


def _separate_vocals_with_demucs(
    input_path: Path,
    output_folder: Path,
    ffmpeg: str,
    progress_cb: Optional[Callable[[str], None]] = None,
) -> Optional[Path]:
    repo_dir = _resolve_demucs_repo()
    model_name = (
        os.environ.get("CREATOR_PROFILE_DEMUCS_MODEL") or _DEFAULT_DEMUCS_MODEL
    ).strip() or _DEFAULT_DEMUCS_MODEL
    segment = (os.environ.get("CREATOR_PROFILE_DEMUCS_SEGMENT") or "8").strip() or "8"

    if _prefer_demucs_helper(repo_dir):
        _emit(progress_cb, f"  Split+Edit: isolating vocals with Demucs ({model_name})...")
        helper_vocals = _run_demucs_helper(
            input_path=input_path,
            output_folder=output_folder,
            repo_dir=repo_dir,
            model_name=model_name,
            ffmpeg_path=ffmpeg,
            progress_cb=progress_cb,
        )
        if helper_vocals:
            return helper_vocals

    try:
        import torch as th
        from demucs.apply import apply_model
        from .demucs_runner import _load_wav_audio, _save_wav_audio

        if repo_dir:
            _emit(progress_cb, f"  Split+Edit: isolating vocals with Demucs ({model_name})...")
            model = _load_demucs_model(model_name, repo_dir)
            model.cpu()
            model.eval()

            temp_root = output_folder / f".split_edit_demucs_{uuid.uuid4().hex[:8]}"
            temp_root.mkdir(parents=True, exist_ok=True)
            audio_input = temp_root / "input.wav"
            if not _extract_audio_to_wav(input_path, audio_input, ffmpeg):
                _cleanup_temp_paths([temp_root])
                raise RuntimeError("audio extraction failed for Demucs input")

            wav = _load_wav_audio(audio_input, model.audio_channels, model.samplerate)
            ref = wav.mean(0)
            wav = wav - ref.mean()
            std = ref.std()
            scale = std.item() if hasattr(std, "item") else float(std)
            if scale > 1e-8:
                wav = wav / std
            else:
                scale = 1.0

            requested_segment = None
            if segment.isdigit():
                requested_segment = int(segment)
            requested_segment = _resolve_demucs_segment(model, requested_segment)

            with th.no_grad():
                sources = apply_model(
                    model,
                    wav[None],
                    device="cpu",
                    shifts=1,
                    split=True,
                    overlap=0.25,
                    progress=False,
                    num_workers=0,
                    segment=requested_segment,
                )[0]
            sources = sources * scale
            sources = sources + ref.mean()

            vocals_index = list(model.sources).index("vocals")
            vocals_copy = temp_root / "vocals.wav"
            _save_wav_audio(sources[vocals_index].cpu(), vocals_copy, model.samplerate)
            if vocals_copy.exists() and vocals_copy.stat().st_size > 4096:
                _cleanup_temp_paths([audio_input])
                return vocals_copy
            _cleanup_temp_paths([temp_root])
            _emit(progress_cb, "  Split+Edit: Demucs vocals stem too small, using CLI fallback.")
    except Exception as exc:
        _emit(progress_cb, f"  Split+Edit: Demucs python fallback ({str(exc)[:160]})")

    if repo_dir:
        helper_vocals = _run_demucs_helper(
            input_path=input_path,
            output_folder=output_folder,
            repo_dir=repo_dir,
            model_name=model_name,
            ffmpeg_path=ffmpeg,
            progress_cb=progress_cb,
        )
        if helper_vocals:
            return helper_vocals

    demucs_cmd = _detect_demucs_command()
    if not demucs_cmd:
        _emit(progress_cb, "  Split+Edit: Demucs not available, using FFmpeg fallback.")
        return None

    temp_root = output_folder / f".split_edit_demucs_{uuid.uuid4().hex[:8]}"
    audio_input = temp_root / "input.wav"
    demucs_output = temp_root / "out"
    vocals_copy = temp_root / "vocals.wav"
    temp_root.mkdir(parents=True, exist_ok=True)

    if not _extract_audio_to_wav(input_path, audio_input, ffmpeg):
        _cleanup_temp_paths([temp_root])
        _emit(progress_cb, "  Split+Edit: audio extraction failed, using FFmpeg fallback.")
        return None

    cmd = list(demucs_cmd)
    cmd.extend(
        [
            "--two-stems=vocals",
            "-n",
            model_name,
            "-d",
            "cpu",
            "-o",
            str(demucs_output),
        ]
    )
    if repo_dir:
        cmd.extend(["--repo", str(repo_dir)])
    if segment.isdigit():
        cmd.extend(["--segment", segment])
    cmd.append(str(audio_input))

    _emit(progress_cb, f"  Split+Edit: isolating vocals with Demucs ({model_name})...")

    flags = _creationflags()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600,
            creationflags=flags,
        )
    except Exception as exc:
        _cleanup_temp_paths([temp_root])
        _emit(progress_cb, f"  Split+Edit: Demucs exception ({str(exc)[:140]})")
        return None

    vocals_path = _find_demucs_vocals(demucs_output)
    if result.returncode != 0 or not vocals_path or not vocals_path.exists():
        err = (result.stderr or result.stdout or "").strip()
        _cleanup_temp_paths([temp_root])
        if err:
            _emit(progress_cb, f"  Split+Edit: Demucs fallback ({err[:160]})")
        else:
            _emit(progress_cb, "  Split+Edit: Demucs produced no vocals stem, using FFmpeg fallback.")
        return None

    try:
        shutil.copy2(vocals_path, vocals_copy)
    except Exception as exc:
        _cleanup_temp_paths([temp_root])
        _emit(progress_cb, f"  Split+Edit: Demucs copy failed ({str(exc)[:140]})")
        return None

    if not vocals_copy.exists() or vocals_copy.stat().st_size <= 4096:
        _cleanup_temp_paths([temp_root])
        _emit(progress_cb, "  Split+Edit: Demucs vocals stem too small, using FFmpeg fallback.")
        return None

    return vocals_copy


def _build_video_filter(settings: dict) -> str:
    zoom = max(50, min(200, int(settings["zoom_percent"]))) / 100.0
    filters = []

    if abs(zoom - 1.0) > 0.001:
        filters.append(
            f"scale='trunc(iw*{zoom:.4f}/2)*2':'trunc(ih*{zoom:.4f}/2)*2'"
        )
        if zoom > 1.0:
            filters.append(
                f"crop='trunc(iw/{zoom:.4f}/2)*2':'trunc(ih/{zoom:.4f}/2)*2'"
            )
        else:
            filters.append(
                f"pad='trunc(iw/{zoom:.4f}/2)*2':'trunc(ih/{zoom:.4f}/2)*2':(ow-iw)/2:(oh-ih)/2:black"
            )

    if settings["mirror_horizontal"]:
        filters.append("hflip")

    filters.extend(["setsar=1", "format=yuv420p"])
    return ",".join(filters)


def _build_audio_filter(settings: dict, music_isolated: bool = False) -> str:
    filters = []
    remove_music = bool(settings["remove_background_music"])
    voice_enabled = bool(settings["voice_enhance_enabled"])
    clarity = str(settings["voice_clarity"]).strip().lower()

    if remove_music:
        if music_isolated:
            filters.extend(
                [
                    "afftdn=nf=-30",
                    "highpass=f=80",
                    "lowpass=f=8000",
                    "acompressor=threshold=-21dB:ratio=2.8:attack=5:release=65",
                    "volume=1.08",
                ]
            )
        else:
            filters.extend(
                [
                    "afftdn=nf=-20",
                    "highpass=f=85",
                    "lowpass=f=3200",
                    "equalizer=f=200:t=h:width=100:g=6",
                    "equalizer=f=800:t=h:width=180:g=5",
                    "equalizer=f=4200:t=h:width=2200:g=-12",
                    "acompressor=threshold=-20dB:ratio=3.5:attack=5:release=60",
                ]
            )

    if voice_enabled:
        if not remove_music:
            filters.extend(["highpass=f=90", "lowpass=f=3800"])
        elif music_isolated:
            filters.extend(["highpass=f=90", "lowpass=f=7800"])

        if clarity == "strong":
            filters.extend(
                [
                    "equalizer=f=180:t=h:width=120:g=7",
                    "equalizer=f=1000:t=h:width=220:g=6",
                    "acompressor=threshold=-18dB:ratio=4.5:attack=4:release=45",
                    "volume=1.20",
                ]
            )
        else:
            filters.extend(
                [
                    "equalizer=f=220:t=h:width=120:g=4",
                    "equalizer=f=900:t=h:width=220:g=3",
                    "acompressor=threshold=-19dB:ratio=3.0:attack=5:release=55",
                    "volume=1.10",
                ]
            )

        pitch_percent = int(settings["voice_pitch_percent"])
        if pitch_percent:
            rate = 1.0 + (pitch_percent / 100.0)
            tempo = 1.0 / rate
            filters.extend(
                [
                    f"asetrate=44100*{rate:.5f}",
                    "aresample=44100",
                    f"atempo={tempo:.5f}",
                ]
            )

    return ",".join(filters)


def _metadata_args(level: str) -> list[str]:
    level = str(level or "off").strip().lower()
    if level == "off":
        return []

    args = ["-map_metadata", "-1", "-map_chapters", "-1"]
    if level == "high":
        args.extend(
            [
                "-metadata",
                "title=",
                "-metadata",
                "artist=",
                "-metadata",
                "album=",
                "-metadata",
                "comment=",
                "-metadata",
                "description=",
                "-metadata",
                "encoder=",
                "-metadata:s:v:0",
                "handler_name=",
                "-metadata:s:a:0",
                "handler_name=",
            ]
        )
    return args


def apply_split_edit_to_clip(
    input_path: Path,
    output_folder: Path,
    settings: dict,
    ffmpeg: str = "ffmpeg",
    progress_cb: Optional[Callable[[str], None]] = None,
) -> Optional[Path]:
    settings = merge_split_edit_settings(settings)
    input_path = Path(input_path)
    output_folder = Path(output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)

    output_path = output_folder / f"{input_path.stem}_fx{input_path.suffix or '.mp4'}"
    flags = _creationflags()

    video_filter = _build_video_filter(settings)
    has_audio = _has_audio_stream(input_path, ffmpeg)
    separated_vocals: Optional[Path] = None
    temp_cleanup_paths: list[Path] = []

    _emit(progress_cb, f"  Split+Edit: editing {input_path.name}...")
    if settings["remove_background_music"]:
        _emit(progress_cb, "  Split+Edit: reducing background music...")
    if settings["voice_enhance_enabled"]:
        _emit(progress_cb, "  Split+Edit: enhancing voice...")

    if has_audio and settings["remove_background_music"]:
        separated_vocals = _separate_vocals_with_demucs(
            input_path=input_path,
            output_folder=output_folder,
            ffmpeg=ffmpeg,
            progress_cb=progress_cb,
        )
        if separated_vocals:
            temp_cleanup_paths.append(separated_vocals.parent)
            _emit(progress_cb, f"  Split+Edit: Demucs vocals ready -> {separated_vocals.name}")

    audio_filter = _build_audio_filter(settings, music_isolated=bool(separated_vocals))

    cmd = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(input_path),
    ]

    if separated_vocals:
        cmd.extend(["-i", str(separated_vocals)])

    if video_filter:
        cmd.extend(["-vf", video_filter])

    cmd.extend(["-map", "0:v:0"])

    cmd.extend(
        [
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
        ]
    )

    if has_audio:
        if separated_vocals:
            cmd.extend(["-map", "1:a:0"])
        else:
            cmd.extend(["-map", "0:a:0?"])
        if audio_filter:
            cmd.extend(["-af", audio_filter])
        if separated_vocals:
            cmd.append("-shortest")
        cmd.extend(["-c:a", "aac", "-b:a", "192k"])
    else:
        cmd.append("-an")

    cmd.extend(_metadata_args(settings["metadata_level"]))
    cmd.extend(["-movflags", "+faststart", str(output_path)])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=1800,
            creationflags=flags,
        )
        if result.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0:
            _emit(progress_cb, f"  Split+Edit: done -> {output_path.name}")
            return output_path
        err = (result.stderr or result.stdout or "").strip()
        _emit(progress_cb, f"  Split+Edit: failed for {input_path.name}")
        if err:
            _emit(progress_cb, f"  Split+Edit: ffmpeg error: {err[:160]}")
    except Exception as exc:
        _emit(progress_cb, f"  Split+Edit: exception for {input_path.name} ({str(exc)[:140]})")
    finally:
        _cleanup_temp_paths(temp_cleanup_paths)

    try:
        if output_path.exists():
            output_path.unlink()
    except Exception:
        pass
    return None
