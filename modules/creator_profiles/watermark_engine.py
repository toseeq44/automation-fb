"""
modules/creator_profiles/watermark_engine.py
FFmpeg-based watermark applier for creator profile videos.

Supports:
  - Text watermark  (font, color, size, weight, style, letter-spacing, opacity)
  - Logo watermark  (image/svg, opacity)
  - Positions: TopLeft, TopRight, BottomLeft, BottomRight, Center, AnimateAround
  - Both text + logo simultaneously, each with independent position
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Callable, Dict, List, Optional

# Supported logo image formats (auto-detect in creator folder)
_LOGO_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".svg", ".gif"}
_AVATAR_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".svg"}
_AVATAR_VIDEO_EXTS = {".mp4", ".mov", ".webm", ".mkv", ".avi", ".gif", ".m4v"}
_AVATAR_EXTS = _AVATAR_IMAGE_EXTS | _AVATAR_VIDEO_EXTS

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


def auto_detect_avatar(creator_folder: Path) -> Optional[str]:
    """
    Look for a file named 'avatar.*' in creator_folder.
    Returns absolute path string or None.
    """
    folder = Path(creator_folder)
    for ext in _AVATAR_EXTS:
        candidate = folder / f"avatar{ext}"
        if candidate.exists():
            return str(candidate)
    return None


def _avatar_media_kind(path: Path, ffmpeg_path: str) -> str:
    suffix = str(path.suffix or "").strip().lower()
    if suffix in _AVATAR_VIDEO_EXTS:
        return "video"
    if suffix in _AVATAR_IMAGE_EXTS:
        return "image"

    ffprobe = _ffprobe_path(ffmpeg_path)
    try:
        run = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=codec_name",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if run.returncode == 0 and (run.stdout or "").strip():
            return "video"
    except Exception:
        pass
    return "image"


def _avatar_box_dims(cfg: Dict) -> tuple[int, int]:
    try:
        width = int(cfg.get("width", 160) or 160)
    except Exception:
        width = 160
    try:
        height = int(cfg.get("height", 160) or 160)
    except Exception:
        height = 160
    return max(8, min(2000, width)), max(8, min(2000, height))


def _contains_cjk_or_cyrillic(text: str) -> str:
    """
    Returns 'cjk' if Chinese/Japanese/Korean characters are found.
    Returns 'cyrillic' if Russian/Cyrillic characters are found.
    Returns None otherwise.
    """
    for char in text:
        cp = ord(char)
        # CJK Unified Ideographs + Hiragana/Katakana + Hangul
        if (0x4E00 <= cp <= 0x9FFF) or (0x3040 <= cp <= 0x309F) or (0x30A0 <= cp <= 0x30FF) or (0xAC00 <= cp <= 0xD7A3):
            return 'cjk'
        # Cyrillic
        if 0x0400 <= cp <= 0x04FF:
            return 'cyrillic'
    return None


def _contains_non_ascii(text: str) -> bool:
    return any(ord(char) > 127 for char in (text or ""))


def _pick_qt_font_family(requested_family: str, text: str) -> str:
    """
    Pick the best available Qt font family for the watermark text.

    Qt does font fallback better than ffmpeg drawtext on Windows, so we lean on
    it for multilingual text rendering.
    """
    try:
        from PyQt5.QtGui import QFontDatabase
    except Exception:
        return (requested_family or "").strip()

    requested = (requested_family or "").strip()
    db = QFontDatabase()
    available = {family.casefold(): family for family in db.families()}

    candidates: List[str] = []
    if requested:
        candidates.append(requested)

    if _contains_non_ascii(text):
        candidates.extend(
            [
                "Segoe UI",
                "Arial Unicode MS",
                "Tahoma",
                "Microsoft YaHei UI",
                "Microsoft YaHei",
                "Microsoft JhengHei UI",
                "Microsoft JhengHei",
                "Yu Gothic UI",
                "Yu Gothic",
                "Malgun Gothic",
                "Meiryo",
                "Nirmala UI",
                "Leelawadee UI",
                "Ebrima",
                "Segoe UI Emoji",
                "Arial",
            ]
        )
    else:
        candidates.extend(["Segoe UI", "Arial", "Verdana", "Tahoma"])

    seen = set()
    for candidate in candidates:
        key = str(candidate or "").strip().casefold()
        if not key or key in seen:
            continue
        seen.add(key)
        match = available.get(key)
        if match:
            return match

    return requested

def _resolve_windows_font(font_family: str, weight: str = "normal", style: str = "normal", text: str = "") -> Optional[str]:
    """
    Look up exact paths for known Unicode-rich fonts on Windows to avoid fontconfig 
    (which often fails or drops characters on Windows FFmpeg builds).
    Auto-detects CJK/Cyrillic to force a fallback font that works.
    """
    import os
    font_dir = Path(os.environ.get("WINDIR", "C:\\Windows")) / "Fonts"
    if not font_dir.exists():
        return None
        
    family = font_family.lower()
    is_bold = weight == "bold"
    is_italic = style == "italic"

    # ── Unicode Fallback Injection ──
    char_type = _contains_cjk_or_cyrillic(text)
    if char_type == 'cjk':
        # Force Microsoft YaHei for CJK to prevent boxes
        family = "microsoft yahei"
    elif char_type == 'cyrillic' and family not in ["segoe ui", "arial", "verdana", "tahoma", "times new roman"]:
        # Arial has good Cyrillic support
        family = "arial"
    
    # Common mappings
    # family -> (regular, bold, italic, bold_italic)
    mappings = {
        "segoe ui": ("segoeui.ttf", "segoeuib.ttf", "segoeuii.ttf", "segoeuiz.ttf"),
        "arial unicode ms": ("ARIALUNI.TTF", "ARIALUNI.TTF", "ARIALUNI.TTF", "ARIALUNI.TTF"), # arialuni only has regular
        "arial": ("arial.ttf", "arialbd.ttf", "ariali.ttf", "arialbi.ttf"),
        "verdana": ("verdana.ttf", "verdanab.ttf", "verdanai.ttf", "verdanaz.ttf"),
        "times new roman": ("times.ttf", "timesbd.ttf", "timesi.ttf", "timesbi.ttf"),
        "georgia": ("georgia.ttf", "georgiab.ttf", "georgiai.ttf", "georgiaz.ttf"),
        "trebuchet ms": ("trebuc.ttf", "trebucbd.ttf", "trebucit.ttf", "trebucbi.ttf"),
        "microsoft yahei": ("msyh.ttc", "msyhbd.ttc", "msyh.ttc", "msyhbd.ttc"),
    }
    
    if family in mappings:
        names = mappings[family]
        if is_bold and is_italic: target = names[3]
        elif is_bold: target = names[1]
        elif is_italic: target = names[2]
        else: target = names[0]
        
        path = font_dir / target
        if path.exists():
            return str(path)
            
    return None


def _render_text_overlay_image(
    text: str,
    wm_text_cfg: Dict,
    output_path: Path,
    progress_cb: Callable[[str], None] = None,
) -> bool:
    """
    Render watermark text into a transparent PNG using Qt text rendering.

    This path is much more reliable for multilingual scripts than ffmpeg
    drawtext on Windows because Qt can use native font fallback/shaping.
    """
    try:
        from PyQt5.QtCore import QPointF, QRectF, Qt
        from PyQt5.QtGui import QColor, QFont, QFontMetrics, QImage, QPainter
        from PyQt5.QtWidgets import QApplication
    except Exception as e:
        if progress_cb:
            progress_cb(f"    WaterMark: Qt text renderer unavailable ({e})")
        return False

    owned_app = None
    app = QApplication.instance()
    if app is None:
        try:
            os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
            owned_app = QApplication([])
            app = owned_app
        except Exception as e:
            if progress_cb:
                progress_cb(f"    WaterMark: failed to init Qt renderer ({e})")
            return False

    raw_text = str(text or "")
    if not raw_text:
        return False

    requested_family = (wm_text_cfg.get("font_family") or "").strip()
    font_family = _pick_qt_font_family(requested_family, raw_text)
    font_size = max(8, int(wm_text_cfg.get("font_size") or 24))
    font_weight = (wm_text_cfg.get("font_weight") or "bold").strip().lower()
    font_style = (wm_text_cfg.get("font_style") or "normal").strip().lower()
    render_style = _normalize_render_style(wm_text_cfg.get("render_style"))
    font_color_hex = wm_text_cfg.get("font_color") or "#FFFFFF"
    opacity = max(0, min(100, int(wm_text_cfg.get("opacity") or 80)))
    letter_spacing = max(0, int(wm_text_cfg.get("letter_spacing") or 0))
    shadow_alpha = max(0, min(100, int(wm_text_cfg.get("shadow_opacity", 75) or 75)))
    shadow_offset = max(0, min(80, int(wm_text_cfg.get("shadow_offset", 2) or 2)))

    has_non_ascii = _contains_non_ascii(raw_text)
    # Complex scripts can break when spacing/style are forced through fallback fonts.
    if has_non_ascii:
        letter_spacing = 0
        if font_family.casefold() != requested_family.casefold():
            font_weight = "normal"
            font_style = "normal"
        if render_style == "outline_hollow":
            render_style = "normal"

    font = QFont()
    if font_family:
        font.setFamily(font_family)
    font.setPixelSize(font_size)
    font.setBold(font_weight == "bold")
    font.setItalic(font_style == "italic")
    font.setStyleStrategy(QFont.PreferDefault)
    if letter_spacing > 0:
        font.setLetterSpacing(QFont.AbsoluteSpacing, float(letter_spacing))

    metrics = QFontMetrics(font)
    lines = raw_text.splitlines() or [raw_text]
    lines = lines if lines else [raw_text]
    line_height = max(metrics.lineSpacing(), metrics.height())
    widths = [max(1, metrics.horizontalAdvance(line or " ")) for line in lines]
    outline_px = max(1, int(round(font_size * 0.06)))
    padding = max(8, int(round(font_size * 0.35)))
    extra = shadow_offset if render_style == "outline_shadow" else outline_px
    canvas_w = max(widths) + (padding * 2) + (extra * 2)
    canvas_h = (line_height * len(lines)) + (padding * 2) + (extra * 2)

    image = QImage(canvas_w, canvas_h, QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)

    fill_color = QColor(font_color_hex)
    if not fill_color.isValid():
        fill_color = QColor("#FFFFFF")
    fill_color.setAlphaF(opacity / 100.0)

    shadow_color = QColor("#000000")
    shadow_color.setAlphaF(shadow_alpha / 100.0)

    painter = QPainter(image)
    try:
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        painter.setFont(font)

        text_x = padding + extra
        text_y = padding + extra
        text_rect = QRectF(
            float(text_x),
            float(text_y),
            float(canvas_w - (text_x * 2) + padding),
            float(canvas_h - (text_y * 2) + padding),
        )

        def _draw_lines(offset_x: int, offset_y: int, color: QColor) -> None:
            painter.setPen(color)
            for idx, line in enumerate(lines):
                line_rect = QRectF(
                    text_rect.x() + offset_x,
                    text_rect.y() + offset_y + (idx * line_height),
                    text_rect.width(),
                    float(line_height),
                )
                painter.drawText(line_rect, int(Qt.AlignLeft | Qt.AlignVCenter), line)

        if render_style == "outline_hollow" and not has_non_ascii:
            for dx in range(-outline_px, outline_px + 1):
                for dy in range(-outline_px, outline_px + 1):
                    if dx == 0 and dy == 0:
                        continue
                    _draw_lines(dx, dy, fill_color)
        elif render_style == "outline_shadow":
            _draw_lines(shadow_offset, shadow_offset, shadow_color)
            if not has_non_ascii:
                for dx in range(-outline_px, outline_px + 1):
                    for dy in range(-outline_px, outline_px + 1):
                        if dx == 0 and dy == 0:
                            continue
                        _draw_lines(dx, dy, fill_color)
            _draw_lines(0, 0, fill_color)
        else:
            _draw_lines(0, 0, fill_color)
    finally:
        painter.end()
        owned_app = None

    return image.save(str(output_path), "PNG")


def apply_watermark(
    input_path: Path,
    output_path: Path,
    creator_folder: Path,
    wm_text_cfg: Dict,
    wm_logo_cfg: Dict,
    wm_avatar_cfg: Dict,
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
    temp_overlay_files: List[Path] = []

    explicit_layer_selection = (
        bool(wm_text_cfg.get("enabled", False))
        or bool(wm_logo_cfg.get("enabled", False))
        or bool(wm_avatar_cfg.get("enabled", False))
    )
    text_enabled = bool(wm_text_cfg.get("enabled", False)) if explicit_layer_selection else True
    logo_enabled = bool(wm_logo_cfg.get("enabled", False)) if explicit_layer_selection else True
    avatar_enabled = bool(wm_avatar_cfg.get("enabled", False)) if explicit_layer_selection else False

    if not text_enabled and not logo_enabled and not avatar_enabled:
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

    avatar_path: Optional[str] = None
    avatar_kind = "image"
    if avatar_enabled:
        avatar_path = (wm_avatar_cfg.get("path") or "").strip()
        if not avatar_path or not Path(avatar_path).exists():
            avatar_path = auto_detect_avatar(creator_folder)
        if not avatar_path:
            if progress_cb:
                progress_cb("    WaterMark: avatar file not found, skipping avatar layer")
            avatar_enabled = False
        else:
            avatar_kind = _avatar_media_kind(Path(avatar_path), ffmpeg)

    text_overlay_path: Optional[Path] = None
    if text_enabled:
        raw_text = (wm_text_cfg.get("text") or "").strip()
        if not raw_text:
            folder_name = Path(creator_folder).name
            folder_name = str(folder_name or "").strip()
            raw_text = folder_name if folder_name.startswith("@") else f"@{folder_name}"

        try:
            fd, tmp_png = tempfile.mkstemp(prefix="wm_text_", suffix=".png")
            os.close(fd)
            candidate_path = Path(tmp_png)
            if _render_text_overlay_image(
                text=raw_text,
                wm_text_cfg=wm_text_cfg,
                output_path=candidate_path,
                progress_cb=progress_cb,
            ):
                text_overlay_path = candidate_path
                temp_overlay_files.append(candidate_path)
            else:
                try:
                    candidate_path.unlink(missing_ok=True)
                except Exception:
                    pass
                if progress_cb:
                    progress_cb("    WaterMark: Qt text render failed, using ffmpeg text fallback")
        except Exception as e:
            if progress_cb:
                progress_cb(f"    WaterMark: text overlay prep failed ({e})")

    # ── Build ffmpeg filter chain ──────────────────────────────────────────
    inputs: List[str] = ["-i", str(input_path)]
    next_input_index = 1
    avatar_input_index: Optional[int] = None
    if avatar_enabled and avatar_path:
        avatar_input_index = next_input_index
        if avatar_kind == "video":
            inputs += ["-stream_loop", "-1", "-i", avatar_path]
        else:
            inputs += ["-i", avatar_path]
        next_input_index += 1
    text_input_index: Optional[int] = None
    if text_enabled and text_overlay_path:
        text_input_index = next_input_index
        inputs += ["-i", str(text_overlay_path)]
        next_input_index += 1
    if logo_enabled and logo_path:
        logo_input_index = next_input_index
        inputs += ["-i", logo_path]
        next_input_index += 1
    else:
        logo_input_index = None

    filter_parts: List[str] = []
    last_label = "[0:v]"

    if avatar_enabled and avatar_path and avatar_input_index is not None:
        avatar_opacity = int(wm_avatar_cfg.get("opacity") or 80)
        avatar_alpha = _opacity_to_alpha(avatar_opacity)
        avatar_width, avatar_height = _avatar_box_dims(wm_avatar_cfg)
        avatar_position = wm_avatar_cfg.get("position") or "TopRight"
        x_expr, y_expr = _position_expr(avatar_position, target="overlay", cycle_sec=media_duration_sec)
        x_expr = _escape_filter_expr(x_expr)
        y_expr = _escape_filter_expr(y_expr)

        avatar_src = "[avatar_src]"
        avatar_box = "[avatar_box]"
        avatar_alpha_label = "[avatar_a]"
        avatar_out = "[vavatar]"

        if avatar_kind == "video":
            filter_parts.append(f"[{avatar_input_index}:v]setpts=PTS-STARTPTS{avatar_src}")
        else:
            filter_parts.append(f"[{avatar_input_index}:v]format=rgba{avatar_src}")

        filter_parts.append(
            f"{avatar_src}scale=w={avatar_width}:h={avatar_height}:force_original_aspect_ratio=decrease,"
            f"format=rgba,pad={avatar_width}:{avatar_height}:(ow-iw)/2:(oh-ih)/2:color=black@0.0"
            f"{avatar_box}"
        )
        filter_parts.append(
            f"{avatar_box}colorchannelmixer=aa={avatar_alpha:.3f}{avatar_alpha_label}"
        )
        filter_parts.append(
            f"{last_label}{avatar_alpha_label}overlay=eval=frame:shortest=1:x='{x_expr}':y='{y_expr}'{avatar_out}"
        )
        last_label = avatar_out

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
        if text_input_index is not None and text_overlay_path:
            x_expr, y_expr = _position_expr(position, target="overlay", cycle_sec=media_duration_sec)
            x_expr = _escape_filter_expr(x_expr)
            y_expr = _escape_filter_expr(y_expr)
            out_label = "[vtxt]"
            filter_parts.append(
                f"{last_label}[{text_input_index}:v]overlay=eval=frame:x='{x_expr}':y='{y_expr}'{out_label}"
            )
            last_label = out_label
        else:
            # Fallback only: use legacy drawtext when Qt image rendering is unavailable.
            font_file = _resolve_windows_font(font_family, font_weight, font_style, raw_text)

            if font_file:
                ff_font_file = font_file.replace("\\", "\\\\").replace(":", "\\:")
                font_opt = f"fontfile='{ff_font_file}'"
            else:
                font_with_style = font_family
                if font_weight == "bold" and font_style == "italic":
                    font_with_style = f"{font_family}:Bold Italic"
                elif font_weight == "bold":
                    font_with_style = f"{font_family}:Bold"
                elif font_style == "italic":
                    font_with_style = f"{font_family}:Italic"
                font_with_style = _sanitize_text(font_with_style)
                font_opt = f"font='{font_with_style}'"

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
                    font_opt,
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
        logo_size_pct = max(1, min(100, int(wm_logo_cfg.get("size", 15))))
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

        # Scale logo to X% of video width, keep aspect ratio
        scale_ratio = logo_size_pct / 100.0
        filter_parts.append(
            f"[{logo_idx}:v]{last_label}scale2ref="
            f"w='min(iw\\,main_w*{scale_ratio:.3f})':h=-1"
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

    ok = False
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
        if r.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0:
            if progress_cb:
                progress_cb(f"    WaterMark: done → {output_path.name}")
            ok = True
        else:
            if progress_cb:
                err = (r.stderr or "")[-200:]
                progress_cb(f"    WaterMark: ffmpeg error: {err}")
    except Exception as e:
        if progress_cb:
            progress_cb(f"    WaterMark: exception: {e}")
    finally:
        for temp_path in temp_overlay_files:
            try:
                temp_path.unlink(missing_ok=True)
            except Exception:
                pass
    return ok


def apply_watermark_inplace(
    video_path: Path,
    creator_folder: Path,
    wm_text_cfg: Dict,
    wm_logo_cfg: Dict,
    wm_avatar_cfg: Dict,
    keep_original: bool = False,
    ffmpeg: str = None,
    progress_cb: Callable[[str], None] = None,
) -> Optional[Path]:
    """
    Apply watermark to video_path. Returns final output path on success, else None.
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
        wm_avatar_cfg=wm_avatar_cfg,
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
        return None

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
            if video_path.exists():
                video_path.unlink()
            tmp_out.replace(video_path)
            return video_path
        except Exception as exc:
            if progress_cb:
                progress_cb(
                    f"    WaterMark: finalization warning for {video_path.name}: {exc}"
                )
            if tmp_out.exists():
                return tmp_out
            return None
