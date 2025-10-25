"""
modules/video_editor/filters.py
Video Filters and Effects
Includes: Brightness, Contrast, Saturation, Blur, Grayscale, Invert, Sepia, etc.
"""

import numpy as np
from typing import Tuple
from modules.logging.logger import get_logger

logger = get_logger(__name__)

try:
    from moviepy.editor import VideoFileClip
    from moviepy.video.fx.all import blackwhite, colorx
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False


# ==================== COLOR FILTERS ====================

def adjust_brightness(clip, intensity: float = 1.0):
    """
    Adjust video brightness

    Args:
        clip: VideoClip
        intensity: Brightness multiplier (0.5 = darker, 2.0 = brighter)
    """
    return colorx(clip, intensity)


def adjust_contrast(clip, intensity: float = 1.0):
    """
    Adjust video contrast

    Args:
        clip: VideoClip
        intensity: Contrast level (0.5 = low contrast, 2.0 = high contrast)
    """
    def contrast_transform(image):
        # Convert to float for processing
        img = image.astype(np.float32)

        # Calculate mean
        mean = np.mean(img, axis=(0, 1), keepdims=True)

        # Apply contrast
        img = mean + intensity * (img - mean)

        # Clip to valid range and convert back
        return np.clip(img, 0, 255).astype(np.uint8)

    return clip.fl_image(contrast_transform)


def adjust_saturation(clip, intensity: float = 1.0):
    """
    Adjust video color saturation

    Args:
        clip: VideoClip
        intensity: Saturation level (0 = grayscale, 1.0 = original, 2.0 = very saturated)
    """
    def saturation_transform(image):
        # Convert to float
        img = image.astype(np.float32)

        # Calculate grayscale
        gray = np.dot(img[..., :3], [0.299, 0.587, 0.114])
        gray = np.stack([gray] * 3, axis=-1)

        # Mix grayscale and color based on intensity
        result = gray + intensity * (img - gray)

        # Clip and convert back
        return np.clip(result, 0, 255).astype(np.uint8)

    return clip.fl_image(saturation_transform)


def adjust_hue(clip, shift: float = 0.0):
    """
    Shift video hue

    Args:
        clip: VideoClip
        shift: Hue shift in degrees (-180 to 180)
    """
    def hue_transform(image):
        from colorsys import rgb_to_hsv, hsv_to_rgb

        # Normalize shift to 0-1 range
        shift_normalized = shift / 360.0

        # Process each pixel
        img = image.astype(np.float32) / 255.0
        h, w, _ = img.shape

        result = np.zeros_like(img)
        for i in range(h):
            for j in range(w):
                r, g, b = img[i, j]
                h_val, s, v = rgb_to_hsv(r, g, b)

                # Shift hue
                h_val = (h_val + shift_normalized) % 1.0

                # Convert back to RGB
                r, g, b = hsv_to_rgb(h_val, s, v)
                result[i, j] = [r, g, b]

        return (result * 255).astype(np.uint8)

    return clip.fl_image(hue_transform)


def grayscale(clip):
    """Convert video to grayscale"""
    return blackwhite(clip)


def sepia(clip):
    """Apply sepia tone filter"""
    def sepia_transform(image):
        img = image.astype(np.float32)

        # Sepia matrix
        sepia_matrix = np.array([
            [0.393, 0.769, 0.189],
            [0.349, 0.686, 0.168],
            [0.272, 0.534, 0.131]
        ])

        # Apply sepia
        result = img.dot(sepia_matrix.T)

        return np.clip(result, 0, 255).astype(np.uint8)

    return clip.fl_image(sepia_transform)


def invert_colors(clip):
    """Invert video colors (negative)"""
    def invert_transform(image):
        return 255 - image

    return clip.fl_image(invert_transform)


# ==================== BLUR & SHARPNESS ====================

def apply_blur(clip, intensity: int = 5):
    """
    Apply Gaussian blur

    Args:
        clip: VideoClip
        intensity: Blur radius (1-20)
    """
    try:
        from scipy.ndimage import gaussian_filter
    except ImportError:
        logger.warning("scipy not installed. Blur filter unavailable.")
        return clip

    def blur_transform(image):
        # Apply Gaussian blur to each channel
        blurred = np.zeros_like(image)
        for i in range(image.shape[2]):
            blurred[:, :, i] = gaussian_filter(image[:, :, i], sigma=intensity)
        return blurred.astype(np.uint8)

    return clip.fl_image(blur_transform)


