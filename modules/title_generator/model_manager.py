"""
Model Manager for Local AI Models
Handles downloading and managing models in C:\TitleGenerator\models
"""

import os
import platform
from pathlib import Path
from typing import Dict, List, Optional
from modules.logging.logger import get_logger

logger = get_logger(__name__)


class ModelManager:
    """
    Manage local AI models for offline title generation
    For EXE distribution: models in C:\TitleGenerator\models
    """

    def __init__(self, models_dir: Optional[str] = None):
        """
        Initialize model manager

        Args:
            models_dir: Custom models directory (default: platform-specific)
        """
        self.models_dir = models_dir or self._get_default_models_dir()
        self.ensure_models_dir()

    def _get_default_models_dir(self) -> str:
        """
        Get models directory with priority search order:
        1. C:\AI_Models\ (Windows) or ~/AI_Models/ (Linux/Mac)
        2. Desktop\AI_Models\
        3. ~/.cache/ (automatic downloads)
        """
        import platform

        # Try multiple locations in order
        possible_locations = []

        system = platform.system()

        if system == 'Windows':
            # Windows paths
            possible_locations = [
                r"C:\AI_Models",                                    # Priority 1
                os.path.join(os.path.expanduser("~"), "Desktop", "AI_Models"),  # Priority 2
                os.path.join(os.path.expanduser("~"), "AI_Models"),  # Priority 3
            ]
        else:  # Linux/Mac
            # Unix paths
            home = os.path.expanduser("~")
            possible_locations = [
                os.path.join(home, "AI_Models"),                    # Priority 1
                os.path.join(home, "Desktop", "AI_Models"),         # Priority 2
                os.path.join(home, ".cache", "ai_models"),          # Priority 3
            ]

        # Check which directory exists and has models
        for location in possible_locations:
            if os.path.exists(location):
                # Check if it has any model files
                if any(os.listdir(location)) if os.path.isdir(location) else False:
                    logger.info(f"📁 Found AI_Models at: {location}")
                    return location

        # If none exist, return first priority (will be created)
        return possible_locations[0]

    def ensure_models_dir(self):
        """Create models directory if it doesn't exist"""
        try:
            os.makedirs(self.models_dir, exist_ok=True)
            logger.info(f"📁 Models directory: {self.models_dir}")
        except Exception as e:
            logger.warning(f"⚠️  Could not create models directory: {e}")

    def get_model_info(self) -> Dict:
        """
        Get information about available models

        Returns:
            Dict with model availability and sizes
        """
        models = {
            'yolo': {
                'filename': 'yolov8n.pt',
                'size_mb': 6,
                'required': False,
                'description': 'YOLO object detection (lightweight)',
                'available': False
            },
            'blip': {
                'filename': 'blip-image-captioning-base',
                'size_mb': 500,
                'required': False,
                'description': 'BLIP image captioning (high accuracy)',
                'available': False
            },
            'whisper': {
                'filename': 'whisper-base.pt',
                'size_mb': 150,
                'required': False,
                'description': 'Whisper speech recognition (offline)',
                'available': False
            }
        }

        # Check which models are available
        for model_name, info in models.items():
            model_path = os.path.join(self.models_dir, info['filename'])
            if os.path.exists(model_path):
                info['available'] = True
                info['path'] = model_path

        return models

    def check_models_status(self) -> Dict:
        """
        Check which models are installed and available

        Returns:
            Status dict with counts and details
        """
        models = self.get_model_info()

        total = len(models)
        available = sum(1 for m in models.values() if m['available'])
        missing = total - available

        status = {
            'total': total,
            'available': available,
            'missing': missing,
            'models': models,
            'models_dir': self.models_dir
        }

        return status

    def print_models_status(self):
        """Print models status to console"""
        status = self.check_models_status()

        logger.info("=" * 60)
        logger.info("📦 LOCAL MODELS STATUS")
        logger.info("=" * 60)
        logger.info(f"📁 Directory: {status['models_dir']}")
        logger.info(f"✅ Available: {status['available']}/{status['total']}")
        logger.info("")

        for name, info in status['models'].items():
            if info['available']:
                logger.info(f"   ✅ {name.upper()}: {info['description']}")
                logger.info(f"      Path: {info.get('path', 'N/A')}")
            else:
                logger.info(f"   ❌ {name.upper()}: {info['description']}")
                logger.info(f"      Size: {info['size_mb']}MB")
                logger.info(f"      Install: Auto-download on first use")

        logger.info("=" * 60)

        if status['missing'] > 0:
            logger.info("")
            logger.info("💡 TIP: Models will auto-download on first use")
            logger.info("   Or manually download to: " + status['models_dir'])
            logger.info("")

    def get_download_instructions(self) -> str:
        """
        Get download instructions for missing models

        Returns:
            Formatted string with download instructions
        """
        status = self.check_models_status()

        if status['missing'] == 0:
            return "✅ All models are available!"

        instructions = f"""
📥 DOWNLOAD INSTRUCTIONS FOR OFFLINE MODELS
{'=' * 60}

Models Directory: {self.models_dir}

Missing Models ({status['missing']}/{status['total']}):

"""

        for name, info in status['models'].items():
            if not info['available']:
                instructions += f"""
{name.upper()}:
   Description: {info['description']}
   Size: {info['size_mb']}MB
   Auto-download: Will download automatically on first use
   Manual: Create folder and model will be cached there

"""

        instructions += f"""
{'=' * 60}

OPTIONS:

1. AUTO-DOWNLOAD (Recommended):
   - Just run the app
   - Models download automatically when needed
   - Takes 1-2 minutes on first use

2. MANUAL DOWNLOAD (For offline use):
   - Create folder: {self.models_dir}
   - Run app once with internet
   - Models will be saved for offline use

3. SKIP (Use API mode only):
   - No download needed
   - Uses cloud APIs (requires Groq API key)
   - Faster but needs internet

{'=' * 60}
"""

        return instructions

    def cleanup_old_models(self):
        """Remove old or corrupted model files"""
        logger.info("🧹 Cleaning up old models...")

        try:
            # List all files in models directory
            if not os.path.exists(self.models_dir):
                logger.info("   No models directory found")
                return

            files = os.listdir(self.models_dir)
            removed = 0

            for file in files:
                file_path = os.path.join(self.models_dir, file)

                # Remove if file is very small (likely corrupted download)
                if os.path.isfile(file_path):
                    size = os.path.getsize(file_path)
                    if size < 1024 * 100:  # Less than 100KB
                        logger.info(f"   🗑️  Removing corrupted file: {file} ({size} bytes)")
                        os.remove(file_path)
                        removed += 1

            if removed > 0:
                logger.info(f"   ✅ Cleaned up {removed} file(s)")
            else:
                logger.info("   ✅ No cleanup needed")

        except Exception as e:
            logger.warning(f"   ⚠️  Cleanup failed: {e}")

    def get_model_path(self, model_name: str) -> Optional[str]:
        """
        Get path to specific model if available

        Args:
            model_name: Name of model ('yolo', 'blip', 'whisper')

        Returns:
            Path to model or None if not available
        """
        models = self.get_model_info()

        if model_name in models and models[model_name]['available']:
            return models[model_name]['path']

        return None

    def is_model_available(self, model_name: str) -> bool:
        """
        Check if specific model is available

        Args:
            model_name: Name of model ('yolo', 'blip', 'whisper')

        Returns:
            True if model is available
        """
        return self.get_model_path(model_name) is not None


# Singleton instance
_model_manager = None


def get_model_manager(models_dir: Optional[str] = None) -> ModelManager:
    """
    Get or create ModelManager singleton

    Args:
        models_dir: Optional custom models directory

    Returns:
        ModelManager instance
    """
    global _model_manager

    if _model_manager is None:
        _model_manager = ModelManager(models_dir)

    return _model_manager


def print_startup_info():
    """Print startup information about models"""
    manager = get_model_manager()
    manager.print_models_status()


if __name__ == "__main__":
    # Test model manager
    manager = ModelManager()
    manager.print_models_status()
    print(manager.get_download_instructions())
