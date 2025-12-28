"""
Title Generator Module
Auto-generate engaging video titles using AI (Groq API)

Enhanced with:
- Multilingual support (English, Portuguese, French, Spanish, Urdu, Hindi, Arabic)
- Audio transcription and language detection (Whisper)
- Visual content analysis (CLIP)
- OCR text extraction (Tesseract)
- Facebook/TikTok optimization
"""

from .dialog import TitleGeneratorDialog
from .api_manager import APIKeyManager
from .enhanced_generator import EnhancedTitleGenerator
from .audio_analyzer import AudioAnalyzer
from .visual_analyzer import VisualAnalyzer
from .content_aggregator import ContentAggregator
from .multilingual_templates import MultilingualTemplates

__all__ = [
    'TitleGeneratorDialog',
    'APIKeyManager',
    'EnhancedTitleGenerator',
    'AudioAnalyzer',
    'VisualAnalyzer',
    'ContentAggregator',
    'MultilingualTemplates'
]
