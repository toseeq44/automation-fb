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

logger = get_logger(__name__)


class EditingPreset:
    """
    Represents a saved editing preset/project
    Similar to CapCut projects
    """

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self.created_at = datetime.now()
        self.modified_at = datetime.now()
        self.operations = []  # List of editing operations
        self.thumbnail = None  # Optional thumbnail path
        self.tags = []  # Tags for categorization

    def add_operation(self, operation_name: str, params: Dict[str, Any]):
        """Add an editing operation to the preset"""
        self.operations.append({
            'operation': operation_name,
            'params': params
        })
        self.modified_at = datetime.now()
        logger.info(f"Added operation to preset '{self.name}': {operation_name}")

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
            'operations_count': len(self.operations),
            'created_at': self.created_at.isoformat(),
            'modified_at': self.modified_at.isoformat(),
            'tags': self.tags
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert preset to dictionary for saving"""
        return {
            'name': self.name,
            'description': self.description,
            'created_at': self.created_at.isoformat(),
            'modified_at': self.modified_at.isoformat(),
            'operations': self.operations,
            'thumbnail': self.thumbnail,
            'tags': self.tags
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'EditingPreset':
        """Create preset from dictionary"""
        preset = EditingPreset(data['name'], data.get('description', ''))
        preset.created_at = datetime.fromisoformat(data['created_at'])
        preset.modified_at = datetime.fromisoformat(data['modified_at'])
        preset.operations = data.get('operations', [])
        preset.thumbnail = data.get('thumbnail')
        preset.tags = data.get('tags', [])
        return preset


class PresetManager:
    """
    Manages saving, loading, and applying editing presets
    """

    def __init__(self, presets_dir: str = None):
        """
        Initialize preset manager

        Args:
            presets_dir: Directory to store presets (default: ./presets/)
        """
        if presets_dir is None:
            presets_dir = os.path.join(os.getcwd(), 'presets')

        self.presets_dir = presets_dir
        os.makedirs(self.presets_dir, exist_ok=True)

        self.current_preset = None
        self.presets_cache = {}  # Cache loaded presets

        logger.info(f"PresetManager initialized: {self.presets_dir}")

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

    def save_preset(self, preset: EditingPreset, overwrite: bool = True) -> str:
        """
        Save preset to file

        Args:
            preset: EditingPreset to save
            overwrite: Whether to overwrite existing preset

        Returns:
            Path to saved preset file
        """
        # Sanitize filename
        safe_name = "".join(c for c in preset.name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        filename = f"{safe_name}.preset.json"
        filepath = os.path.join(self.presets_dir, filename)

        # Check if exists
        if os.path.exists(filepath) and not overwrite:
            # Add timestamp to make unique
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{safe_name}_{timestamp}.preset.json"
            filepath = os.path.join(self.presets_dir, filename)

        # Save to file
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(preset.to_dict(), f, indent=2, ensure_ascii=False)

        # Update cache
        self.presets_cache[preset.name] = preset

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

    def list_presets(self) -> List[Dict[str, Any]]:
        """
        List all available presets

        Returns:
            List of preset summaries
        """
        presets = []

        # Scan presets directory
        for filename in os.listdir(self.presets_dir):
            if filename.endswith('.preset.json'):
                filepath = os.path.join(self.presets_dir, filename)

                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    preset = EditingPreset.from_dict(data)
                    presets.append(preset.get_summary())

                except Exception as e:
                    logger.error(f"Failed to read preset file '{filename}': {e}")

        # Sort by modified date (newest first)
        presets.sort(key=lambda x: x['modified_at'], reverse=True)

        logger.info(f"Found {len(presets)} presets")
        return presets

    def delete_preset(self, name: str) -> bool:
        """
        Delete a preset

        Args:
            name: Preset name

        Returns:
            True if deleted, False if not found
        """
        safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        filename = f"{safe_name}.preset.json"
        filepath = os.path.join(self.presets_dir, filename)

        if not os.path.exists(filepath):
            logger.warning(f"Preset not found for deletion: {name}")
            return False

        try:
            os.remove(filepath)

            # Remove from cache
            if name in self.presets_cache:
                del self.presets_cache[name]

            logger.info(f"Preset deleted: {filepath}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete preset '{name}': {e}")
            return False

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

            # Apply all operations
            for i, operation in enumerate(preset.operations):
                op_name = operation['operation']
                params = operation['params']

                if progress_callback:
                    progress_callback(f"Applying {op_name}... ({i+1}/{len(preset.operations)})")

                # Execute operation
                if hasattr(editor, op_name):
                    method = getattr(editor, op_name)
                    method(**params)
                else:
                    logger.warning(f"Unknown operation: {op_name}")

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

    def import_preset(self, import_path: str) -> Optional[EditingPreset]:
        """
        Import preset from file

        Args:
            import_path: Path to preset file

        Returns:
            Imported EditingPreset or None
        """
        preset = self.load_preset_from_file(import_path)
        if preset:
            # Save to presets directory
            self.save_preset(preset)
            logger.info(f"Preset imported: {preset.name}")

        return preset


# ==================== QUICK PRESET TEMPLATES ====================

class PresetTemplates:
    """Predefined preset templates for common use cases"""

    @staticmethod
    def tiktok_standard():
        """Standard TikTok preset"""
        preset = EditingPreset("TikTok Standard", "Optimized for TikTok videos")
        preset.add_operation('crop', {'preset': '9:16'})
        preset.add_operation('resize_video', {'width': 1080, 'height': 1920})
        preset.add_operation('fade_in', {'duration': 0.5})
        preset.add_operation('fade_out', {'duration': 0.5})
        preset.tags = ['tiktok', 'vertical', 'social']
        return preset

    @staticmethod
    def instagram_reels():
        """Instagram Reels preset"""
        preset = EditingPreset("Instagram Reels", "Optimized for Instagram Reels")
        preset.add_operation('crop', {'preset': '9:16'})
        preset.add_operation('resize_video', {'width': 1080, 'height': 1920})
        preset.add_operation('apply_filter', {'filter_name': 'instagram_valencia'})
        preset.add_operation('fade_in', {'duration': 0.5})
        preset.add_operation('fade_out', {'duration': 0.5})
        preset.tags = ['instagram', 'reels', 'vertical']
        return preset

    @staticmethod
    def youtube_shorts():
        """YouTube Shorts preset"""
        preset = EditingPreset("YouTube Shorts", "Optimized for YouTube Shorts")
        preset.add_operation('crop', {'preset': '9:16'})
        preset.add_operation('resize_video', {'width': 1080, 'height': 1920})
        preset.add_operation('apply_filter', {'filter_name': 'youtube_cinematic'})
        preset.add_operation('fade_in', {'duration': 1.0})
        preset.add_operation('fade_out', {'duration': 1.0})
        preset.tags = ['youtube', 'shorts', 'vertical']
        return preset

    @staticmethod
    def cinematic():
        """Cinematic preset"""
        preset = EditingPreset("Cinematic", "Professional cinematic look")
        preset.add_operation('apply_filter', {'filter_name': 'cinematic'})
        preset.add_operation('fade_in', {'duration': 2.0})
        preset.add_operation('fade_out', {'duration': 2.0})
        preset.tags = ['cinematic', 'professional']
        return preset

    @staticmethod
    def vintage():
        """Vintage/retro preset"""
        preset = EditingPreset("Vintage", "Retro/vintage film look")
        preset.add_operation('apply_filter', {'filter_name': 'vintage'})
        preset.add_operation('apply_filter', {'filter_name': 'vignette', 'intensity': 0.5})
        preset.tags = ['vintage', 'retro', 'artistic']
        return preset

    @classmethod
    def get_all_templates(cls) -> List[EditingPreset]:
        """Get all available templates"""
        return [
            cls.tiktok_standard(),
            cls.instagram_reels(),
            cls.youtube_shorts(),
            cls.cinematic(),
            cls.vintage()
        ]
