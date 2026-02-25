"""
modules/creator_profiles/watermark_engine.py
FFmpeg-based watermark applier for creator profile videos.

Supports:
  - Text watermark  (font, color, size, weight, style, letter-spacing, opacity)
  - Logo watermark  (image/svg, opacity)
  - Positions: TopLeft, TopRight, BottomLeft, BottomRight, Center, AnimateAround
  - Both text + logo simultaneously, each with independent position
"""

import re
import shutil
import subprocess
from pathlib import Path
from typing import Callable, Dict, List, Optional

# Supported logo image formats (auto-detect in creator folder)
_LOGO_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".svg", ".gif"}

# Margin from edges (pixels)
_MARGIN = 20

# AnimateAround: keyframe stops (x_expr, y_expr, t_start_frac, t_end_frac)
# Video is split into 4 equal segments, corner moves TopLeft→TopRight→BottomRight→BottomLeft
_ANIMATE_EXPR = (
    "x='if(lt(mod(t,4*{dur}),{dur}),{m},"
    "if(lt(mod(t,4*{dur}),2*{dur}),W-w-{m},"
    "if(lt(mod(t,4*{dur}),3*{dur}),W-w-{m},{m})))':"
    "y='if(lt(mod(t,4*{dur}),{dur}),{m},"
    "if(lt(mod(t,4*{dur}),2*{dur}),{m},"
    "if(lt(mod(t,4*{dur}),3*{dur}),H-h-{m},H-h-{m})))'"
)
_ANIMATE_DURATION = 3  # seconds per corner


def _ffmpeg_path() -> str:
    try:
        from modules.video_editor.utils import check_ffmpeg, get_ffmpeg_path
        if check_ffmpeg():
            p = get_ffmpeg_path()
            if p:
                return p
    except Exception:
        pass
    which = shutil.which("ffmpeg")
    if which:
        return which
    for candidate in [
        Path("bin/ffmpeg/ffmpeg.exe"),
        Path("C:/ffmpeg/bin/ffmpeg.exe"),
        Path("C:/ffmpeg/ffmpeg.exe"),
    ]:
        if candidate.exists():
            return str(candidate)
    return "ffmpeg"


def _position_expr(position: str, margin: int = _MARGIN) -> tuple:
    """Return (x_expr, y_expr) for drawtext/overlay filter."""
    m = margin
    pos = (position or "BottomRight").strip()
    mapping = {
        "TopLeft":     (f"{m}", f"{m}"),
        "TopRight":    (f"W-w-{m}", f"{m}"),
        "BottomLeft":  (f"{m}", f"H-h-{m}"),
        "BottomRight": (f"W-w-{m}", f"H-h-{m}"),
        "Center":      ("(W-w)/2", "(H-h)/2"),
    }
    if pos == "AnimateAround":
        dur = _ANIMATE_DURATION
        x = (
            f"if(lt(mod(t,4*{dur}),{dur}),{m},"
            f"if(lt(mod(t,4*{dur}),2*{dur}),W-w-{m},"
            f"if(lt(mod(t,4*{dur}),3*{dur}),W-w-{m},{m})))"
        )
        y = (
            f"if(lt(mod(t,4*{dur}),{dur}),{m},"
            f"if(lt(mod(t,4*{dur}),2*{dur}),{m},"
            f"if(lt(mod(t,4*{dur}),3*{dur}),H-h-{m},H-h-{m})))"
        )
        return x, y
    return mapping.get(pos, mapping["BottomRight"])


def _opacity_to_alpha(opacity: int) -> float:
    """Convert 0-100 opacity to 0.0-1.0 alpha."""
    return max(0.0, min(1.0, int(opacity or 80) / 100.0))


def _hex_to_ffmpeg_color(hex_color: str, opacity: int) -> str:
    """Convert #RRGGBB + opacity(0-100) to ffmpeg color string 0xRRGGBBAA."""
    hex_color = (hex_color or "#FFFFFF").strip().lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join(c * 2 for c in hex_color)
    if len(hex_color) != 6:
        hex_color = "FFFFFF"
    alpha_byte = int((opacity / 100.0) * 255)
    return f"0x{hex_color.upper()}{alpha_byte:02X}"


