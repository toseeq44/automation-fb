"""
modules/video_editor/preset_validator.py
Validates preset JSON structure and operation compatibility
"""

import json
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime

from modules.logging.logger import get_logger

logger = get_logger(__name__)


class ValidationResult:
    """Result of preset validation"""

    def __init__(self, valid: bool = True, errors: List[str] = None, warnings: List[str] = None):
        self.valid = valid
        self.errors = errors or []
        self.warnings = warnings or []

    def add_error(self, error: str):
        """Add validation error"""
        self.errors.append(error)
        self.valid = False

    def add_warning(self, warning: str):
        """Add validation warning"""
        self.warnings.append(warning)

    def __bool__(self):
        """Allow using in boolean context"""
        return self.valid

    def get_message(self) -> str:
        """Get formatted validation message"""
        if self.valid:
            msg = "✓ Validation passed"
            if self.warnings:
                msg += f" ({len(self.warnings)} warnings)"
            return msg
        else:
            msg = f"✗ Validation failed with {len(self.errors)} error(s)"
            for error in self.errors:
                msg += f"\n  • {error}"
            if self.warnings:
                msg += f"\n\nWarnings ({len(self.warnings)}):"
                for warning in self.warnings:
                    msg += f"\n  • {warning}"
            return msg


class PresetValidator:
    """
    Validates editing presets for correctness and compatibility
    """

    # Supported schema versions
    SUPPORTED_SCHEMAS = ["1.0", "2.0"]

    # Required fields for each schema version
    REQUIRED_FIELDS_V1 = ['name', 'description', 'created_at', 'modified_at', 'operations']
    REQUIRED_FIELDS_V2 = REQUIRED_FIELDS_V1 + ['schema_version', 'author', 'category']

    # Valid categories
    VALID_CATEGORIES = ['Video', 'Audio', 'Social Media', 'Professional', 'Artistic', 'Custom']

    # Valid quality settings
    VALID_QUALITIES = ['high', 'medium', 'low']

    # Valid video formats
    VALID_FORMATS = ['mp4', 'avi', 'mov', 'mkv', 'flv', 'wmv', 'webm', 'm4v', 'mpeg', 'mpg']

    def __init__(self):
        """Initialize validator"""
        self.operation_registry = None  # Will be set from OperationLibrary

    def set_operation_registry(self, registry):
        """Set operation registry for operation validation"""
        self.operation_registry = registry

    def validate_preset_file(self, filepath: str) -> ValidationResult:
        """
        Validate a preset file

        Args:
            filepath: Path to preset JSON file

        Returns:
            ValidationResult
        """
        result = ValidationResult()

        # Check file exists
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except FileNotFoundError:
            result.add_error(f"File not found: {filepath}")
            return result
        except json.JSONDecodeError as e:
            result.add_error(f"Invalid JSON format: {e}")
            return result
        except Exception as e:
            result.add_error(f"Failed to read file: {e}")
            return result

        # Validate preset data
        return self.validate_preset_data(data)

    def validate_preset_data(self, data: Dict[str, Any]) -> ValidationResult:
        """
        Validate preset data dictionary

        Args:
            data: Preset data dictionary

        Returns:
            ValidationResult
        """
        result = ValidationResult()

        # 1. Validate schema version
        schema_version = data.get('schema_version', '1.0')

        if schema_version not in self.SUPPORTED_SCHEMAS:
            result.add_error(f"Unsupported schema version: {schema_version}")
            return result

        # 2. Validate required fields
        required_fields = self.REQUIRED_FIELDS_V2 if schema_version == '2.0' else self.REQUIRED_FIELDS_V1

        for field in required_fields:
            if field not in data:
                result.add_error(f"Missing required field: {field}")

        if not result.valid:
            return result

        # 3. Validate field types and values
        self._validate_basic_fields(data, result)

        # 4. Validate operations
        self._validate_operations(data.get('operations', []), result)

        # 5. Validate export settings (v2.0 only)
        if schema_version == '2.0' and 'export_settings' in data:
            self._validate_export_settings(data['export_settings'], result)

        # 6. Additional warnings
        if not data.get('operations'):
            result.add_warning("Preset has no operations defined")

        return result

    def _validate_basic_fields(self, data: Dict[str, Any], result: ValidationResult):
        """Validate basic preset fields"""

        # Name
        name = data.get('name', '')
        if not name or not isinstance(name, str):
            result.add_error("Invalid name: must be non-empty string")
        elif len(name) > 100:
            result.add_warning("Name is very long (>100 chars)")

        # Description
        description = data.get('description', '')
        if not isinstance(description, str):
            result.add_error("Invalid description: must be string")

        # Timestamps
        for field in ['created_at', 'modified_at']:
            try:
                datetime.fromisoformat(data[field])
            except (ValueError, KeyError) as e:
                result.add_error(f"Invalid {field}: must be ISO format datetime")

        # Category (v2.0)
        if 'category' in data:
            category = data['category']
            if category not in self.VALID_CATEGORIES:
                result.add_warning(f"Unknown category: {category}. Valid: {', '.join(self.VALID_CATEGORIES)}")

        # Tags
        if 'tags' in data:
            tags = data['tags']
            if not isinstance(tags, list):
                result.add_error("Invalid tags: must be list")
            elif not all(isinstance(t, str) for t in tags):
                result.add_error("Invalid tags: all items must be strings")

        # Compatibility (v2.0)
        if 'compatibility' in data:
            compat = data['compatibility']
            if not isinstance(compat, list):
                result.add_error("Invalid compatibility: must be list")

    def _validate_operations(self, operations: List[Dict[str, Any]], result: ValidationResult):
        """Validate operations list"""

        if not isinstance(operations, list):
            result.add_error("Operations must be a list")
            return

        for i, op in enumerate(operations):
            # Check operation structure
            if not isinstance(op, dict):
                result.add_error(f"Operation {i}: must be a dictionary")
                continue

            if 'operation' not in op:
                result.add_error(f"Operation {i}: missing 'operation' field")
                continue

            if 'params' not in op:
                result.add_error(f"Operation {i}: missing 'params' field")
                continue

            op_name = op['operation']
            params = op['params']

            # Validate operation name
            if not isinstance(op_name, str):
                result.add_error(f"Operation {i}: operation name must be string")
                continue

            # Validate params
            if not isinstance(params, dict):
                result.add_error(f"Operation {i} ({op_name}): params must be dictionary")
                continue

            # Check operation exists in registry (if registry is set)
            if self.operation_registry:
                if not self.operation_registry.has_operation(op_name):
                    result.add_warning(f"Operation {i}: unknown operation '{op_name}'")
                else:
                    # Validate parameters against registry
                    op_validation = self.operation_registry.validate_operation(op_name, params)
                    if not op_validation.valid:
                        for error in op_validation.errors:
                            result.add_error(f"Operation {i} ({op_name}): {error}")
                        for warning in op_validation.warnings:
                            result.add_warning(f"Operation {i} ({op_name}): {warning}")

    def _validate_export_settings(self, settings: Dict[str, Any], result: ValidationResult):
        """Validate export settings (v2.0)"""

        if not isinstance(settings, dict):
            result.add_error("Export settings must be dictionary")
            return

        # Quality
        if 'quality' in settings:
            quality = settings['quality']
            if quality not in self.VALID_QUALITIES:
                result.add_error(f"Invalid quality: {quality}. Valid: {', '.join(self.VALID_QUALITIES)}")

        # Format
        if 'format' in settings:
            fmt = settings['format']
            if fmt not in self.VALID_FORMATS:
                result.add_warning(f"Unknown format: {fmt}. Common formats: {', '.join(self.VALID_FORMATS[:5])}")

        # Resolution
        if 'resolution' in settings and settings['resolution'] is not None:
            res = settings['resolution']
            if not isinstance(res, (list, tuple)) or len(res) != 2:
                result.add_error("Resolution must be [width, height] or null")
            elif not all(isinstance(x, int) and x > 0 for x in res):
                result.add_error("Resolution dimensions must be positive integers")

        # FPS
        if 'fps' in settings and settings['fps'] is not None:
            fps = settings['fps']
            if not isinstance(fps, (int, float)) or fps <= 0:
                result.add_error("FPS must be positive number or null")

        # Codecs
        for codec_field in ['codec_video', 'codec_audio']:
            if codec_field in settings:
                codec = settings[codec_field]
                if not isinstance(codec, str):
                    result.add_error(f"{codec_field} must be string")

        # Bitrates
        for bitrate_field in ['bitrate_video', 'bitrate_audio']:
            if bitrate_field in settings and settings[bitrate_field] is not None:
                bitrate = settings[bitrate_field]
                if not isinstance(bitrate, (str, int)):
                    result.add_error(f"{bitrate_field} must be string (e.g., '5000k') or integer")

    def validate_operation_compatibility(self, operations: List[Dict[str, Any]]) -> ValidationResult:
        """
        Check if operations are compatible with each other
        (e.g., some operations may conflict)

        Args:
            operations: List of operations

        Returns:
            ValidationResult
        """
        result = ValidationResult()

        # Track what types of operations we've seen
        seen_ops = set()

        for i, op in enumerate(operations):
            op_name = op.get('operation', '')
            seen_ops.add(op_name)

            # Check for potential conflicts
            # Example: Multiple resize operations might be redundant
            if op_name in ['resize_video', 'scale']:
                resize_count = sum(1 for o in operations if o.get('operation') in ['resize_video', 'scale'])
                if resize_count > 1:
                    result.add_warning(f"Multiple resize operations detected ({resize_count})")

            # Example: Crop and resize order matters
            if op_name == 'resize_video':
                # Check if there's a crop operation after this
                remaining_ops = [o.get('operation') for o in operations[i+1:]]
                if 'crop' in remaining_ops:
                    result.add_warning(f"Operation {i}: resize before crop - consider reordering")

        return result
