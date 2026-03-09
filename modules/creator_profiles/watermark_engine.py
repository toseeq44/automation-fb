"""
modules/creator_profiles/watermark_engine.py
FFmpeg-based watermark applier for creator profile videos.

Supports:
  - Text watermark  (font, color, size, weight, style, letter-spacing, opacity)
  - Logo watermark  (image/svg, opacity)
  - Positions: TopLeft, TopRight, BottomLeft, BottomRight, Center, AnimateAround
  - Both text + logo simultaneously, each with independent position
"""

import shutil
import subprocess
from pathlib import Path
from typing import Callable, Dict, List, Optional

# Supported logo image formats (auto-detect in creator folder)
_LOGO_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".svg", ".gif"}

# Margin from edges (pixels)
_MARGIN = 20

# AnimateAround: fallback loop period (seconds) when duration is unavailable.
_ANIMATE_CYCLE_SEC_DEFAULT = 8.0


def _ffmpeg_path() -> str:
    try:
        from modules.video_editor.utils import check_ffmpeg, get_ffmpeg_path
        if check_ffmpeg():
            return get_ffmpeg_path()
    except Exception:
        pass
    return "ffmpeg"


def _animate_rect_expr(
    width_expr: str,
    height_expr: str,
    margin: int,
    cycle_sec: float,
) -> tuple:
    """
    Build 4-corner rectangular path:
      TopLeft -> TopRight -> BottomRight -> BottomLeft -> TopLeft
    """
    m = margin
    cycle = max(1.0, float(cycle_sec or _ANIMATE_CYCLE_SEC_DEFAULT))
    quarter = cycle / 4.0
    t_mod = f"mod(t,{cycle:g})"
    x_max = f"{width_expr}-{m}"
    y_max = f"{height_expr}-{m}"
    x_rng = f"({x_max}-{m})"
    y_rng = f"({y_max}-{m})"

    x_expr = (
        f"if(lt({t_mod},{quarter:g}),{m}+{x_rng}*({t_mod}/{quarter:g}),"
        f"if(lt({t_mod},{(2 * quarter):g}),{x_max},"
        f"if(lt({t_mod},{(3 * quarter):g}),"
        f"{x_max}-{x_rng}*(({t_mod}-{(2 * quarter):g})/{quarter:g}),{m})))"
    )
    y_expr = (
        f"if(lt({t_mod},{quarter:g}),{m},"
        f"if(lt({t_mod},{(2 * quarter):g}),"
        f"{m}+{y_rng}*(({t_mod}-{quarter:g})/{quarter:g}),"
        f"if(lt({t_mod},{(3 * quarter):g}),{y_max},"
        f"{y_max}-{y_rng}*(({t_mod}-{(3 * quarter):g})/{quarter:g}))))"
    )
    return x_expr, y_expr


def _escape_filter_expr(expr: str) -> str:
    """Escape expression chars that break ffmpeg option parsing."""
    return str(expr).replace("\\", "\\\\").replace(",", "\\,")


def _position_expr(
    position: str,
    margin: int = _MARGIN,
    target: str = "overlay",
    cycle_sec: float = _ANIMATE_CYCLE_SEC_DEFAULT,
) -> tuple:
    """Return (x_expr, y_expr) for drawtext or overlay filter."""
    m = margin
    pos = (position or "BottomRight").strip()
    is_text = str(target).strip().lower() == "text"

    if is_text:
        mapping = {
            "TopLeft":     (f"{m}", f"{m}"),
            "TopRight":    (f"w-text_w-{m}", f"{m}"),
            "BottomLeft":  (f"{m}", f"h-text_h-{m}"),
            "BottomRight": (f"w-text_w-{m}", f"h-text_h-{m}"),
            "Center":      ("(w-text_w)/2", "(h-text_h)/2"),
        }
    else:
        mapping = {
            "TopLeft":     (f"{m}", f"{m}"),
            "TopRight":    (f"W-w-{m}", f"{m}"),
            "BottomLeft":  (f"{m}", f"H-h-{m}"),
            "BottomRight": (f"W-w-{m}", f"H-h-{m}"),
            "Center":      ("(W-w)/2", "(H-h)/2"),
        }

    if pos == "AnimateAround":
        if is_text:
            return _animate_rect_expr("w-text_w", "h-text_h", m, cycle_sec)
        return _animate_rect_expr("W-w", "H-h", m, cycle_sec)
    return mapping.get(pos, mapping["BottomRight"])


def _opacity_to_alpha(opacity: int) -> float:
    """Convert 0-100 opacity to 0.0-1.0 alpha."""
    return max(0.0, min(1.0, int(opacity or 80) / 100.0))


