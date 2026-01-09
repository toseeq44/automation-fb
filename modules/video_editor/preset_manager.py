"""
modules/video_editor/preset_manager.py
Preset/Project Management System - Like CapCut
Save editing operations as presets and apply to multiple videos
"""

import os
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path

from modules.logging.logger import get_logger
from modules.config.paths import get_application_root
from modules.video_editor.operation_library import OperationLibrary
from modules.video_editor.preset_validator import PresetValidator

logger = get_logger(__name__)


class EditingPreset:
    """
    Represents a saved editing preset/project
    Similar to CapCut projects

    Schema v2.0 - Enhanced with metadata and export settings
    """

    SCHEMA_VERSION = "2.0"

    # Preset categories
    CATEGORY_VIDEO = "Video"
    CATEGORY_AUDIO = "Audio"
    CATEGORY_SOCIAL_MEDIA = "Social Media"
    CATEGORY_PROFESSIONAL = "Professional"
    CATEGORY_ARTISTIC = "Artistic"
    CATEGORY_CUSTOM = "Custom"

    def __init__(self, name: str, description: str = "", author: str = "User", category: str = None):
        # Basic info
        self.name = name
        self.description = description
        self.schema_version = self.SCHEMA_VERSION

        # Timestamps
        self.created_at = datetime.now()
        self.modified_at = datetime.now()

        # Operations
        self.operations = []  # List of editing operations

        # Enhanced metadata (v2.0)
        self.author = author
        self.category = category or self.CATEGORY_CUSTOM
        self.preset_version = "1.0"  # User can increment this (1.0, 1.1, 2.0, etc.)
        self.compatibility = ["1.0"]  # Which video editor versions this works with

        # Visual
        self.thumbnail = None  # Optional thumbnail path
        self.tags = []  # Tags for categorization

        # Export settings (v2.0)
        self.export_settings = {
            'quality': 'high',  # high/medium/low
            'format': 'mp4',    # mp4/avi/mov/mkv/etc.
            'resolution': None,  # None = keep original, or (width, height) tuple
            'fps': None,         # None = keep original, or int value
            'codec_video': 'libx264',  # Preferred video codec
            'codec_audio': 'aac',      # Preferred audio codec
            'bitrate_video': None,     # None = auto, or string like '5000k'
            'bitrate_audio': '192k'    # Audio bitrate
        }

    def add_operation(self, operation_name: str, params: Dict[str, Any]):
        """Add an editing operation to the preset"""
        self.operations.append({
            'operation': operation_name,
            'params': params
        })
        self.modified_at = datetime.now()
        # Silent operation - no logging for preset building
        # logger.debug(f"Added operation to preset '{self.name}': {operation_name}")

    def remove_operation(self, index: int):
        """Remove operation by index"""
        if 0 <= index < len(self.operations):
            removed = self.operations.pop(index)
            self.modified_at = datetime.now()
            logger.info(f"Removed operation from preset '{self.name}': {removed['operation']}")
            return removed
        return None

    def clear_operations(self):
        """Clear all operations"""
        self.operations.clear()
        self.modified_at = datetime.now()
        logger.info(f"Cleared all operations from preset '{self.name}'")

    def get_summary(self) -> Dict[str, Any]:
        """Get preset summary"""
        return {
            'name': self.name,
            'description': self.description,
            'author': self.author,
            'category': self.category,
            'preset_version': self.preset_version,
            'operations_count': len(self.operations),
            'created_at': self.created_at.isoformat(),
            'modified_at': self.modified_at.isoformat(),
            'tags': self.tags,
            'schema_version': self.schema_version
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert preset to dictionary for saving (Schema v2.0)"""
        return {
            'schema_version': self.schema_version,
            'name': self.name,
            'description': self.description,
            'created_at': self.created_at.isoformat(),
            'modified_at': self.modified_at.isoformat(),
            'operations': self.operations,
            'thumbnail': self.thumbnail,
            'tags': self.tags,
            # v2.0 fields
            'author': self.author,
            'category': self.category,
            'preset_version': self.preset_version,
            'compatibility': self.compatibility,
            'export_settings': self.export_settings
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'EditingPreset':
        """
        Create preset from dictionary
        Supports both v1.0 and v2.0 schema (backward compatible)
        """
        # Detect schema version
        schema_version = data.get('schema_version', '1.0')

        # Create preset with v2.0 fields (or defaults for v1.0)
        preset = EditingPreset(
            name=data['name'],
            description=data.get('description', ''),
            author=data.get('author', 'User'),
            category=data.get('category', EditingPreset.CATEGORY_CUSTOM)
        )

        # Basic fields
        preset.created_at = datetime.fromisoformat(data['created_at'])
        preset.modified_at = datetime.fromisoformat(data['modified_at'])
        preset.operations = data.get('operations', [])
        preset.thumbnail = data.get('thumbnail')
        preset.tags = data.get('tags', [])

        # v2.0 specific fields
        preset.schema_version = schema_version
        preset.preset_version = data.get('preset_version', '1.0')
        preset.compatibility = data.get('compatibility', ['1.0'])

        # Export settings (use defaults if not present - v1.0 compatibility)
        if 'export_settings' in data:
            preset.export_settings = data['export_settings']
        # else: keep the defaults set in __init__

        return preset


class PresetManager:
    """
    Manages saving, loading, and applying editing presets
    Supports organized folder structure: system/user/imported
    """

    # Preset folders
    FOLDER_SYSTEM = 'system'      # Built-in templates (read-only)
    FOLDER_USER = 'user'          # User-created presets
    FOLDER_IMPORTED = 'imported'  # Imported from others

    def __init__(self, presets_dir: str = None):
        """
        Initialize preset manager with folder structure

        Args:
            presets_dir: Directory to store presets (default: ./presets/)
        """
        if presets_dir is None:
            app_root = get_application_root()
            presets_dir = str(app_root / 'presets')

        self.presets_dir = presets_dir

        # Create folder structure
        self.folders = {
            self.FOLDER_SYSTEM: os.path.join(self.presets_dir, self.FOLDER_SYSTEM),
            self.FOLDER_USER: os.path.join(self.presets_dir, self.FOLDER_USER),
            self.FOLDER_IMPORTED: os.path.join(self.presets_dir, self.FOLDER_IMPORTED)
        }

        for folder_path in self.folders.values():
            os.makedirs(folder_path, exist_ok=True)

        self.current_preset = None
        self.presets_cache = {}  # Cache loaded presets
        self.operation_library = OperationLibrary()
        self.preset_validator = PresetValidator()
        self.preset_validator.set_operation_registry(self.operation_library)

        # Initialize system presets on first run
        self._initialize_system_presets()

        # Silent initialization
        # logger.debug(f"PresetManager initialized: {self.presets_dir}")

    def _initialize_system_presets(self):
        """Initialize built-in system presets if they don't exist"""
        system_folder = self.folders[self.FOLDER_SYSTEM]

        # Get existing preset files
        existing_files = [f for f in os.listdir(system_folder) if f.endswith('.preset.json')]
        existing_names = set()
        for filename in existing_files:
            # Extract preset name from filename (remove .preset.json extension)
            name = filename.replace('.preset.json', '')
            existing_names.add(name)

        # Get all template presets
        from modules.video_editor.preset_manager import PresetTemplates
        templates = PresetTemplates.get_all_templates()

        # Create missing presets
        for template in templates:
            safe_name = "".join(c for c in template.name if c.isalnum() or c in (' ', '-', '_')).rstrip()

            if safe_name not in existing_names:
                # Preset doesn't exist, create it
                try:
                    filepath = os.path.join(system_folder, f"{safe_name}.preset.json")
                    with open(filepath, 'w', encoding='utf-8') as f:
                        json.dump(template.to_dict(), f, indent=2, ensure_ascii=False)
                    logger.info(f"Created system preset: {template.name}")
                except Exception as e:
                    logger.error(f"Failed to create system preset '{template.name}': {e}")

    def create_preset(self, name: str, description: str = "") -> EditingPreset:
        """
        Create a new empty preset

        Args:
            name: Preset name
            description: Optional description

        Returns:
            EditingPreset instance
        """
        preset = EditingPreset(name, description)
        self.current_preset = preset
        logger.info(f"Created new preset: {name}")
        return preset

    def save_preset(self, preset: EditingPreset, folder: str = None, overwrite: bool = True) -> str:
        """
        Save preset to file

        Args:
            preset: EditingPreset to save
            folder: Folder to save in (system/user/imported). Defaults to 'user'
            overwrite: Whether to overwrite existing preset

        Returns:
            Path to saved preset file
        """
        # Default to user folder
        if folder is None:
            folder = self.FOLDER_USER

        # Get folder path
        if folder not in self.folders:
            logger.warning(f"Unknown folder '{folder}', using 'user'")
            folder = self.FOLDER_USER

        folder_path = self.folders[folder]

        # Sanitize filename
        safe_name = "".join(c for c in preset.name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        filename = f"{safe_name}.preset.json"
        filepath = os.path.join(folder_path, filename)

        # Check if exists
        if os.path.exists(filepath) and not overwrite:
            # Add timestamp to make unique
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{safe_name}_{timestamp}.preset.json"
            filepath = os.path.join(folder_path, filename)

        # Save to file
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(preset.to_dict(), f, indent=2, ensure_ascii=False)

        # Update cache
        cache_key = f"{folder}/{preset.name}"
        self.presets_cache[cache_key] = preset

        logger.info(f"Preset saved: {filepath}")
        return filepath

    def load_preset(self, name: str) -> Optional[EditingPreset]:
        """
        Load preset by name

        Args:
            name: Preset name

        Returns:
            EditingPreset or None if not found
        """
        # Check cache first
        if name in self.presets_cache:
            logger.info(f"Loaded preset from cache: {name}")
            return self.presets_cache[name]

        # Find preset file
        safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        filename = f"{safe_name}.preset.json"
        filepath = os.path.join(self.presets_dir, filename)

        if not os.path.exists(filepath):
            logger.warning(f"Preset not found: {name}")
            return None

        # Load from file
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            preset = EditingPreset.from_dict(data)

            # Cache it
            self.presets_cache[preset.name] = preset

            logger.info(f"Preset loaded: {filepath}")
            return preset

        except Exception as e:
            logger.error(f"Failed to load preset '{name}': {e}")
            return None

    def load_preset_from_file(self, filepath: str) -> Optional[EditingPreset]:
        """
        Load preset from specific file path

        Args:
            filepath: Path to preset file

        Returns:
            EditingPreset or None if failed
        """
        if not os.path.exists(filepath):
            logger.warning(f"Preset file not found: {filepath}")
            return None

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            preset = EditingPreset.from_dict(data)

            # Cache it
            self.presets_cache[preset.name] = preset

            logger.info(f"Preset loaded from file: {filepath}")
            return preset

        except Exception as e:
            logger.error(f"Failed to load preset from '{filepath}': {e}")
            return None

    def load_preset_from_folder(self, name: str, folder: str) -> Optional[EditingPreset]:
        """
        Load preset from specific folder

        Args:
            name: Preset name
            folder: Folder name (system/user/imported)

        Returns:
            EditingPreset or None if not found
        """
        # Check cache first with folder-specific key
        cache_key = f"{folder}/{name}"
        if cache_key in self.presets_cache:
            logger.info(f"Loaded preset from cache: {cache_key}")
            return self.presets_cache[cache_key]

        # Get folder path
        if folder not in self.folders:
            logger.warning(f"Unknown folder: {folder}")
            return None

        folder_path = self.folders[folder]

        # Find preset file
        safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        filename = f"{safe_name}.preset.json"
        filepath = os.path.join(folder_path, filename)

        if not os.path.exists(filepath):
            logger.warning(f"Preset not found: {name} in folder {folder}")
            return None

        # Load from file
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            preset = EditingPreset.from_dict(data)

            # Cache it with folder-specific key
            self.presets_cache[cache_key] = preset

            logger.info(f"Preset loaded: {filepath}")
            return preset

        except Exception as e:
            logger.error(f"Failed to load preset '{name}' from folder '{folder}': {e}")
            return None

    def list_presets(self, folder: str = None) -> List[Dict[str, Any]]:
        """
        List available presets

        Args:
            folder: Specific folder to list (None = all folders)

        Returns:
            List of preset summaries with folder info
        """
        presets = []

        # Determine which folders to scan
        if folder:
            folders_to_scan = {folder: self.folders.get(folder)} if folder in self.folders else {}
        else:
            folders_to_scan = self.folders

        # Scan folders
        for folder_name, folder_path in folders_to_scan.items():
            for filename in os.listdir(folder_path):
                if filename.endswith('.preset.json'):
                    filepath = os.path.join(folder_path, filename)

                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            data = json.load(f)

                        preset = EditingPreset.from_dict(data)
                        summary = preset.get_summary()
                        summary['folder'] = folder_name  # Add folder info
                        summary['filepath'] = filepath   # Add file path
                        presets.append(summary)

                    except Exception as e:
                        logger.error(f"Failed to read preset file '{filename}': {e}")

        # Sort by modified date (newest first)
        presets.sort(key=lambda x: x['modified_at'], reverse=True)

        logger.info(f"Found {len(presets)} presets")
        return presets

    def list_presets_by_folder(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        List all presets organized by folder

        Returns:
            Dictionary mapping folder name to list of preset summaries
        """
        organized = {
            self.FOLDER_SYSTEM: [],
            self.FOLDER_USER: [],
            self.FOLDER_IMPORTED: []
        }

        for folder_name in organized.keys():
            organized[folder_name] = self.list_presets(folder=folder_name)

        return organized

    def delete_preset(self, name: str, folder: str = None) -> bool:
        """
        Delete a preset

        Args:
            name: Preset name
            folder: Folder to delete from (None = search all folders)

        Returns:
            True if deleted, False if not found
        """
        safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        filename = f"{safe_name}.preset.json"

        # If folder specified, delete from that folder
        if folder and folder in self.folders:
            filepath = os.path.join(self.folders[folder], filename)
        else:
            # Search in all folders to find the preset
            filepath = None
            for folder_name, folder_path in self.folders.items():
                test_path = os.path.join(folder_path, filename)
                if os.path.exists(test_path):
                    filepath = test_path
                    folder = folder_name
                    break

        if not filepath or not os.path.exists(filepath):
            logger.warning(f"Preset not found for deletion: {name}")
            return False

        # Don't allow deleting system presets
        if folder == self.FOLDER_SYSTEM:
            logger.error(f"Cannot delete system preset: {name}")
            return False

        try:
            os.remove(filepath)

            # Remove from cache
            cache_key = f"{folder}/{name}"
            if cache_key in self.presets_cache:
                del self.presets_cache[cache_key]
            # Also try old cache format
            if name in self.presets_cache:
                del self.presets_cache[name]

            logger.info(f"Preset deleted: {filepath}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete preset '{name}': {e}")
            return False

    def _validate_and_fix_params(self, editor, op_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate parameters, normalize values, and add missing required ones.
        """
        import inspect

        if not isinstance(params, dict):
            logger.warning(f"   Invalid params for {op_name}, using empty params")
            params = {}

        if not hasattr(editor, op_name):
            return params

        method = getattr(editor, op_name)
        sig = inspect.signature(method)
        accepts_kwargs = any(
            param.kind == inspect.Parameter.VAR_KEYWORD
            for param in sig.parameters.values()
        )
        allowed_params = {
            name for name, param in sig.parameters.items()
            if name != 'self' and param.kind not in (
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD
            )
        }

        op_def = None
        if self.operation_library and self.operation_library.has_operation(op_name):
            op_def = self.operation_library.get_operation(op_name)

        fixed_params = {}
        for param_name, value in params.items():
            if not accepts_kwargs and param_name not in allowed_params:
                logger.warning(f"   Dropping unknown param '{param_name}' for {op_name}")
                continue

            if op_name == 'lip_color' and param_name == 'color' and isinstance(value, str):
                value = self._normalize_color_alias(value)

            if op_def and param_name in op_def.parameters:
                value = self._normalize_param_value(op_def.parameters[param_name], value)

            fixed_params[param_name] = value

        for param_name, param in sig.parameters.items():
            if param_name == 'self':
                continue
            if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                continue
            if param.default == inspect.Parameter.empty and param_name not in fixed_params:
                default_value = None
                if op_def and param_name in op_def.parameters:
                    default_value = op_def.parameters[param_name].default
                if default_value is None:
                    default_value = self._generate_sensible_default_by_name(param_name)
                fixed_params[param_name] = default_value
                logger.warning(
                    f"   Missing required parameter '{param_name}' for {op_name}, using default: {default_value}"
                )

        return fixed_params

    def _generate_sensible_default_by_name(self, param_name: str) -> Any:
        """
        Generate sensible default value based on parameter name

        Args:
            param_name: Parameter name

        Returns:
            Sensible default value
        """
        param_lower = param_name.lower()

        # Common patterns
        if 'volume' in param_lower:
            return 1.0  # 100% volume
        elif 'opacity' in param_lower or 'alpha' in param_lower:
            return 1.0  # 100% opacity
        elif 'duration' in param_lower:
            return 1.0  # 1 second
        elif 'speed' in param_lower or 'factor' in param_lower or 'rate' in param_lower:
            return 1.0  # Normal speed
        elif 'width' in param_lower:
            return 1920  # HD width
        elif 'height' in param_lower:
            return 1080  # HD height
        elif 'x' in param_lower or 'y' in param_lower:
            return 0  # Coordinate
        elif 'angle' in param_lower or 'rotation' in param_lower:
            return 0  # No rotation
        elif 'color' in param_lower:
            return 'black'  # Default color
        elif 'text' in param_lower:
            return ''  # Empty text
        elif 'path' in param_lower:
            return ''  # Empty path
        elif 'enabled' in param_lower or 'enable' in param_lower:
            return True  # Enabled by default
        else:
            # Generic defaults
            return 1.0  # Most numeric parameters work with 1.0

    def _normalize_color_alias(self, value: str) -> str:
        """
        Normalize common color aliases to known values.
        """
        normalized = value.strip().lower().replace('_', ' ').replace('-', ' ')
        aliases = {
            'natural': 'nude',
            'skin': 'nude',
            'light red': 'coral',
            'soft red': 'coral',
            'rose': 'coral',
            'dark red': 'berry',
            'maroon': 'berry',
            'wine': 'berry'
        }
        return aliases.get(normalized, normalized)

    def _normalize_param_value(self, param_def, value: Any) -> Any:
        """
        Coerce and clamp a parameter value based on its definition.
        """
        if value is None:
            return value

        try:
            if param_def.param_type == 'int':
                if isinstance(value, str):
                    value = int(float(value.strip()))
                elif isinstance(value, float):
                    value = int(value)
            elif param_def.param_type == 'float':
                if isinstance(value, str):
                    value = float(value.strip())
                elif isinstance(value, int):
                    value = float(value)
            elif param_def.param_type == 'bool':
                if isinstance(value, str):
                    lowered = value.strip().lower()
                    if lowered in ('true', '1', 'yes', 'y', 'on'):
                        value = True
                    elif lowered in ('false', '0', 'no', 'n', 'off'):
                        value = False
                elif isinstance(value, int):
                    value = bool(value)
            elif param_def.param_type == 'tuple':
                if isinstance(value, list):
                    value = tuple(value)
                elif isinstance(value, str) and ',' in value:
                    parts = [p.strip() for p in value.split(',')]
                    if len(parts) == 2:
                        value = (parts[0], parts[1])
            elif param_def.param_type == 'list':
                if isinstance(value, tuple):
                    value = list(value)
        except Exception:
            if param_def.default is not None:
                logger.warning(
                    f"   Invalid value for '{param_def.name}', using default: {param_def.default}"
                )
                return param_def.default
            return value

        if isinstance(value, (int, float)):
            if param_def.min_val is not None and value < param_def.min_val:
                value = param_def.min_val
            if param_def.max_val is not None and value > param_def.max_val:
                value = param_def.max_val

        if param_def.choices and isinstance(value, str):
            choice_map = {str(c).lower(): c for c in param_def.choices}
            lowered = value.lower()
            if lowered in choice_map:
                value = choice_map[lowered]
            else:
                fallback = param_def.default if param_def.default is not None else param_def.choices[0]
                logger.warning(
                    f"   Unknown choice for '{param_def.name}': {value}, using {fallback}"
                )
                value = fallback

        return value

    def apply_preset_to_video(self, preset: EditingPreset, video_path: str,
                             output_path: str, quality: str = 'high',
                             progress_callback=None) -> bool:
        """
        Apply preset to a single video

        Args:
            preset: EditingPreset to apply
            video_path: Input video path
            output_path: Output video path
            quality: Export quality
            progress_callback: Optional callback function(message)

        Returns:
            True if successful, False otherwise
        """
        from modules.video_editor.core import VideoEditor

        try:
            if progress_callback:
                progress_callback(f"Loading video: {os.path.basename(video_path)}")

            # Create editor
            editor = VideoEditor(video_path)

            # Validate preset once before applying
            if self.preset_validator:
                validation = self.preset_validator.validate_preset_data(preset.to_dict())
                if not validation.valid:
                    logger.warning("Preset validation failed, attempting to continue with auto-fixes")
                if validation.warnings:
                    logger.info(f"Preset validation warnings: {len(validation.warnings)}")

            operations = preset.operations if isinstance(preset.operations, list) else []

            # Apply all operations
            for i, operation in enumerate(operations):
                if not isinstance(operation, dict):
                    logger.warning(f"Skipping invalid operation at index {i}")
                    continue

                op_name = operation.get('operation')
                if not op_name or not isinstance(op_name, str):
                    logger.warning(f"Skipping invalid operation name at index {i}")
                    continue

                params = operation.get('params', {})
                if isinstance(params, dict):
                    params = params.copy()
                else:
                    logger.warning(f"Invalid params for operation '{op_name}', using empty params")
                    params = {}

                if progress_callback:
                    progress_callback(f"Applying {op_name}... ({i+1}/{len(operations)})")

                logger.info(f"   Applying operation: {op_name}")
                logger.info(f"   Operation params: {params}")

                # Fix parameter names for specific operations
                if op_name == 'crop':
                    # VideoEditor.crop() only accepts: x1, y1, x2, y2, preset
                    # Remove width, height parameters and rename aspect_ratio to preset
                    if 'aspect_ratio' in params:
                        params['preset'] = params.pop('aspect_ratio')
                    # Remove unsupported parameters
                    params.pop('width', None)
                    params.pop('height', None)

                # Validate and fix missing required parameters
                params = self._validate_and_fix_params(editor, op_name, params)

                # Execute operation
                try:
                    if hasattr(editor, op_name):
                        method = getattr(editor, op_name)
                        logger.info(f"   Calling {op_name} with params...")
                        method(**params)
                        logger.info(f"   ✅ {op_name} completed successfully")
                    else:
                        logger.warning(f"Unknown operation: {op_name}")
                        if progress_callback:
                            progress_callback(f"⚠️  Unknown operation: {op_name}")
                except Exception as op_error:
                    logger.error(f"   ❌ Operation '{op_name}' failed: {op_error}", exc_info=True)
                    if progress_callback:
                        progress_callback(f"❌ Operation '{op_name}' failed: {op_error}")
                    # Re-raise to trigger fallback
                    raise

            # Export
            if progress_callback:
                progress_callback(f"Exporting: {os.path.basename(output_path)}")

            editor.export(output_path, quality=quality)

            editor.cleanup()

            logger.info(f"Preset applied successfully: {video_path} -> {output_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to apply preset to '{video_path}': {e}")
            return False

    def apply_preset_to_multiple_videos(self, preset: EditingPreset,
                                       video_paths: List[str],
                                       output_dir: str,
                                       quality: str = 'high',
                                       name_pattern: str = "{name}_edited{ext}",
                                       progress_callback=None) -> List[Dict[str, Any]]:
        """
        Apply preset to multiple videos (Batch Processing)

        Args:
            preset: EditingPreset to apply
            video_paths: List of input video paths
            output_dir: Output directory
            quality: Export quality
            name_pattern: Output filename pattern
            progress_callback: Optional callback(current, total, current_file, message)

        Returns:
            List of results
        """
        os.makedirs(output_dir, exist_ok=True)
        results = []

        for idx, video_path in enumerate(video_paths):
            try:
                if progress_callback:
                    progress_callback(idx + 1, len(video_paths), video_path, "Processing...")

                # Generate output filename
                name, ext = os.path.splitext(os.path.basename(video_path))
                output_filename = name_pattern.format(
                    name=name,
                    ext=ext,
                    index=idx + 1
                )
                output_path = os.path.join(output_dir, output_filename)

                # Apply preset
                def file_progress(msg):
                    if progress_callback:
                        progress_callback(idx + 1, len(video_paths), video_path, msg)

                success = self.apply_preset_to_video(
                    preset, video_path, output_path, quality, file_progress
                )

                results.append({
                    'input': video_path,
                    'output': output_path if success else None,
                    'status': 'success' if success else 'failed'
                })

            except Exception as e:
                logger.error(f"Failed to process '{video_path}': {e}")
                results.append({
                    'input': video_path,
                    'output': None,
                    'status': 'failed',
                    'error': str(e)
                })

        logger.info(f"Batch processing complete: {len(results)} videos")
        return results

    def duplicate_preset(self, source_name: str, new_name: str) -> Optional[EditingPreset]:
        """
        Duplicate an existing preset

        Args:
            source_name: Source preset name
            new_name: New preset name

        Returns:
            New EditingPreset or None if source not found
        """
        source = self.load_preset(source_name)
        if not source:
            return None

        # Create duplicate
        duplicate = EditingPreset(new_name, source.description)
        duplicate.operations = [op.copy() for op in source.operations]
        duplicate.tags = source.tags.copy()

        # Save duplicate
        self.save_preset(duplicate)

        logger.info(f"Preset duplicated: '{source_name}' -> '{new_name}'")
        return duplicate

    def export_preset(self, preset_name: str, export_path: str) -> bool:
        """
        Export preset to a specific location

        Args:
            preset_name: Preset to export
            export_path: Destination path

        Returns:
            True if successful
        """
        preset = self.load_preset(preset_name)
        if not preset:
            return False

        try:
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(preset.to_dict(), f, indent=2, ensure_ascii=False)

            logger.info(f"Preset exported: {export_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to export preset: {e}")
            return False

    def import_preset(self, import_path: str, folder: str = None) -> Optional[EditingPreset]:
        """
        Import preset from file

        Args:
            import_path: Path to preset file
            folder: Folder to save in (defaults to 'imported')

        Returns:
            Imported EditingPreset or None
        """
        if folder is None:
            folder = self.FOLDER_IMPORTED

        preset = self.load_preset_from_file(import_path)
        if preset:
            # Save to specified folder
            self.save_preset(preset, folder=folder)
            logger.info(f"Preset imported to '{folder}': {preset.name}")

        return preset

    def get_preset_folder(self, preset_name: str) -> Optional[str]:
        """
        Find which folder contains a preset

        Args:
            preset_name: Name of preset

        Returns:
            Folder name or None if not found
        """
        safe_name = "".join(c for c in preset_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        filename = f"{safe_name}.preset.json"

        for folder_name, folder_path in self.folders.items():
            filepath = os.path.join(folder_path, filename)
            if os.path.exists(filepath):
                return folder_name

        return None

    def move_preset(self, preset_name: str, from_folder: str, to_folder: str) -> bool:
        """
        Move preset from one folder to another

        Args:
            preset_name: Name of preset
            from_folder: Source folder
            to_folder: Destination folder

        Returns:
            True if successful
        """
        if from_folder not in self.folders or to_folder not in self.folders:
            logger.error(f"Invalid folder: {from_folder} or {to_folder}")
            return False

        # Don't allow moving to/from system folder
        if from_folder == self.FOLDER_SYSTEM or to_folder == self.FOLDER_SYSTEM:
            logger.error("Cannot move presets to/from system folder")
            return False

        safe_name = "".join(c for c in preset_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        filename = f"{safe_name}.preset.json"

        source_path = os.path.join(self.folders[from_folder], filename)
        dest_path = os.path.join(self.folders[to_folder], filename)

        if not os.path.exists(source_path):
            logger.error(f"Preset not found: {preset_name} in {from_folder}")
            return False

        try:
            # Move file
            os.rename(source_path, dest_path)

            # Update cache
            old_key = f"{from_folder}/{preset_name}"
            new_key = f"{to_folder}/{preset_name}"
            if old_key in self.presets_cache:
                self.presets_cache[new_key] = self.presets_cache.pop(old_key)

            logger.info(f"Moved preset '{preset_name}': {from_folder} → {to_folder}")
            return True

        except Exception as e:
            logger.error(f"Failed to move preset: {e}")
            return False


# ==================== QUICK PRESET TEMPLATES ====================

class PresetTemplates:
    """Predefined preset templates for common use cases"""

    @staticmethod
    def tiktok_standard():
        """Standard TikTok preset"""
        preset = EditingPreset(
            "TikTok Standard",
            "Optimized for TikTok videos",
            author="System",
            category=EditingPreset.CATEGORY_SOCIAL_MEDIA
        )
        preset.add_operation('crop', {'preset': '9:16'})
        preset.add_operation('resize_video', {'width': 1080, 'height': 1920})
        preset.add_operation('fade_in', {'duration': 0.5})
        preset.add_operation('fade_out', {'duration': 0.5})
        preset.tags = ['tiktok', 'vertical', 'social']
        preset.export_settings['resolution'] = (1080, 1920)
        return preset

    @staticmethod
    def instagram_reels():
        """Instagram Reels preset"""
        preset = EditingPreset(
            "Instagram Reels",
            "Optimized for Instagram Reels",
            author="System",
            category=EditingPreset.CATEGORY_SOCIAL_MEDIA
        )
        preset.add_operation('crop', {'preset': '9:16'})
        preset.add_operation('resize_video', {'width': 1080, 'height': 1920})
        preset.add_operation('apply_filter', {'filter_name': 'instagram_valencia'})
        preset.add_operation('fade_in', {'duration': 0.5})
        preset.add_operation('fade_out', {'duration': 0.5})
        preset.tags = ['instagram', 'reels', 'vertical']
        preset.export_settings['resolution'] = (1080, 1920)
        return preset

    @staticmethod
    def youtube_shorts():
        """YouTube Shorts preset"""
        preset = EditingPreset(
            "YouTube Shorts",
            "Optimized for YouTube Shorts",
            author="System",
            category=EditingPreset.CATEGORY_SOCIAL_MEDIA
        )
        preset.add_operation('crop', {'preset': '9:16'})
        preset.add_operation('resize_video', {'width': 1080, 'height': 1920})
        preset.add_operation('apply_filter', {'filter_name': 'youtube_cinematic'})
        preset.add_operation('fade_in', {'duration': 1.0})
        preset.add_operation('fade_out', {'duration': 1.0})
        preset.tags = ['youtube', 'shorts', 'vertical']
        preset.export_settings['resolution'] = (1080, 1920)
        return preset

    @staticmethod
    def cinematic():
        """Cinematic preset"""
        preset = EditingPreset(
            "Cinematic",
            "Professional cinematic look",
            author="System",
            category=EditingPreset.CATEGORY_PROFESSIONAL
        )
        preset.add_operation('apply_filter', {'filter_name': 'cinematic'})
        preset.add_operation('fade_in', {'duration': 2.0})
        preset.add_operation('fade_out', {'duration': 2.0})
        preset.tags = ['cinematic', 'professional']
        return preset

    @staticmethod
    def vintage():
        """Vintage/retro preset"""
        preset = EditingPreset(
            "Vintage",
            "Retro/vintage film look",
            author="System",
            category=EditingPreset.CATEGORY_ARTISTIC
        )
        preset.add_operation('apply_filter', {'filter_name': 'vintage'})
        preset.add_operation('apply_filter', {'filter_name': 'vignette', 'intensity': 0.5})
        preset.tags = ['vintage', 'retro', 'artistic']
        return preset

    @staticmethod
    def dual_video():
        """Dual Video preset - merge two videos side-by-side"""
        preset = EditingPreset(
            "Dual Video",
            "Merge two videos side-by-side with intelligent length matching. "
            "Primary video (60%) with audio, secondary video (40%) muted. "
            "Both videos zoomed 110% with seamless divider.",
            author="System",
            category=EditingPreset.CATEGORY_VIDEO
        )
        # Note: secondary_video_path will be provided by user at runtime
        preset.add_operation('dual_video_merge', {
            'secondary_video_path': '',  # User will specify this
            'primary_position': 'right',  # Primary on right, secondary on left
            'zoom_factor': 1.1,  # 110% zoom
            'primary_width_ratio': 0.6,  # 60-40 split
            'divider_width': 2,  # 2px divider line
            'divider_color': 'black',  # Seamless black divider
            'audio_source': 'primary'  # Only primary audio
        })
        preset.tags = ['dual', 'split-screen', 'merge', 'side-by-side']
        preset.export_settings['quality'] = 'high'
        return preset

    @classmethod
    def get_all_templates(cls) -> List[EditingPreset]:
        """Get all available templates"""
        return [
            cls.tiktok_standard(),
            cls.instagram_reels(),
            cls.youtube_shorts(),
            cls.cinematic(),
            cls.vintage(),
            cls.dual_video()
        ]