def sharpen(clip, intensity: float = 1.0):
    """
    Sharpen video

    Args:
        clip: VideoClip
        intensity: Sharpness level (0.5 = slight, 2.0 = strong)
    """
    try:
        from scipy.ndimage import gaussian_filter
    except ImportError:
        logger.warning("scipy not installed. Sharpen filter unavailable.")
        return clip

    def sharpen_transform(image):
        # Create blurred version
        blurred = np.zeros_like(image, dtype=np.float32)
        for i in range(image.shape[2]):
            blurred[:, :, i] = gaussian_filter(image[:, :, i].astype(np.float32), sigma=1)

        # Unsharp mask: original + intensity * (original - blurred)
        sharpened = image.astype(np.float32) + intensity * (image.astype(np.float32) - blurred)

        return np.clip(sharpened, 0, 255).astype(np.uint8)

    return clip.fl_image(sharpen_transform)


# ==================== ARTISTIC FILTERS ====================

def posterize(clip, levels: int = 4):
    """
    Posterize video (reduce color levels)

    Args:
        clip: VideoClip
        levels: Number of color levels per channel (2-16)
    """
    def posterize_transform(image):
        # Reduce color depth
        factor = 256 / levels
        posterized = (image // factor) * factor
        return posterized.astype(np.uint8)

    return clip.fl_image(posterize_transform)


def edge_detect(clip, threshold: int = 50):
    """
    Edge detection filter

    Args:
        clip: VideoClip
        threshold: Edge detection threshold
    """
    try:
        from scipy.ndimage import sobel
    except ImportError:
        logger.warning("scipy not installed. Edge detect unavailable.")
        return clip

    def edge_transform(image):
        # Convert to grayscale
        gray = np.dot(image[..., :3], [0.299, 0.587, 0.114])

        # Sobel edge detection
        sx = sobel(gray, axis=0)
        sy = sobel(gray, axis=1)
        edges = np.hypot(sx, sy)

        # Normalize and threshold
        edges = (edges / edges.max() * 255)
        edges[edges < threshold] = 0

        # Convert back to RGB
        result = np.stack([edges] * 3, axis=-1)

        return result.astype(np.uint8)

    return clip.fl_image(edge_transform)


def pixelate(clip, pixel_size: int = 10):
    """
    Pixelate video (mosaic effect)

    Args:
        clip: VideoClip
        pixel_size: Size of pixels (larger = more pixelated)
    """
    def pixelate_transform(image):
        h, w = image.shape[:2]

        # Downscale
        small_h = max(1, h // pixel_size)
        small_w = max(1, w // pixel_size)

        try:
            from PIL import Image
            img = Image.fromarray(image)

            # Resize down then up
            img = img.resize((small_w, small_h), Image.NEAREST)
            img = img.resize((w, h), Image.NEAREST)

            return np.array(img)
        except ImportError:
            # Fallback without PIL
            return image

    return clip.fl_image(pixelate_transform)


def vignette(clip, intensity: float = 0.5):
    """
    Add vignette effect (darkened corners)

    Args:
        clip: VideoClip
        intensity: Vignette strength (0.0 = none, 1.0 = strong)
    """
    def vignette_transform(image):
        h, w = image.shape[:2]

        # Create radial gradient
        center_y, center_x = h // 2, w // 2
        Y, X = np.ogrid[:h, :w]

        # Calculate distance from center
        distance = np.sqrt((X - center_x) ** 2 + (Y - center_y) ** 2)
        max_distance = np.sqrt(center_x ** 2 + center_y ** 2)

        # Normalize distance
        distance = distance / max_distance

        # Create vignette mask
        vignette_mask = 1 - (distance * intensity)
        vignette_mask = np.clip(vignette_mask, 0, 1)

        # Apply to image
        result = image.astype(np.float32)
        for i in range(image.shape[2]):
            result[:, :, i] *= vignette_mask

        return result.astype(np.uint8)

    return clip.fl_image(vignette_transform)


# ==================== COLOR GRADING ====================

def warm_filter(clip, intensity: float = 0.3):
    """
    Apply warm color tone (orange/yellow tint)

    Args:
        clip: VideoClip
        intensity: Warmth intensity (0.0 to 1.0)
    """
    def warm_transform(image):
        img = image.astype(np.float32)

        # Add warmth (increase red, slightly increase green)
        img[:, :, 0] += intensity * 50  # Red
        img[:, :, 1] += intensity * 25  # Green

        return np.clip(img, 0, 255).astype(np.uint8)

    return clip.fl_image(warm_transform)


def cool_filter(clip, intensity: float = 0.3):
    """
    Apply cool color tone (blue tint)

    Args:
        clip: VideoClip
        intensity: Coolness intensity (0.0 to 1.0)
    """
    def cool_transform(image):
        img = image.astype(np.float32)

        # Add coolness (increase blue, slightly decrease red)
        img[:, :, 2] += intensity * 50  # Blue
        img[:, :, 0] -= intensity * 15  # Red

        return np.clip(img, 0, 255).astype(np.uint8)

    return clip.fl_image(cool_transform)


def vintage_filter(clip):
    """
    Apply vintage film look
    """
    # Combine multiple effects
    result = clip

    # Desaturate slightly
    result = adjust_saturation(result, 0.7)

    # Add warm tone
    result = warm_filter(result, 0.2)

    # Reduce contrast slightly
    result = adjust_contrast(result, 0.9)

    # Add vignette
    result = vignette(result, 0.3)

    return result


def cinematic_filter(clip):
    """
    Apply cinematic color grading
    """
    # High contrast, desaturated, cool tones
    result = clip

    # Increase contrast
    result = adjust_contrast(result, 1.3)

    # Slight desaturation
    result = adjust_saturation(result, 0.85)

    # Cool tones
    result = cool_filter(result, 0.15)

    return result


# ==================== MAIN FILTER FUNCTION ====================

def apply_custom_filter(clip, filter_name: str, **kwargs):
    """
    Apply filter by name

    Available filters:
        - brightness (intensity=1.0)
        - contrast (intensity=1.0)
        - saturation (intensity=1.0)
        - hue (shift=0.0)
        - grayscale
        - sepia
        - invert
        - blur (intensity=5)
        - sharpen (intensity=1.0)
        - posterize (levels=4)
        - edge_detect (threshold=50)
        - pixelate (pixel_size=10)
        - vignette (intensity=0.5)
        - warm (intensity=0.3)
        - cool (intensity=0.3)
        - vintage
        - cinematic
    """
    filters = {
        'brightness': adjust_brightness,
        'contrast': adjust_contrast,
        'saturation': adjust_saturation,
        'hue': adjust_hue,
        'grayscale': grayscale,
        'sepia': sepia,
        'invert': invert_colors,
        'blur': apply_blur,
        'sharpen': sharpen,
        'posterize': posterize,
        'edge_detect': edge_detect,
        'pixelate': pixelate,
        'vignette': vignette,
        'warm': warm_filter,
        'cool': cool_filter,
        'vintage': vintage_filter,
        'cinematic': cinematic_filter
    }

    if filter_name not in filters:
        available = ', '.join(filters.keys())
        raise ValueError(f"Unknown filter: {filter_name}. Available: {available}")

    filter_func = filters[filter_name]

    # Check if filter accepts kwargs
    import inspect
    sig = inspect.signature(filter_func)

    if len(sig.parameters) > 1:  # Has parameters beyond 'clip'
        return filter_func(clip, **kwargs)
    else:
        return filter_func(clip)


# ==================== PRESET COMBINATIONS ====================

class FilterPreset:
    """Predefined filter combinations"""

    @staticmethod
    def instagram_valencia(clip):
        """Instagram Valencia filter"""
        result = adjust_brightness(clip, 1.1)
        result = adjust_saturation(result, 1.2)
        result = warm_filter(result, 0.2)
        return result

    @staticmethod
    def instagram_nashville(clip):
        """Instagram Nashville filter"""
        result = adjust_brightness(clip, 1.05)
        result = adjust_contrast(result, 1.2)
        result = warm_filter(result, 0.3)
        return result

    @staticmethod
    def instagram_lark(clip):
        """Instagram Lark filter"""
        result = adjust_brightness(clip, 1.1)
        result = adjust_saturation(result, 0.9)
        result = cool_filter(result, 0.1)
        return result

    @staticmethod
    def tiktok_vivid(clip):
        """TikTok Vivid filter"""
        result = adjust_saturation(clip, 1.4)
        result = adjust_contrast(result, 1.2)
        return result

    @staticmethod
    def youtube_cinematic(clip):
        """YouTube Cinematic look"""
        return cinematic_filter(clip)


def apply_preset(clip, preset_name: str):
    """
    Apply filter preset by name

    Available presets:
        - instagram_valencia
        - instagram_nashville
        - instagram_lark
        - tiktok_vivid
        - youtube_cinematic
    """
    presets = {
        'instagram_valencia': FilterPreset.instagram_valencia,
        'instagram_nashville': FilterPreset.instagram_nashville,
        'instagram_lark': FilterPreset.instagram_lark,
        'tiktok_vivid': FilterPreset.tiktok_vivid,
        'youtube_cinematic': FilterPreset.youtube_cinematic
    }

    if preset_name not in presets:
        available = ', '.join(presets.keys())
        raise ValueError(f"Unknown preset: {preset_name}. Available: {available}")

    return presets[preset_name](clip)