def _sanitize_text(text: str) -> str:
    """Escape special characters for ffmpeg drawtext."""
    text = text.replace("\\", "\\\\")
    text = text.replace("'", "\\'")
    text = text.replace(":", "\\:")
    return text


def auto_detect_logo(creator_folder: Path) -> Optional[str]:
    """
    Look for a file named 'logo.*' in creator_folder.
    Returns absolute path string or None.
    """
    folder = Path(creator_folder)
    for ext in _LOGO_EXTS:
        candidate = folder / f"logo{ext}"
        if candidate.exists():
            return str(candidate)
    return None


def apply_watermark(
    input_path: Path,
    output_path: Path,
    creator_folder: Path,
    wm_text_cfg: Dict,
    wm_logo_cfg: Dict,
    ffmpeg: str = None,
    progress_cb: Callable[[str], None] = None,
) -> bool:
    """
    Apply text and/or logo watermark to a video using ffmpeg.

    Returns True on success, False on failure.
    """
    if ffmpeg is None:
        ffmpeg = _ffmpeg_path()

    input_path = Path(input_path)
    output_path = Path(output_path)

    text_enabled = bool(wm_text_cfg.get("enabled", False))
    logo_enabled = bool(wm_logo_cfg.get("enabled", False))

    if not text_enabled and not logo_enabled:
        # Nothing to do — copy as-is
        try:
            shutil.copy2(str(input_path), str(output_path))
            return True
        except Exception:
            return False

    # ── Resolve logo path ──────────────────────────────────────────────────
    logo_path: Optional[str] = None
    if logo_enabled:
        logo_path = (wm_logo_cfg.get("path") or "").strip()
        if not logo_path or not Path(logo_path).exists():
            logo_path = auto_detect_logo(creator_folder)
        if not logo_path:
            if progress_cb:
                progress_cb("    WaterMark: logo file not found, skipping logo layer")
            logo_enabled = False

    # ── Build ffmpeg filter chain ──────────────────────────────────────────
    # Inputs: [0] = video
    # If logo: [1] = logo image
    inputs: List[str] = ["-i", str(input_path)]
    if logo_enabled and logo_path:
        inputs += ["-i", logo_path]

    filter_parts: List[str] = []
    last_label = "[0:v]"
    logo_input_index = 1  # ffmpeg input index for logo

    # ── Text watermark filter ──────────────────────────────────────────────
    if text_enabled:
        raw_text = (wm_text_cfg.get("text") or "").strip()
        if not raw_text:
            folder_name = Path(creator_folder).name
            raw_text = f"@{folder_name}"

        text = _sanitize_text(raw_text)
        font_family = (wm_text_cfg.get("font_family") or "Arial").strip()
        font_color_hex = wm_text_cfg.get("font_color") or "#FFFFFF"
        font_size = int(wm_text_cfg.get("font_size") or 24)
        opacity = int(wm_text_cfg.get("opacity") or 80)
        font_weight = (wm_text_cfg.get("font_weight") or "bold").strip().lower()
        font_style = (wm_text_cfg.get("font_style") or "normal").strip().lower()
        letter_spacing = int(wm_text_cfg.get("letter_spacing") or 0)
        position = wm_text_cfg.get("position") or "BottomRight"

        x_expr, y_expr = _position_expr(position)
        color_str = _hex_to_ffmpeg_color(font_color_hex, opacity)

        # Bold/italic: ffmpeg drawtext uses fontfile or font name with style suffix
        # We pass font name + style hint via 'font' option
        font_with_style = font_family
        if font_weight == "bold" and font_style == "italic":
            font_with_style = f"{font_family}:Bold Italic"
        elif font_weight == "bold":
            font_with_style = f"{font_family}:Bold"
        elif font_style == "italic":
            font_with_style = f"{font_family}:Italic"

        drawtext_opts = [
            f"text='{text}'",
            f"font='{font_with_style}'",
            f"fontsize={font_size}",
            f"fontcolor={color_str}",
            f"x={x_expr}",
            f"y={y_expr}",
        ]
        if letter_spacing > 0:
            drawtext_opts.append(f"expansion=normal")

        out_label = "[vtxt]"
        filter_parts.append(
            f"{last_label}drawtext={':'.join(drawtext_opts)}{out_label}"
        )
        last_label = out_label

    # ── Logo watermark filter ──────────────────────────────────────────────
    if logo_enabled and logo_path:
        logo_opacity = int(wm_logo_cfg.get("opacity") or 80)
        alpha = _opacity_to_alpha(logo_opacity)
        position = wm_logo_cfg.get("position") or "TopLeft"
        x_expr, y_expr = _position_expr(position)

        logo_idx = logo_input_index
        logo_scaled = f"[logo_sc]"
        logo_alpha = f"[logo_a]"
        out_label = "[vlogo]"

        # Scale logo to max 15% of video width, keep aspect ratio
        filter_parts.append(
            f"[{logo_idx}:v]scale=iw*min(W*0.15/iw\\,1):ih*min(W*0.15/iw\\,1)"
            f",format=rgba,colorchannelmixer=aa={alpha:.3f}{logo_alpha}"
        )
        filter_parts.append(
            f"{last_label}{logo_alpha}overlay=x={x_expr}:y={y_expr}{out_label}"
        )
        last_label = out_label

    # ── Build full command ─────────────────────────────────────────────────
    filter_str = ";".join(filter_parts)

    cmd = (
        [ffmpeg, "-hide_banner", "-loglevel", "error"]
        + inputs
        + [
            "-filter_complex", filter_str,
            "-map", last_label.strip("[]"),
            "-map", "0:a?",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-c:a", "copy",
            "-movflags", "+faststart",
            str(output_path), "-y",
        ]
    )

    if progress_cb:
        progress_cb(f"    WaterMark: applying to {input_path.name}...")

    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
        if r.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0:
            if progress_cb:
                progress_cb(f"    WaterMark: done → {output_path.name}")
            return True
        else:
            if progress_cb:
                err = (r.stderr or "")[-200:]
                progress_cb(f"    WaterMark: ffmpeg error: {err}")
            return False
    except Exception as e:
        if progress_cb:
            progress_cb(f"    WaterMark: exception: {e}")
        return False


