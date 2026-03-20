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
        Search for AI models in all standard locations AND check pip installations

        PRIORITY:
        1. Check if packages are installed via pip (MOST COMMON)
        2. Check for model files in custom directories (MANUAL INSTALL)

        Returns:
            Dict with model availability:
            {
                'whisper': bool,
                'clip': bool,
                'base_path': str or None,
                'install_method': 'pip' or 'manual' or None
            }
        """
        logger.info("🔍 Searching for AI models...")

        # PRIORITY 1: Check if packages are installed via pip
        pip_whisper = self._check_pip_package('whisper')
        pip_transformers = self._check_pip_package('transformers')
        pip_torch = self._check_pip_package('torch')

        if pip_whisper or pip_transformers:
            logger.info("✅ Found AI packages installed via pip:")
            if pip_whisper:
                logger.info("   ✅ openai-whisper")
            if pip_transformers:
                logger.info("   ✅ transformers (CLIP)")
            if pip_torch:
                logger.info("   ✅ torch")

            return {
                'whisper': pip_whisper,
                'clip': pip_transformers,  # CLIP requires transformers
                'base_path': 'pip-installed',
                'install_method': 'pip'
            }

        # PRIORITY 2: Check for manual installations in specific folders
        logger.info("📂 Checking manual installation folders...")

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
                    'base_path': str(search_path),
                    'install_method': 'manual'
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
            'base_path': None,
            'install_method': None
        }

    def _check_pip_package(self, package_name: str) -> bool:
        """
        Check if a Python package is installed via pip

        Args:
            package_name: Package to check ('whisper', 'transformers', 'torch')

        Returns:
            True if package can be imported, False otherwise
        """
        try:
            if package_name == 'whisper':
                import whisper
                logger.debug(f"✅ Package 'whisper' is importable")
                return True
            elif package_name == 'transformers':
                import transformers
                logger.debug(f"✅ Package 'transformers' is importable")
                return True
            elif package_name == 'torch':
                import torch
                logger.debug(f"✅ Package 'torch' is importable")
                return True
            else:
                return False
        except ImportError as e:
            logger.debug(f"❌ Package '{package_name}' not installed: {e}")
            return False
        except OSError as e:
            # Common Windows DLL error (PyTorch)
            if "DLL" in str(e) or "1114" in str(e):
                logger.warning(f"⚠️  DLL Error loading '{package_name}'")
                logger.warning(f"")
                logger.warning(f"🔧 QUICK FIX Required:")
                logger.warning(f"   Option 1: Install Visual C++ Redistributables")
                logger.warning(f"   Download: https://aka.ms/vs/17/release/vc_redist.x64.exe")
                logger.warning(f"")
                logger.warning(f"   Option 2: Reinstall PyTorch (CPU-only)")
                logger.warning(f"   pip uninstall torch")
                logger.warning(f"   pip install torch --index-url https://download.pytorch.org/whl/cpu")
                logger.warning(f"")
            else:
                logger.error(f"❌ OS Error checking package '{package_name}': {e}")
            return False
        except Exception as e:
            logger.debug(f"❌ Error checking package '{package_name}': {e}")
            return False

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

    def auto_install_packages(self, progress_callback=None) -> Dict[str, any]:
        """
        Automatically install AI packages via pip

        Args:
            progress_callback: Optional callback function(message: str) for progress updates

        Returns:
            Dict with installation results:
            {
                'success': bool,
                'installed': List[str],
                'failed': List[str],
                'errors': List[str]
            }
        """
        import subprocess
        import sys

        packages = [
            ('openai-whisper', 'whisper'),
            ('transformers', 'transformers'),
            ('torch', 'torch')
        ]

        installed = []
        failed = []
        errors = []

        def log_progress(msg):
            if progress_callback:
                progress_callback(msg)
            logger.info(msg)

        log_progress("🚀 Starting automatic package installation...")
        log_progress("This may take 10-15 minutes (downloading ~2-4GB)")
        log_progress("")

        for pip_name, import_name in packages:
            try:
                log_progress(f"📥 Installing {pip_name}...")

                # Run pip install
                result = subprocess.run(
                    [sys.executable, '-m', 'pip', 'install', pip_name],
                    capture_output=True,
                    text=True,
                    timeout=600  # 10 minute timeout per package
                )

                if result.returncode == 0:
                    log_progress(f"   ✅ {pip_name} installed successfully")
                    installed.append(pip_name)
                else:
                    error_msg = result.stderr[:200] if result.stderr else "Unknown error"
                    log_progress(f"   ❌ {pip_name} installation failed: {error_msg}")
                    failed.append(pip_name)
                    errors.append(error_msg)

            except subprocess.TimeoutExpired:
                error_msg = f"Installation timeout (>10 minutes)"
                log_progress(f"   ❌ {pip_name}: {error_msg}")
                failed.append(pip_name)
                errors.append(error_msg)

            except Exception as e:
                error_msg = str(e)
                log_progress(f"   ❌ {pip_name}: {error_msg}")
                failed.append(pip_name)
                errors.append(error_msg)

        log_progress("")
        log_progress("=" * 60)

        if len(installed) == len(packages):
            log_progress("🎉 SUCCESS! All packages installed")
            log_progress("🔄 Please RESTART the application to enable Enhanced Mode")
            return {
                'success': True,
                'installed': installed,
                'failed': [],
                'errors': []
            }
        elif installed:
            log_progress(f"⚠️  Partial success: {len(installed)}/{len(packages)} installed")
            log_progress(f"   ✅ Installed: {', '.join(installed)}")
            log_progress(f"   ❌ Failed: {', '.join(failed)}")
            return {
                'success': False,
                'installed': installed,
                'failed': failed,
                'errors': errors
            }
        else:
            log_progress("❌ FAILED: No packages installed")
            log_progress("Please check your internet connection and try manual installation")
            return {
                'success': False,
                'installed': [],
                'failed': failed,
                'errors': errors
            }


# Global model finder instance
_model_finder = None

def get_model_finder() -> ModelFinder:
    """Get global model finder instance"""
    global _model_finder
    if _model_finder is None:
        _model_finder = ModelFinder()
    return _model_finder
