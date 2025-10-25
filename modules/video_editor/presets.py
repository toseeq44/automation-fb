"""
modules/video_editor/presets.py
Platform-Specific Video Presets
Optimized settings for TikTok, Instagram, YouTube, Facebook, Twitter
"""

from typing import Dict, Any, List
from dataclasses import dataclass
from modules.logging.logger import get_logger

logger = get_logger(__name__)


@dataclass
class VideoSpec:
    """Video specification"""
    name: str
    platform: str
    aspect_ratio: str
    width: int
    height: int
    min_duration: float = 0
    max_duration: float = float('inf')
    fps: int = 30
    bitrate: str = '5000k'
    audio_bitrate: str = '192k'
    codec: str = 'libx264'
    audio_codec: str = 'aac'
    description: str = ''


# ==================== PLATFORM PRESETS ====================

class PlatformPresets:
    """Predefined platform specifications"""

    # TikTok
    TIKTOK_VERTICAL = VideoSpec(
        name="TikTok Vertical",
        platform="TikTok",
        aspect_ratio="9:16",
        width=1080,
        height=1920,
        min_duration=0,
        max_duration=600,  # 10 minutes max
        fps=30,
        bitrate='5000k',
        description="TikTok vertical video (recommended)"
    )

    TIKTOK_HORIZONTAL = VideoSpec(
        name="TikTok Horizontal",
        platform="TikTok",
        aspect_ratio="16:9",
        width=1920,
        height=1080,
        max_duration=600,
        fps=30,
        bitrate='5000k',
        description="TikTok horizontal video"
    )

    TIKTOK_SQUARE = VideoSpec(
        name="TikTok Square",
        platform="TikTok",
        aspect_ratio="1:1",
        width=1080,
        height=1080,
        max_duration=600,
        fps=30,
        bitrate='4000k',
        description="TikTok square video"
    )

    # Instagram
    INSTAGRAM_REELS = VideoSpec(
        name="Instagram Reels",
        platform="Instagram",
        aspect_ratio="9:16",
        width=1080,
        height=1920,
        min_duration=0,
        max_duration=90,  # 90 seconds max
        fps=30,
        bitrate='5000k',
        description="Instagram Reels (vertical)"
    )

    INSTAGRAM_STORY = VideoSpec(
        name="Instagram Story",
        platform="Instagram",
        aspect_ratio="9:16",
        width=1080,
        height=1920,
        min_duration=0,
        max_duration=60,
        fps=30,
        bitrate='4000k',
        description="Instagram Story"
    )

    INSTAGRAM_POST = VideoSpec(
        name="Instagram Post",
        platform="Instagram",
        aspect_ratio="1:1",
        width=1080,
        height=1080,
        min_duration=3,
        max_duration=60,
        fps=30,
        bitrate='3500k',
        description="Instagram Feed Post (square)"
    )

    INSTAGRAM_POST_PORTRAIT = VideoSpec(
        name="Instagram Post Portrait",
        platform="Instagram",
        aspect_ratio="4:5",
        width=1080,
        height=1350,
        min_duration=3,
        max_duration=60,
        fps=30,
        bitrate='4000k',
        description="Instagram Feed Post (portrait)"
    )

    INSTAGRAM_POST_LANDSCAPE = VideoSpec(
        name="Instagram Post Landscape",
        platform="Instagram",
        aspect_ratio="16:9",
        width=1920,
        height=1080,
        min_duration=3,
        max_duration=60,
        fps=30,
        bitrate='5000k',
        description="Instagram Feed Post (landscape)"
    )

    INSTAGRAM_IGTV = VideoSpec(
        name="Instagram IGTV",
        platform="Instagram",
        aspect_ratio="9:16",
        width=1080,
        height=1920,
        min_duration=60,
        max_duration=3600,  # 1 hour
        fps=30,
        bitrate='6000k',
        description="Instagram IGTV (long-form vertical)"
    )

    # YouTube
    YOUTUBE_STANDARD = VideoSpec(
        name="YouTube Standard (1080p)",
        platform="YouTube",
        aspect_ratio="16:9",
        width=1920,
        height=1080,
        fps=30,
        bitrate='8000k',
        description="YouTube 1080p HD"
    )

    YOUTUBE_4K = VideoSpec(
        name="YouTube 4K",
        platform="YouTube",
        aspect_ratio="16:9",
        width=3840,
        height=2160,
        fps=30,
        bitrate='35000k',
        description="YouTube 4K UHD"
    )

    YOUTUBE_SHORTS = VideoSpec(
        name="YouTube Shorts",
        platform="YouTube",
        aspect_ratio="9:16",
        width=1080,
        height=1920,
        min_duration=0,
        max_duration=60,
        fps=30,
        bitrate='5000k',
        description="YouTube Shorts (vertical)"
    )

    YOUTUBE_720P = VideoSpec(
        name="YouTube 720p",
        platform="YouTube",
        aspect_ratio="16:9",
        width=1280,
        height=720,
        fps=30,
        bitrate='5000k',
        description="YouTube 720p HD"
    )

    # Facebook
    FACEBOOK_FEED = VideoSpec(
        name="Facebook Feed",
        platform="Facebook",
        aspect_ratio="16:9",
        width=1920,
        height=1080,
        fps=30,
        bitrate='6000k',
        description="Facebook News Feed"
    )

    FACEBOOK_STORY = VideoSpec(
        name="Facebook Story",
        platform="Facebook",
        aspect_ratio="9:16",
        width=1080,
        height=1920,
        max_duration=120,
        fps=30,
        bitrate='5000k',
        description="Facebook Stories"
    )

    FACEBOOK_SQUARE = VideoSpec(
        name="Facebook Square",
        platform="Facebook",
        aspect_ratio="1:1",
        width=1080,
        height=1080,
        fps=30,
        bitrate='4000k',
        description="Facebook Square Video"
    )

    # Twitter / X
    TWITTER_LANDSCAPE = VideoSpec(
        name="Twitter Landscape",
        platform="Twitter",
        aspect_ratio="16:9",
        width=1920,
        height=1080,
        min_duration=0.5,
        max_duration=140,
        fps=30,
        bitrate='6000k',
        description="Twitter/X Landscape"
    )

    TWITTER_SQUARE = VideoSpec(
        name="Twitter Square",
        platform="Twitter",
        aspect_ratio="1:1",
        width=1080,
        height=1080,
        max_duration=140,
        fps=30,
        bitrate='5000k',
        description="Twitter/X Square"
    )

    TWITTER_PORTRAIT = VideoSpec(
        name="Twitter Portrait",
        platform="Twitter",
        aspect_ratio="9:16",
        width=1080,
        height=1920,
        max_duration=140,
        fps=30,
        bitrate='5000k',
        description="Twitter/X Portrait"
    )

    # LinkedIn
    LINKEDIN_FEED = VideoSpec(
        name="LinkedIn Feed",
        platform="LinkedIn",
        aspect_ratio="16:9",
        width=1920,
        height=1080,
        min_duration=3,
        max_duration=600,
        fps=30,
        bitrate='5000k',
        description="LinkedIn Feed Video"
    )

    LINKEDIN_SQUARE = VideoSpec(
        name="LinkedIn Square",
        platform="LinkedIn",
        aspect_ratio="1:1",
        width=1080,
        height=1080,
        max_duration=600,
        fps=30,
        bitrate='4000k',
        description="LinkedIn Square Video"
    )

    # Pinterest
    PINTEREST_STANDARD = VideoSpec(
        name="Pinterest Standard",
        platform="Pinterest",
        aspect_ratio="2:3",
        width=1000,
        height=1500,
        min_duration=4,
        max_duration=900,  # 15 minutes
        fps=30,
        bitrate='5000k',
        description="Pinterest Standard Pin"
    )

    PINTEREST_SQUARE = VideoSpec(
        name="Pinterest Square",
        platform="Pinterest",
        aspect_ratio="1:1",
        width=1080,
        height=1080,
        max_duration=900,
        fps=30,
        bitrate='4000k',
        description="Pinterest Square Pin"
    )

    # Snapchat
    SNAPCHAT_STORY = VideoSpec(
        name="Snapchat Story",
        platform="Snapchat",
        aspect_ratio="9:16",
        width=1080,
        height=1920,
        max_duration=60,
        fps=30,
        bitrate='5000k',
        description="Snapchat Story"
    )

    @classmethod
    def get_all_presets(cls) -> Dict[str, VideoSpec]:
        """Get all available presets"""
        presets = {}
        for attr_name in dir(cls):
            attr = getattr(cls, attr_name)
            if isinstance(attr, VideoSpec):
                presets[attr_name.lower()] = attr
        return presets

    @classmethod
    def get_by_platform(cls, platform: str) -> List[VideoSpec]:
        """Get all presets for a specific platform"""
        all_presets = cls.get_all_presets()
        return [spec for spec in all_presets.values() if spec.platform.lower() == platform.lower()]

    @classmethod
    def get_preset(cls, preset_name: str) -> VideoSpec:
        """Get specific preset by name"""
        all_presets = cls.get_all_presets()
        preset_key = preset_name.lower()

        if preset_key in all_presets:
            return all_presets[preset_key]

        # Try searching by display name
        for spec in all_presets.values():
            if spec.name.lower() == preset_name.lower():
                return spec

        raise ValueError(f"Preset not found: {preset_name}")

    @classmethod
    def list_platforms(cls) -> List[str]:
        """List all available platforms"""
        all_presets = cls.get_all_presets()
        platforms = set(spec.platform for spec in all_presets.values())
        return sorted(list(platforms))

    @classmethod
    def print_all_presets(cls):
        """Print all presets in a readable format"""
        all_presets = cls.get_all_presets()
        platforms = cls.list_platforms()

        print("\n=== PLATFORM PRESETS ===\n")
        for platform in platforms:
            print(f"📱 {platform}:")
            platform_presets = cls.get_by_platform(platform)
            for spec in platform_presets:
                duration_info = ""
                if spec.max_duration != float('inf'):
                    duration_info = f" (max {spec.max_duration}s)"
                print(f"  • {spec.name}: {spec.width}x{spec.height} ({spec.aspect_ratio}){duration_info}")
            print()


