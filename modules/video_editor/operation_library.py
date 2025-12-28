"""
modules/video_editor/operation_library.py
Registry of all available video editing operations with metadata
"""

from typing import Dict, Any, List, Optional
from modules.logging.logger import get_logger

logger = get_logger(__name__)


class ParameterDef:
    """Definition of an operation parameter"""

    def __init__(self, name: str, param_type: str, required: bool = True,
                 default: Any = None, description: str = "",
                 min_val: Any = None, max_val: Any = None,
                 choices: List[Any] = None):
        self.name = name
        self.param_type = param_type  # 'int', 'float', 'str', 'bool', 'tuple', 'list'
        self.required = required
        self.default = default
        self.description = description
        self.min_val = min_val
        self.max_val = max_val
        self.choices = choices  # List of valid choices

    def validate(self, value: Any) -> tuple[bool, Optional[str]]:
        """Validate parameter value"""

        # Check None for required params
        if value is None:
            if self.required:
                return False, f"Required parameter '{self.name}' is missing"
            else:
                return True, None

        # Type validation
        type_map = {
            'int': int,
            'float': (int, float),  # Allow int for float params
            'str': str,
            'bool': bool,
            'tuple': (tuple, list),  # Allow list for tuple params
            'list': list
        }

        expected_type = type_map.get(self.param_type)
        if expected_type and not isinstance(value, expected_type):
            return False, f"Parameter '{self.name}' must be {self.param_type}, got {type(value).__name__}"

        # Range validation
        if self.min_val is not None and value < self.min_val:
            return False, f"Parameter '{self.name}' must be >= {self.min_val}"

        if self.max_val is not None and value > self.max_val:
            return False, f"Parameter '{self.name}' must be <= {self.max_val}"

        # Choices validation
        if self.choices and value not in self.choices:
            return False, f"Parameter '{self.name}' must be one of: {', '.join(map(str, self.choices))}"

        return True, None


class OperationDef:
    """Definition of a video editing operation"""

    def __init__(self, name: str, display_name: str, category: str,
                 description: str, parameters: List[ParameterDef],
                 icon: str = None):
        self.name = name
        self.display_name = display_name
        self.category = category
        self.description = description
        self.parameters = {p.name: p for p in parameters}
        self.icon = icon

    def validate_params(self, params: Dict[str, Any]) -> tuple[bool, List[str], List[str]]:
        """
        Validate operation parameters

        Returns:
            (valid, errors, warnings)
        """
        errors = []
        warnings = []

        # Check for unknown parameters
        for param_name in params:
            if param_name not in self.parameters:
                warnings.append(f"Unknown parameter: {param_name}")

        # Validate each defined parameter
        for param_def in self.parameters.values():
            value = params.get(param_def.name)

            valid, error = param_def.validate(value)
            if not valid:
                errors.append(error)

        return len(errors) == 0, errors, warnings


class ValidationResult:
    """Result of operation validation"""

    def __init__(self, valid: bool = True, errors: List[str] = None, warnings: List[str] = None):
        self.valid = valid
        self.errors = errors or []
        self.warnings = warnings or []