def _hex_to_ffmpeg_color(hex_color: str, opacity: int) -> str:
    """Convert #RRGGBB + opacity(0-100) to ffmpeg color string 0xRRGGBB@A.

    Using @alpha is more reliable across ffmpeg builds for drawtext than
    packed hex with trailing AA.
    """
    hex_color = (hex_color or "#FFFFFF").strip().lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join(c * 2 for c in hex_color)
    if len(hex_color) != 6:
        hex_color = "FFFFFF"
    alpha = max(0.0, min(1.0, float(opacity) / 100.0))
    return f"0x{hex_color.upper()}@{alpha:.3f}"


def _normalize_render_style(value: str) -> str:
    style = str(value or "normal").strip().lower()
    if style in {"normal", "outline_hollow", "outline_shadow"}:
        return style
    return "normal"


def _sanitize_text(text: str) -> str:
    """Escape special characters for ffmpeg drawtext."""
    text = text.replace("\\", "\\\\")
    text = text.replace("'", "\\'")
    text = text.replace(":", "\\:")
    return text


def _ffprobe_path(ffmpeg_path: str) -> str:
    """Best-effort ffprobe resolver matching selected ffmpeg binary."""
    try:
        ffmpeg_p = Path(ffmpeg_path)
        if ffmpeg_p.exists():
            # Common layout: .../bin/ffmpeg.exe -> .../bin/ffprobe.exe
            candidate = ffmpeg_p.with_name("ffprobe.exe")
            if candidate.exists():
                return str(candidate)
            candidate2 = ffmpeg_p.with_name("ffprobe")
            if candidate2.exists():
                return str(candidate2)
    except Exception:
        pass

    return shutil.which("ffprobe") or "ffprobe"