# ==================== PRESET APPLICATION ====================

class PresetApplicator:
    """Apply platform presets to videos"""

    @staticmethod
    def apply_preset(video_editor, preset: VideoSpec, auto_crop: bool = True):
        """
        Apply preset to video editor

        Args:
            video_editor: VideoEditor instance
            preset: VideoSpec preset to apply
            auto_crop: Auto-crop to fit aspect ratio
        """
        logger.info(f"Applying preset: {preset.name}")

        # Get current video info
        info = video_editor.get_info()
        current_width = info['width']
        current_height = info['height']

        # Resize and crop to match preset
        if auto_crop:
            # Crop to aspect ratio first
            video_editor.crop(preset=preset.aspect_ratio)

        # Resize to target dimensions
        video_editor.resize_video(width=preset.width, height=preset.height)

        # Validate duration
        if info['duration'] < preset.min_duration:
            logger.warning(f"Video duration ({info['duration']}s) is less than minimum ({preset.min_duration}s)")

        if info['duration'] > preset.max_duration:
            logger.warning(f"Video duration ({info['duration']}s) exceeds maximum ({preset.max_duration}s)")
            logger.info(f"Trimming to {preset.max_duration}s")
            video_editor.trim(0, preset.max_duration)

        logger.info(f"Preset applied: {preset.name} ({preset.width}x{preset.height})")
        return video_editor

    @staticmethod
    def get_export_settings(preset: VideoSpec) -> Dict[str, Any]:
        """
        Get export settings for a preset

        Args:
            preset: VideoSpec preset

        Returns:
            Dictionary of export settings
        """
        return {
            'fps': preset.fps,
            'codec': preset.codec,
            'audio_codec': preset.audio_codec,
            'bitrate': preset.bitrate,
            'preset': 'medium',  # FFmpeg preset
            'threads': 4
        }

    @staticmethod
    def optimize_for_platform(video_editor, platform: str, format_type: str = 'standard'):
        """
        Optimize video for specific platform

        Args:
            video_editor: VideoEditor instance
            platform: Platform name (tiktok, instagram, youtube, etc.)
            format_type: Format type (vertical, horizontal, square, reels, shorts, etc.)
        """
        platform = platform.lower()

        # Map platform + format to preset
        preset_map = {
            'tiktok': {
                'vertical': PlatformPresets.TIKTOK_VERTICAL,
                'horizontal': PlatformPresets.TIKTOK_HORIZONTAL,
                'square': PlatformPresets.TIKTOK_SQUARE,
                'standard': PlatformPresets.TIKTOK_VERTICAL
            },
            'instagram': {
                'reels': PlatformPresets.INSTAGRAM_REELS,
                'story': PlatformPresets.INSTAGRAM_STORY,
                'post': PlatformPresets.INSTAGRAM_POST,
                'square': PlatformPresets.INSTAGRAM_POST,
                'portrait': PlatformPresets.INSTAGRAM_POST_PORTRAIT,
                'landscape': PlatformPresets.INSTAGRAM_POST_LANDSCAPE,
                'igtv': PlatformPresets.INSTAGRAM_IGTV,
                'standard': PlatformPresets.INSTAGRAM_REELS
            },
            'youtube': {
                'shorts': PlatformPresets.YOUTUBE_SHORTS,
                '1080p': PlatformPresets.YOUTUBE_STANDARD,
                '720p': PlatformPresets.YOUTUBE_720P,
                '4k': PlatformPresets.YOUTUBE_4K,
                'standard': PlatformPresets.YOUTUBE_STANDARD,
                'vertical': PlatformPresets.YOUTUBE_SHORTS
            },
            'facebook': {
                'feed': PlatformPresets.FACEBOOK_FEED,
                'story': PlatformPresets.FACEBOOK_STORY,
                'square': PlatformPresets.FACEBOOK_SQUARE,
                'standard': PlatformPresets.FACEBOOK_FEED
            },
            'twitter': {
                'landscape': PlatformPresets.TWITTER_LANDSCAPE,
                'square': PlatformPresets.TWITTER_SQUARE,
                'portrait': PlatformPresets.TWITTER_PORTRAIT,
                'standard': PlatformPresets.TWITTER_LANDSCAPE
            },
            'x': {  # Twitter/X alias
                'landscape': PlatformPresets.TWITTER_LANDSCAPE,
                'square': PlatformPresets.TWITTER_SQUARE,
                'portrait': PlatformPresets.TWITTER_PORTRAIT,
                'standard': PlatformPresets.TWITTER_LANDSCAPE
            },
            'linkedin': {
                'feed': PlatformPresets.LINKEDIN_FEED,
                'square': PlatformPresets.LINKEDIN_SQUARE,
                'standard': PlatformPresets.LINKEDIN_FEED
            },
            'pinterest': {
                'standard': PlatformPresets.PINTEREST_STANDARD,
                'square': PlatformPresets.PINTEREST_SQUARE
            },
            'snapchat': {
                'story': PlatformPresets.SNAPCHAT_STORY,
                'standard': PlatformPresets.SNAPCHAT_STORY
            }
        }

        if platform not in preset_map:
            raise ValueError(f"Unknown platform: {platform}. Available: {list(preset_map.keys())}")

        if format_type not in preset_map[platform]:
            available = list(preset_map[platform].keys())
            raise ValueError(f"Unknown format type '{format_type}' for {platform}. Available: {available}")

        preset = preset_map[platform][format_type]
        return PresetApplicator.apply_preset(video_editor, preset)


