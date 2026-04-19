"""
Title Generator Module
Auto-generate engaging video titles using local or API-backed analysis.
"""

from modules.logging.logger import get_logger

from .api_manager import APIKeyManager
from .generator import TitleGenerator
from .model_finder import ModelFinder, get_model_finder

logger = get_logger(__name__)


ENHANCED_MODE = False
API_ENHANCED_MODE = False
models_available = {
    "whisper": False,
    "clip": False,
    "base_path": None,
    "install_method": None,
}

EnhancedTitleGenerator = None
AudioAnalyzer = None
VisualAnalyzer = None
ContentAggregator = None
MultilingualTemplates = None

APIEnhancedTitleGenerator = None
APIContentAnalyzer = None

_runtime_initialized = False


def _log_mode_banner(title: str, lines: list[str]) -> None:
    logger.info("=" * 60)
    logger.info(title)
    logger.info("=" * 60)
    for line in lines:
        logger.info(line)
    logger.info("=" * 60)


def initialize_runtime_features() -> dict:
    """
    Lazy runtime initialization.

    PyInstaller may import this package while building the EXE. We avoid model
    scans and optional heavy imports until the title generator is actually used.
    """
    global ENHANCED_MODE
    global API_ENHANCED_MODE
    global models_available
    global EnhancedTitleGenerator
    global AudioAnalyzer
    global VisualAnalyzer
    global ContentAggregator
    global MultilingualTemplates
    global APIEnhancedTitleGenerator
    global APIContentAnalyzer
    global _runtime_initialized

    if _runtime_initialized:
        return get_runtime_capabilities()

    local_model_finder = get_model_finder()
    models_available = local_model_finder.find_models()

    try:
        if models_available.get("whisper") or models_available.get("clip"):
            from .enhanced_generator import EnhancedTitleGenerator as _EnhancedTitleGenerator
            from .audio_analyzer import AudioAnalyzer as _AudioAnalyzer
            from .visual_analyzer import VisualAnalyzer as _VisualAnalyzer
            from .content_aggregator import ContentAggregator as _ContentAggregator
            from .multilingual_templates import MultilingualTemplates as _MultilingualTemplates

            EnhancedTitleGenerator = _EnhancedTitleGenerator
            AudioAnalyzer = _AudioAnalyzer
            VisualAnalyzer = _VisualAnalyzer
            ContentAggregator = _ContentAggregator
            MultilingualTemplates = _MultilingualTemplates
            ENHANCED_MODE = True

            lines = [f"Models location: {models_available.get('base_path')}"]
            if models_available.get("whisper"):
                lines.append("Whisper available")
            if models_available.get("clip"):
                lines.append("CLIP available")
            lines.append("Multilingual support available")
            _log_mode_banner("ENHANCED MODE ENABLED", lines)
    except ImportError:
        ENHANCED_MODE = False
    except Exception as exc:
        ENHANCED_MODE = False
        logger.warning(f"Failed to load enhanced features: {exc}")

    if not ENHANCED_MODE:
        _log_mode_banner(
            "BASIC MODE ACTIVE",
            [
                "AI models not found - using basic title generation",
                "To enable AI-powered features:",
                "1. Download Whisper + CLIP models",
                "2. Place them in C:\\AI_Models\\ or Desktop\\AI_Models\\",
                "3. Restart the app to auto-enable enhanced mode",
            ],
        )

    try:
        from .api_enhanced_generator import APIEnhancedTitleGenerator as _APIEnhancedTitleGenerator
        from .api_content_analyzer import APIContentAnalyzer as _APIContentAnalyzer
        from .multilingual_templates import MultilingualTemplates as _MultilingualTemplates

        import cv2  # noqa: F401
        import pytesseract  # noqa: F401

        APIEnhancedTitleGenerator = _APIEnhancedTitleGenerator
        APIContentAnalyzer = _APIContentAnalyzer
        MultilingualTemplates = _MultilingualTemplates
        API_ENHANCED_MODE = True

        _log_mode_banner(
            "API-ENHANCED MODE ENABLED",
            [
                "Python 3.14+ compatible",
                "Groq Vision API available",
                "Groq LLaMA title refinement available",
                "Lightweight OCR available",
                "No local PyTorch/Whisper dependency required",
            ],
        )
    except ImportError as exc:
        API_ENHANCED_MODE = False
        if not ENHANCED_MODE:
            logger.debug(f"API-enhanced mode not available: {exc}")
    except Exception as exc:
        API_ENHANCED_MODE = False
        logger.debug(f"Failed to load API-enhanced features: {exc}")

    _runtime_initialized = True
    return get_runtime_capabilities()


def get_runtime_capabilities() -> dict:
    if not _runtime_initialized:
        return initialize_runtime_features()

    return {
        "enhanced_mode": ENHANCED_MODE,
        "api_enhanced_mode": API_ENHANCED_MODE,
        "models_available": models_available,
    }


def get_generator(prefer_enhanced: bool = True):
    """
    Get appropriate title generator based on availability.

    Priority order:
    1. API-enhanced (no PyTorch dependency)
    2. Enhanced (PyTorch-based)
    3. Basic
    """
    initialize_runtime_features()

    if prefer_enhanced:
        if API_ENHANCED_MODE and APIEnhancedTitleGenerator:
            logger.info("Using API-enhanced title generator")

            groq_client = None
            try:
                api_manager = APIKeyManager()
                api_key = api_manager.get_api_key()

                if api_key:
                    from groq import Groq

                    groq_client = Groq(api_key=api_key)
                    logger.info("Groq API client initialized")
                else:
                    logger.warning("Groq API key not found - using fallback behavior")
            except Exception as exc:
                logger.warning(f"Failed to initialize Groq client: {exc}")

            return APIEnhancedTitleGenerator(groq_client=groq_client)

        if ENHANCED_MODE and EnhancedTitleGenerator:
            logger.info("Using enhanced title generator")
            return EnhancedTitleGenerator(model_size="base")

    logger.info("Using basic title generator")
    return TitleGenerator()


def show_model_instructions():
    """Display model download instructions."""
    print(get_model_finder().get_download_instructions())


__all__ = [
    "TitleGeneratorDialog",
    "APIKeyManager",
    "TitleGenerator",
    "ModelFinder",
    "get_model_finder",
    "get_generator",
    "get_runtime_capabilities",
    "initialize_runtime_features",
    "show_model_instructions",
    "ENHANCED_MODE",
    "API_ENHANCED_MODE",
    "models_available",
]


from .dialog import TitleGeneratorDialog