def apply_watermark_inplace(
    video_path: Path,
    creator_folder: Path,
    wm_text_cfg: Dict,
    wm_logo_cfg: Dict,
    keep_original: bool = False,
    ffmpeg: str = None,
    progress_cb: Callable[[str], None] = None,
) -> Path:
    """
    Apply watermark to video_path. Returns path to watermarked file.
    If keep_original=False, replaces original. Otherwise saves as _wm suffix.
    """
    video_path = Path(video_path)
    tmp_out = video_path.with_name(f"{video_path.stem}_wm_tmp{video_path.suffix}")

    success = apply_watermark(
        input_path=video_path,
        output_path=tmp_out,
        creator_folder=creator_folder,
        wm_text_cfg=wm_text_cfg,
        wm_logo_cfg=wm_logo_cfg,
        ffmpeg=ffmpeg,
        progress_cb=progress_cb,
    )

    if not success:
        # Clean up temp if exists
        if tmp_out.exists():
            try:
                tmp_out.unlink()
            except Exception:
                pass
        return video_path  # Return original unchanged

    if keep_original:
        final_out = video_path.with_name(f"{video_path.stem}_wm{video_path.suffix}")
        try:
            tmp_out.rename(final_out)
        except Exception:
            final_out = tmp_out
        return final_out
    else:
        # Replace original
        try:
            video_path.unlink()
            tmp_out.rename(video_path)
        except Exception:
            pass
        return video_path