# ==================== BATCH CONVERSION ====================

def convert_for_all_platforms(input_video: str, output_dir: str,
                              platforms: List[str] = None):
    """
    Convert video to multiple platform formats

    Args:
        input_video: Input video path
        output_dir: Output directory
        platforms: List of platforms (None = all major platforms)
    """
    import os
    from modules.video_editor.core import VideoEditor

    if platforms is None:
        platforms = ['tiktok', 'instagram_reels', 'youtube_shorts', 'facebook']

    os.makedirs(output_dir, exist_ok=True)

    results = []

    for platform_spec in platforms:
        try:
            # Parse platform spec (e.g., "instagram_reels" -> platform="instagram", type="reels")
            parts = platform_spec.split('_', 1)
            platform = parts[0]
            format_type = parts[1] if len(parts) > 1 else 'standard'

            logger.info(f"Converting for {platform} ({format_type})...")

            # Create editor
            editor = VideoEditor(input_video)

            # Optimize for platform
            PresetApplicator.optimize_for_platform(editor, platform, format_type)

            # Export
            output_filename = f"{os.path.splitext(os.path.basename(input_video))[0]}_{platform_spec}.mp4"
            output_path = os.path.join(output_dir, output_filename)

            preset = PlatformPresets.get_preset(f"{platform}_{format_type}")
            export_settings = PresetApplicator.get_export_settings(preset)

            editor.export(output_path, **export_settings)

            results.append({
                'platform': platform_spec,
                'output': output_path,
                'status': 'success'
            })

            editor.cleanup()

        except Exception as e:
            logger.error(f"Failed to convert for {platform_spec}: {e}")
            results.append({
                'platform': platform_spec,
                'output': None,
                'status': 'failed',
                'error': str(e)
            })

    return results


# ==================== QUICK PRESETS ====================

QUICK_PRESETS = {
    # Aspect ratios only
    'vertical': '9:16',
    'horizontal': '16:9',
    'square': '1:1',
    'portrait': '4:5',
    'cinematic': '21:9',

    # Common resolutions
    '1080p': (1920, 1080),
    '720p': (1280, 720),
    '4k': (3840, 2160),
    '480p': (854, 480),

    # Platform shortcuts
    'tiktok': PlatformPresets.TIKTOK_VERTICAL,
    'reels': PlatformPresets.INSTAGRAM_REELS,
    'shorts': PlatformPresets.YOUTUBE_SHORTS,
    'story': PlatformPresets.INSTAGRAM_STORY,
}


def get_quick_preset(name: str):
    """Get quick preset by name"""
    if name in QUICK_PRESETS:
        return QUICK_PRESETS[name]
    else:
        raise ValueError(f"Unknown quick preset: {name}")