def _probe_duration_sec(input_path: Path, ffmpeg_path: str) -> Optional[float]:
    """Return media duration in seconds using ffprobe, else None."""
    ffprobe = _ffprobe_path(ffmpeg_path)
    try:
        run = subprocess.run(
            [
                ffprobe,
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(input_path),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if run.returncode != 0:
            return None
        value = (run.stdout or "").strip()
        if not value:
            return None
        sec = float(value)
        if sec <= 0:
            return None
        return sec
    except Exception:
        return None


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
    media_duration_sec = _probe_duration_sec(input_path, ffmpeg) or _ANIMATE_CYCLE_SEC_DEFAULT

    explicit_layer_selection = bool(wm_text_cfg.get("enabled", False)) or bool(wm_logo_cfg.get("enabled", False))
    text_enabled = bool(wm_text_cfg.get("enabled", False)) if explicit_layer_selection else True
    logo_enabled = bool(wm_logo_cfg.get("enabled", False)) if explicit_layer_selection else True

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
            folder_name = str(folder_name or "").strip()
            # Avoid accidental "@@name" when folder already starts with '@'.
            raw_text = folder_name if folder_name.startswith("@") else f"@{folder_name}"

        text = _sanitize_text(raw_text)
        font_family = (wm_text_cfg.get("font_family") or "Arial").strip()
        font_color_hex = wm_text_cfg.get("font_color") or "#FFFFFF"
        font_size = int(wm_text_cfg.get("font_size") or 24)
        opacity = int(wm_text_cfg.get("opacity") or 80)
        font_weight = (wm_text_cfg.get("font_weight") or "bold").strip().lower()
        font_style = (wm_text_cfg.get("font_style") or "normal").strip().lower()
        letter_spacing = int(wm_text_cfg.get("letter_spacing") or 0)
        position = wm_text_cfg.get("position") or "BottomRight"
        render_style = _normalize_render_style(wm_text_cfg.get("render_style"))
        default_shadow_opacity = max(35, min(100, int(opacity * 0.75)))
        default_shadow_offset = max(2, int(round(font_size * 0.08)))
        try:
            shadow_alpha = int(wm_text_cfg.get("shadow_opacity", default_shadow_opacity))
        except Exception:
            shadow_alpha = default_shadow_opacity
        shadow_alpha = max(0, min(100, shadow_alpha))
        try:
            shadow_offset = int(wm_text_cfg.get("shadow_offset", default_shadow_offset))
        except Exception:
            shadow_offset = default_shadow_offset
        shadow_offset = max(0, min(80, shadow_offset))

        x_expr_raw, y_expr_raw = _position_expr(position, target="text", cycle_sec=media_duration_sec)
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
        font_with_style = _sanitize_text(font_with_style)

        transparent_fill = _hex_to_ffmpeg_color(font_color_hex, 0)

        def _drawtext_opts(
            x_raw: str,
            y_raw: str,
            font_color: str,
            border_w: int = 0,
            border_color: str = "",
            shadow_x: int = 0,
            shadow_y: int = 0,
            shadow_color: str = "",
        ) -> str:
            x_expr = _escape_filter_expr(x_raw)
            y_expr = _escape_filter_expr(y_raw)
            opts = [
                f"text='{text}'",
                f"font='{font_with_style}'",
                f"fontsize={font_size}",
                f"fontcolor={font_color}",
                f"x='{x_expr}'",
                f"y='{y_expr}'",
            ]
            if border_w > 0 and border_color:
                opts.append(f"borderw={border_w}")
                opts.append(f"bordercolor={border_color}")
            if shadow_x or shadow_y:
                opts.append(f"shadowx={int(shadow_x)}")
                opts.append(f"shadowy={int(shadow_y)}")
                if shadow_color:
                    opts.append(f"shadowcolor={shadow_color}")
            if letter_spacing > 0:
                opts.append("expansion=normal")
            return ":".join(opts)

        if render_style == "normal":
            out_label = "[vtxt]"
            drawtext = _drawtext_opts(
                x_raw=x_expr_raw,
                y_raw=y_expr_raw,
                font_color=color_str,
            )
            filter_parts.append(f"{last_label}drawtext={drawtext}{out_label}")
            last_label = out_label

        elif render_style == "outline_hollow":
            # Stable hollow: transparent fill + visible stroke.
            border_w = max(1, int(round(font_size * 0.06)))
            out_label = "[vtxt]"
            drawtext = _drawtext_opts(
                x_raw=x_expr_raw,
                y_raw=y_expr_raw,
                font_color=transparent_fill,
                border_w=border_w,
                border_color=color_str,
            )
            filter_parts.append(f"{last_label}drawtext={drawtext}{out_label}")
            last_label = out_label

        else:  # outline_shadow
            # Readable style:
            # 1) offset shadow fill
            # 2) main fill + stroke
            border_w = max(1, int(round(font_size * 0.06)))
            shadow_color = _hex_to_ffmpeg_color("#000000", shadow_alpha)
            shadow_x_raw = f"({x_expr_raw})+{shadow_offset}"
            shadow_y_raw = f"({y_expr_raw})+{shadow_offset}"
            fill_color = _hex_to_ffmpeg_color("#FFFFFF", opacity)

            shadow_label = "[vtxt_sh]"
            out_label = "[vtxt]"

            shadow_draw = _drawtext_opts(
                x_raw=shadow_x_raw,
                y_raw=shadow_y_raw,
                font_color=shadow_color,
            )
            main_draw = _drawtext_opts(
                x_raw=x_expr_raw,
                y_raw=y_expr_raw,
                font_color=fill_color,
                border_w=border_w,
                border_color=color_str,
            )

            filter_parts.append(f"{last_label}drawtext={shadow_draw}{shadow_label}")
            filter_parts.append(f"{shadow_label}drawtext={main_draw}{out_label}")
            last_label = out_label

    # ── Logo watermark filter ──────────────────────────────────────────────
    if logo_enabled and logo_path:
        logo_opacity = int(wm_logo_cfg.get("opacity") or 80)
        alpha = _opacity_to_alpha(logo_opacity)
        position = wm_logo_cfg.get("position") or "TopLeft"
        x_expr, y_expr = _position_expr(position, target="overlay", cycle_sec=media_duration_sec)
        x_expr = _escape_filter_expr(x_expr)
        y_expr = _escape_filter_expr(y_expr)

        logo_idx = logo_input_index
        logo_scaled = f"[logo_sc]"
        base_label = f"[vbase]"
        logo_alpha = f"[logo_a]"
        out_label = "[vlogo]"

        # Scale logo to max 15% of video width, keep aspect ratio
        filter_parts.append(
            f"[{logo_idx}:v]{last_label}scale2ref="
            f"w='min(iw\\,main_w*0.15)':h=-1"
            f"{logo_scaled}{base_label}"
        )
        filter_parts.append(
            f"{logo_scaled}format=rgba,colorchannelmixer=aa={alpha:.3f}{logo_alpha}"
        )
        filter_parts.append(
            f"{base_label}{logo_alpha}overlay=eval=frame:x='{x_expr}':y='{y_expr}'{out_label}"
        )
        last_label = out_label

    # ── Build full command ─────────────────────────────────────────────────
    filter_str = ";".join(filter_parts)

    cmd = (
        [ffmpeg, "-hide_banner", "-loglevel", "error"]
        + inputs
        + [
            "-filter_complex", filter_str,
            "-map", last_label,
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