class OperationLibrary:
    """
    Registry of all available video editing operations
    Provides metadata, categorization, and parameter validation
    """

    # Operation categories
    CATEGORY_VIDEO = "Video"
    CATEGORY_AUDIO = "Audio"
    CATEGORY_TEXT_OVERLAY = "Text & Overlay"
    CATEGORY_EFFECTS = "Effects"
    CATEGORY_TRANSFORM = "Transform"
    CATEGORY_METADATA = "Metadata"

    def __init__(self):
        """Initialize operation library"""
        self.operations: Dict[str, OperationDef] = {}
        self._register_all_operations()

    def _register_all_operations(self):
        """Register all available operations"""

        # ==================== VIDEO OPERATIONS ====================

        self.register(OperationDef(
            name='trim',
            display_name='Trim Video',
            category=self.CATEGORY_VIDEO,
            description='Trim video to specific time range',
            parameters=[
                ParameterDef('start_time', 'float', required=True, min_val=0,
                           description='Start time in seconds'),
                ParameterDef('end_time', 'float', required=True, min_val=0,
                           description='End time in seconds')
            ],
            icon='✂️'
        ))

        self.register(OperationDef(
            name='crop',
            display_name='Crop Video',
            category=self.CATEGORY_VIDEO,
            description='Crop video to specific dimensions or aspect ratio',
            parameters=[
                ParameterDef('x1', 'int', required=False, min_val=0,
                           description='Left position (pixels)'),
                ParameterDef('y1', 'int', required=False, min_val=0,
                           description='Top position (pixels)'),
                ParameterDef('x2', 'int', required=False, min_val=0,
                           description='Right position (pixels)'),
                ParameterDef('y2', 'int', required=False, min_val=0,
                           description='Bottom position (pixels)'),
                ParameterDef('preset', 'str', required=False,
                           choices=['16:9', '9:16', '1:1', '4:3', '21:9'],
                           description='Aspect ratio preset')
            ],
            icon='⬛'
        ))

        self.register(OperationDef(
            name='resize_video',
            display_name='Resize Video',
            category=self.CATEGORY_VIDEO,
            description='Resize video to specific dimensions or scale',
            parameters=[
                ParameterDef('width', 'int', required=False, min_val=1,
                           description='Target width (pixels)'),
                ParameterDef('height', 'int', required=False, min_val=1,
                           description='Target height (pixels)'),
                ParameterDef('scale', 'float', required=False, min_val=0.1, max_val=10.0,
                           description='Scale factor (e.g., 0.5 = 50%, 2.0 = 200%)')
            ],
            icon='📏'
        ))

        self.register(OperationDef(
            name='change_speed',
            display_name='Change Speed',
            category=self.CATEGORY_VIDEO,
            description='Speed up or slow down video',
            parameters=[
                ParameterDef('factor', 'float', required=True, min_val=0.1, max_val=10.0,
                           description='Speed factor (e.g., 0.5 = 50% speed, 2.0 = 2x speed)')
            ],
            icon='⏩'
        ))

        self.register(OperationDef(
            name='dual_video_merge',
            display_name='Dual Video Merge',
            category=self.CATEGORY_VIDEO,
            description='Merge two videos side-by-side with intelligent length matching',
            parameters=[
                ParameterDef('secondary_video_path', 'str', required=True,
                           description='Path to secondary video file'),
                ParameterDef('primary_position', 'str', required=False, default='right',
                           choices=['left', 'right'],
                           description='Position of primary video (left or right)'),
                ParameterDef('zoom_factor', 'float', required=False, default=1.1, min_val=0.1, max_val=5.0,
                           description='Zoom factor for both videos (1.1 = 110%)'),
                ParameterDef('primary_width_ratio', 'float', required=False, default=0.6, min_val=0.1, max_val=0.9,
                           description='Width ratio for primary video (0.6 = 60%)'),
                ParameterDef('divider_width', 'int', required=False, default=2, min_val=0, max_val=20,
                           description='Width of divider line in pixels'),
                ParameterDef('divider_color', 'str', required=False, default='black',
                           description='Color of divider line (black, white, etc.)'),
                ParameterDef('audio_source', 'str', required=False, default='primary',
                           choices=['primary', 'secondary', 'both'],
                           description='Audio source (primary, secondary, or both)')
            ],
            icon='📹'
        ))

        # ==================== TRANSFORM OPERATIONS ====================

        self.register(OperationDef(
            name='rotate',
            display_name='Rotate',
            category=self.CATEGORY_TRANSFORM,
            description='Rotate video by angle',
            parameters=[
                ParameterDef('angle', 'float', required=True,
                           description='Rotation angle in degrees')
            ],
            icon='🔄'
        ))

        self.register(OperationDef(
            name='flip_horizontal',
            display_name='Flip Horizontal',
            category=self.CATEGORY_TRANSFORM,
            description='Flip video horizontally (mirror)',
            parameters=[],
            icon='↔️'
        ))

        self.register(OperationDef(
            name='flip_vertical',
            display_name='Flip Vertical',
            category=self.CATEGORY_TRANSFORM,
            description='Flip video vertically',
            parameters=[],
            icon='↕️'
        ))

        # ==================== AUDIO OPERATIONS ====================

        self.register(OperationDef(
            name='adjust_volume',
            display_name='Adjust Volume',
            category=self.CATEGORY_AUDIO,
            description='Adjust audio volume level',
            parameters=[
                ParameterDef('volume', 'float', required=True, min_val=0.0, max_val=10.0,
                           description='Volume multiplier (1.0 = 100%, 0.5 = 50%, 2.0 = 200%)')
            ],
            icon='🔊'
        ))

        self.register(OperationDef(
            name='remove_audio',
            display_name='Remove Audio',
            category=self.CATEGORY_AUDIO,
            description='Remove all audio from video',
            parameters=[],
            icon='🔇'
        ))

        self.register(OperationDef(
            name='replace_audio',
            display_name='Replace Audio',
            category=self.CATEGORY_AUDIO,
            description='Replace video audio with new audio file',
            parameters=[
                ParameterDef('audio_path', 'str', required=True,
                           description='Path to audio file'),
                ParameterDef('start_time', 'float', required=False, default=0, min_val=0,
                           description='Start time in seconds')
            ],
            icon='🎵'
        ))

        self.register(OperationDef(
            name='mix_audio',
            display_name='Mix Audio',
            category=self.CATEGORY_AUDIO,
            description='Mix additional audio with existing audio',
            parameters=[
                ParameterDef('audio_path', 'str', required=True,
                           description='Path to audio file'),
                ParameterDef('volume', 'float', required=False, default=0.5, min_val=0.0, max_val=10.0,
                           description='Volume of mixed audio'),
                ParameterDef('start_time', 'float', required=False, default=0, min_val=0,
                           description='Start time in seconds')
            ],
            icon='🎶'
        ))

        # ==================== TEXT & OVERLAY OPERATIONS ====================

        self.register(OperationDef(
            name='add_text',
            display_name='Add Text',
            category=self.CATEGORY_TEXT_OVERLAY,
            description='Add text overlay to video',
            parameters=[
                ParameterDef('text', 'str', required=True,
                           description='Text content'),
                ParameterDef('position', 'tuple', required=False, default=('center', 'bottom'),
                           description='Text position (horizontal, vertical)'),
                ParameterDef('fontsize', 'int', required=False, default=50, min_val=1,
                           description='Font size in pixels'),
                ParameterDef('color', 'str', required=False, default='white',
                           description='Text color'),
                ParameterDef('font', 'str', required=False, default='Arial',
                           description='Font name'),
                ParameterDef('start_time', 'float', required=False, default=0, min_val=0,
                           description='Start time in seconds'),
                ParameterDef('duration', 'float', required=False,
                           description='Duration in seconds (None = full video)')
            ],
            icon='📝'
        ))

        self.register(OperationDef(
            name='add_watermark',
            display_name='Add Watermark',
            category=self.CATEGORY_TEXT_OVERLAY,
            description='Add watermark image to video',
            parameters=[
                ParameterDef('image_path', 'str', required=True,
                           description='Path to watermark image'),
                ParameterDef('position', 'tuple', required=False, default=('right', 'bottom'),
                           description='Watermark position (horizontal, vertical)'),
                ParameterDef('opacity', 'float', required=False, default=1.0, min_val=0.0, max_val=1.0,
                           description='Watermark opacity (0.0 = transparent, 1.0 = opaque)'),
                ParameterDef('size', 'float', required=False, default=0.1, min_val=0.01, max_val=1.0,
                           description='Watermark size as fraction of video width')
            ],
            icon='©️'
        ))

        # ==================== EFFECTS OPERATIONS ====================

        self.register(OperationDef(
            name='fade_in',
            display_name='Fade In',
            category=self.CATEGORY_EFFECTS,
            description='Add fade in effect at start',
            parameters=[
                ParameterDef('duration', 'float', required=False, default=1.0, min_val=0.1,
                           description='Fade duration in seconds')
            ],
            icon='🌅'
        ))

        self.register(OperationDef(
            name='fade_out',
            display_name='Fade Out',
            category=self.CATEGORY_EFFECTS,
            description='Add fade out effect at end',
            parameters=[
                ParameterDef('duration', 'float', required=False, default=1.0, min_val=0.1,
                           description='Fade duration in seconds')
            ],
            icon='🌇'
        ))

        self.register(OperationDef(
            name='apply_filter',
            display_name='Apply Filter',
            category=self.CATEGORY_EFFECTS,
            description='Apply visual filter/effect',
            parameters=[
                ParameterDef('filter_name', 'str', required=True,
                           choices=['grayscale', 'sepia', 'vintage', 'cinematic',
                                   'vignette', 'blur', 'sharpen', 'negative'],
                           description='Filter to apply'),
                ParameterDef('intensity', 'float', required=False, default=1.0, min_val=0.0, max_val=1.0,
                           description='Filter intensity/strength')
            ],
            icon='🎨'
        ))

        logger.info(f"OperationLibrary initialized with {len(self.operations)} operations")

    def register(self, operation: OperationDef):
        """Register an operation"""
        self.operations[operation.name] = operation

    def has_operation(self, name: str) -> bool:
        """Check if operation exists"""
        return name in self.operations

    def get_operation(self, name: str) -> Optional[OperationDef]:
        """Get operation definition by name"""
        return self.operations.get(name)

    def get_all_operations(self) -> List[OperationDef]:
        """Get all registered operations"""
        return list(self.operations.values())

    def get_operations_by_category(self, category: str) -> List[OperationDef]:
        """Get all operations in a category"""
        return [op for op in self.operations.values() if op.category == category]

    def get_categories(self) -> List[str]:
        """Get all unique categories"""
        categories = set(op.category for op in self.operations.values())
        return sorted(list(categories))

    def validate_operation(self, name: str, params: Dict[str, Any]) -> ValidationResult:
        """
        Validate an operation and its parameters

        Args:
            name: Operation name
            params: Operation parameters

        Returns:
            ValidationResult
        """
        result = ValidationResult()

        # Check operation exists
        if not self.has_operation(name):
            result.valid = False
            result.errors.append(f"Unknown operation: {name}")
            return result

        # Validate parameters
        operation = self.get_operation(name)
        valid, errors, warnings = operation.validate_params(params)

        result.valid = valid
        result.errors = errors
        result.warnings = warnings

        return result

    def get_operation_summary(self) -> Dict[str, Any]:
        """Get summary of all operations organized by category"""
        summary = {
            'total_operations': len(self.operations),
            'categories': {}
        }

        for category in self.get_categories():
            ops = self.get_operations_by_category(category)
            summary['categories'][category] = {
                'count': len(ops),
                'operations': [
                    {
                        'name': op.name,
                        'display_name': op.display_name,
                        'description': op.description,
                        'icon': op.icon,
                        'param_count': len(op.parameters)
                    }
                    for op in ops
                ]
            }

        return summary
