"""
Title Generator Module
Auto-generate engaging video titles using AI (Groq API)

SMART MODE DETECTION:
- Automatically detects if AI models are available
- Enhanced Mode: Full AI features (Whisper + CLIP + Multilingual)
- Basic Mode: Standard title generation (works without models)

AI Models can be placed in:
- C:\\AI_Models\\
- Desktop\\AI_Models\\
- App directory\\models\\
"""

from modules.logging.logger import get_logger

# Import core components (NOT dialog yet - to avoid circular import)
from .api_manager import APIKeyManager
from .generator import TitleGenerator  # Basic generator (no models needed)
from .model_finder import ModelFinder, get_model_finder

logger = get_logger(__name__)

# Initialize model finder
model_finder = get_model_finder()
models_available = model_finder.find_models()

# Try to import enhanced features (requires models)
ENHANCED_MODE = False
EnhancedTitleGenerator = None
AudioAnalyzer = None
VisualAnalyzer = None
ContentAggregator = None
MultilingualTemplates = None

try:
    # Check if models are available
    if models_available.get('whisper') or models_available.get('clip'):
        # Try importing enhanced components
        from .enhanced_generator import EnhancedTitleGenerator
        from .audio_analyzer import AudioAnalyzer
        from .visual_analyzer import VisualAnalyzer
        from .content_aggregator import ContentAggregator
        from .multilingual_templates import MultilingualTemplates

        ENHANCED_MODE = True
        logger.info("=" * 60)
        logger.info("🚀 ENHANCED MODE ENABLED")
        logger.info("=" * 60)
        logger.info(f"📂 Models location: {models_available.get('base_path')}")
        if models_available.get('whisper'):
            logger.info("   ✅ Whisper (Audio analysis + Language detection)")
        if models_available.get('clip'):
            logger.info("   ✅ CLIP (Visual object/scene detection)")
        logger.info("   ✅ Multilingual support (7+ languages)")
        logger.info("   ✅ Platform optimization (Facebook/TikTok/Instagram)")
        logger.info("=" * 60)

    else:
        raise ImportError("Models not found")

except ImportError as e:
    logger.info("=" * 60)
    logger.info("⚡ BASIC MODE ACTIVE")
    logger.info("=" * 60)
    logger.info("ℹ️  AI models not found - using basic title generation")
    logger.info("")
    logger.info("💡 To enable AI-powered features:")
    logger.info("   1. Download Whisper + CLIP models")
    logger.info("   2. Place in: C:\\AI_Models\\ or Desktop\\AI_Models\\")
    logger.info("   3. Restart app → Auto-enables enhanced mode!")
    logger.info("")
    logger.info("📥 Download instructions available in title generator dialog")
    logger.info("=" * 60)

except Exception as e:
    logger.warning(f"⚠️ Failed to load enhanced features: {e}")
    logger.info("Running in BASIC MODE")


# Export based on available features
__all__ = [
    'TitleGeneratorDialog',
    'APIKeyManager',
    'TitleGenerator',
    'ModelFinder',
    'get_model_finder',
    'get_generator',
    'show_model_instructions',
    'ENHANCED_MODE',
    'models_available'
]

if ENHANCED_MODE:
    __all__.extend([
        'EnhancedTitleGenerator',
        'AudioAnalyzer',
        'VisualAnalyzer',
        'ContentAggregator',
        'MultilingualTemplates'
    ])


def get_generator(prefer_enhanced: bool = True):
    """
    Get appropriate title generator based on availability

    Args:
        prefer_enhanced: Use enhanced generator if available

    Returns:
        TitleGenerator or EnhancedTitleGenerator instance
    """
    if ENHANCED_MODE and prefer_enhanced and EnhancedTitleGenerator:
        logger.info("Using Enhanced Title Generator (AI-powered)")
        return EnhancedTitleGenerator(model_size='base')
    else:
        logger.info("Using Basic Title Generator")
        return TitleGenerator()


def show_model_instructions():
    """Display model download instructions"""
    print(model_finder.get_download_instructions())


# Import dialog AFTER defining ENHANCED_MODE, models_available, get_generator
# This prevents circular import since dialog.py imports from this module
from .dialog import TitleGeneratorDialog
