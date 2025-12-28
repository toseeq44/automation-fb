"""
Smart Model Finder
Automatically detects AI models in multiple locations
Enables enhanced features when models are available
"""

import os
import json
from pathlib import Path
from typing import Dict, Optional, List
from modules.logging.logger import get_logger

logger = get_logger(__name__)


class ModelFinder:
    """
    Smart model finder that searches for AI models in multiple locations
    Supports: Whisper, CLIP, and other downloadable models
    """

    # Standard search locations (in priority order)
    SEARCH_PATHS = [
        # 1. Application directory
        Path(__file__).parent / "models",

        # 2. C drive AI_Models folder
        Path("C:/AI_Models"),

        # 3. Desktop AI_Models folder
        Path.home() / "Desktop" / "AI_Models",

        # 4. User home directory
        Path.home() / "AI_Models",

        # 5. Documents folder
        Path.home() / "Documents" / "AI_Models",
    ]

    def __init__(self):
        """Initialize model finder"""
        self.models_found = {}
        self.base_path = None
        self.custom_paths = self._load_custom_paths()

    def _load_custom_paths(self) -> Dict[str, str]:
        """Load custom paths from config file"""
        config_locations = [
            Path.home() / ".automation-fb" / "model_paths.json",
            Path("C:/AI_Models/config.json"),
            Path.home() / "Desktop" / "AI_Models" / "config.json"
        ]

        for config_path in config_locations:
            if config_path.exists():
                try:
                    with open(config_path, 'r') as f:
                        custom = json.load(f)
                        logger.info(f"✅ Loaded custom paths from: {config_path}")
                        return custom
                except Exception as e:
                    logger.warning(f"Failed to load config from {config_path}: {e}")

        return {}

    def find_models(self) -> Dict[str, bool]:
        """
        Search for AI models in all standard locations

        Returns:
            Dict with model availability:
            {
                'whisper': bool,
                'clip': bool,
                'base_path': str or None
            }
        """
        logger.info("🔍 Searching for AI models...")

        # Add custom paths to search
        search_paths = list(self.SEARCH_PATHS)
        if self.custom_paths.get('whisper_path'):
            search_paths.insert(0, Path(self.custom_paths['whisper_path']).parent)

        # Search each location
        for search_path in search_paths:
            if not search_path.exists():
                continue

            logger.debug(f"Checking: {search_path}")

            # Check for Whisper models
            whisper_found = self._check_whisper(search_path)

            # Check for CLIP models
            clip_found = self._check_clip(search_path)

            # If any models found in this location, use it as base
            if whisper_found or clip_found:
                self.base_path = search_path
                self.models_found = {
                    'whisper': whisper_found,
                    'clip': clip_found,
                    'base_path': str(search_path)
                }

                logger.info(f"✅ Models found in: {search_path}")
                if whisper_found:
                    logger.info(f"   ✅ Whisper models available")
                if clip_found:
                    logger.info(f"   ✅ CLIP models available")

                return self.models_found

        # No models found
        logger.warning("⚠️ No AI models found in any standard location")
        logger.info("💡 Download models and place in:")
        for path in self.SEARCH_PATHS[:3]:
            logger.info(f"   • {path}")

        return {
            'whisper': False,
            'clip': False,
            'base_path': None
        }

    def _check_whisper(self, base_path: Path) -> bool:
        """Check if Whisper models exist"""
        whisper_path = base_path / "whisper"

        if not whisper_path.exists():
            return False

        # Check for any model file (.pt extension)
        model_files = list(whisper_path.glob("*.pt"))

        if model_files:
            logger.debug(f"Found Whisper models: {[m.name for m in model_files]}")
            return True

        return False

    def _check_clip(self, base_path: Path) -> bool:
        """Check if CLIP models exist"""
        clip_path = base_path / "clip"

        if not clip_path.exists():
            return False

        # Check for CLIP model folder
        model_folders = [
            clip_path / "vit-base-patch32",
            clip_path / "openai-clip-vit-base-patch32"
        ]

        for folder in model_folders:
            if folder.exists():
                # Check for model files
                if list(folder.glob("*.bin")) or list(folder.glob("pytorch_model.bin")):
                    logger.debug(f"Found CLIP model in: {folder}")
                    return True

        return False

    def get_whisper_model_path(self, model_size: str = 'base') -> Optional[str]:
        """
        Get path to Whisper model file

        Args:
            model_size: Model size (tiny, base, small, medium, large)

        Returns:
            Path to model file or None
        """
        if not self.models_found.get('whisper'):
            return None

        whisper_path = Path(self.base_path) / "whisper"
        model_file = whisper_path / f"{model_size}.pt"

        if model_file.exists():
            return str(model_file)

        # Try to find any available model
        available_models = list(whisper_path.glob("*.pt"))
        if available_models:
            logger.info(f"Model '{model_size}' not found, using: {available_models[0].name}")
            return str(available_models[0])

        return None

    def get_clip_model_path(self) -> Optional[str]:
        """
        Get path to CLIP model folder

        Returns:
            Path to CLIP model folder or None
        """
        if not self.models_found.get('clip'):
            return None

        clip_path = Path(self.base_path) / "clip"

        # Try standard paths
        for folder_name in ["vit-base-patch32", "openai-clip-vit-base-patch32"]:
            model_folder = clip_path / folder_name
            if model_folder.exists():
                return str(model_folder)

        return None

    def get_download_instructions(self) -> str:
        """
        Get user-friendly download instructions

        Returns:
            Formatted instructions string
        """
        instructions = """
╔══════════════════════════════════════════════════════════════╗
║  🚀 ENABLE AI-POWERED TITLE GENERATION                       ║
╚══════════════════════════════════════════════════════════════╝

Currently running in BASIC MODE.
Download AI models for enhanced multilingual features:

📥 DOWNLOAD MODELS:
──────────────────────────────────────────────────────────────

1️⃣  WHISPER (Audio/Language Detection)
   Size: ~150MB (base model, recommended)
   Link: https://github.com/openai/whisper/releases

   Download: base.pt

2️⃣  CLIP (Visual Analysis)
   Size: ~350MB
   Link: https://huggingface.co/openai/clip-vit-base-patch32

   Or use: git lfs install && git clone https://huggingface.co/openai/clip-vit-base-patch32

📁 PLACE MODELS IN ANY OF THESE LOCATIONS:
──────────────────────────────────────────────────────────────

Option 1 (Recommended): C:\\AI_Models\\
   C:\\AI_Models\\
      ├── whisper\\
      │   └── base.pt
      └── clip\\
          └── vit-base-patch32\\
              └── (model files)

Option 2: Desktop\\AI_Models\\
   {Desktop}\\AI_Models\\
      ├── whisper\\
      └── clip\\

Option 3: Application Folder
   {App Directory}\\models\\
      ├── whisper\\
      └── clip\\

🔄 AFTER DOWNLOADING:
──────────────────────────────────────────────────────────────
1. Place models in one of the above folders
2. Restart the application
3. AI features will auto-enable! ✅

💡 TIP: Keep models in C:\\AI_Models\\ for easy updates

════════════════════════════════════════════════════════════════
"""
        return instructions.format(
            Desktop=str(Path.home() / "Desktop"),
            App_Directory=str(Path(__file__).parent)
        )

    def save_custom_path(self, model_type: str, path: str):
        """
        Save custom model path to config

        Args:
            model_type: 'whisper' or 'clip'
            path: Path to model
        """
        config_path = Path.home() / ".automation-fb" / "model_paths.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)

        # Load existing config
        if config_path.exists():
            with open(config_path, 'r') as f:
                config = json.load(f)
        else:
            config = {}

        # Update path
        config[f'{model_type}_path'] = path

        # Save
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)

        logger.info(f"✅ Saved custom path for {model_type}: {path}")


# Global model finder instance
_model_finder = None

def get_model_finder() -> ModelFinder:
    """Get global model finder instance"""
    global _model_finder
    if _model_finder is None:
        _model_finder = ModelFinder()
    return _model_finder
