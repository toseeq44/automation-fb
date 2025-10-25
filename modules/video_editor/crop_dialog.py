"""
modules/video_editor/crop_dialog.py
Interactive Crop Dialog - CapCut Style
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSpinBox, QComboBox, QGraphicsView, QGraphicsScene,
    QGraphicsRectItem, QGroupBox, QGridLayout
)
from PyQt5.QtCore import Qt, QRectF, QPointF
from PyQt5.QtGui import QPen, QBrush, QColor, QPixmap, QPainter

from modules.logging.logger import get_logger

logger = get_logger(__name__)


class CropDialog(QDialog):
    """
    Interactive crop dialog with visual preview
    """

    def __init__(self, video_path: str, video_info: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🔲 Crop Video")
        self.setMinimumSize(900, 700)
        self.setModal(True)

        self.video_path = video_path
        self.video_info = video_info
        self.video_width = video_info.get('width', 1920)
        self.video_height = video_info.get('height', 1080)

        # Crop values
        self.crop_x = 0
        self.crop_y = 0
        self.crop_width = self.video_width
        self.crop_height = self.video_height

        self.result = None  # Will store crop parameters

        self.init_ui()
        self.load_video_preview()

    def init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title
        title = QLabel("🔲 Crop Video - Drag to Select Area")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #00D9FF;")
        layout.addWidget(title)

        # Main content
        content_layout = QHBoxLayout()
        content_layout.setSpacing(20)

        # Left: Preview
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout()

        # Graphics view for visual crop selection
        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.view.setMinimumSize(600, 400)
        self.view.setStyleSheet("background-color: #000000; border: 2px solid #3A3A3A;")

        preview_layout.addWidget(self.view)

        # Video info
        info_text = f"Original: {self.video_width} x {self.video_height}"
        info_label = QLabel(info_text)
        info_label.setStyleSheet("color: #888888; padding: 5px;")
        preview_layout.addWidget(info_label)

        preview_group.setLayout(preview_layout)
        content_layout.addWidget(preview_group, 2)

        # Right: Controls
        controls_group = QGroupBox("Crop Settings")
        controls_layout = QVBoxLayout()
        controls_layout.setSpacing(15)

        # Aspect Ratio Presets
        preset_label = QLabel("📐 Aspect Ratio Presets:")
        preset_label.setStyleSheet("font-weight: bold; color: #00D9FF;")
        controls_layout.addWidget(preset_label)

        presets = [
            ("Original", "original"),
            ("Square (1:1)", "1:1"),
            ("Vertical (9:16)", "9:16"),
            ("Horizontal (16:9)", "16:9"),
            ("Instagram Story (9:16)", "9:16"),
            ("YouTube (16:9)", "16:9"),
            ("TikTok (9:16)", "9:16"),
        ]

        for name, ratio in presets:
            btn = QPushButton(name)
            btn.clicked.connect(lambda checked, r=ratio: self.apply_aspect_ratio(r))
            controls_layout.addWidget(btn)

        controls_layout.addSpacing(20)

        # Manual Input
        manual_label = QLabel("✏️ Manual Crop Values:")
        manual_label.setStyleSheet("font-weight: bold; color: #00D9FF;")
        controls_layout.addWidget(manual_label)

        grid = QGridLayout()
        grid.setSpacing(10)

        # X
        grid.addWidget(QLabel("X (Left):"), 0, 0)
        self.x_spin = QSpinBox()
        self.x_spin.setRange(0, self.video_width)
        self.x_spin.setValue(0)
        self.x_spin.valueChanged.connect(self.update_crop_from_inputs)
        grid.addWidget(self.x_spin, 0, 1)

        # Y
        grid.addWidget(QLabel("Y (Top):"), 1, 0)
        self.y_spin = QSpinBox()
        self.y_spin.setRange(0, self.video_height)
        self.y_spin.setValue(0)
        self.y_spin.valueChanged.connect(self.update_crop_from_inputs)
        grid.addWidget(self.y_spin, 1, 1)

        # Width
        grid.addWidget(QLabel("Width:"), 2, 0)
        self.width_spin = QSpinBox()
        self.width_spin.setRange(1, self.video_width)
        self.width_spin.setValue(self.video_width)
        self.width_spin.valueChanged.connect(self.update_crop_from_inputs)
        grid.addWidget(self.width_spin, 2, 1)

        # Height
        grid.addWidget(QLabel("Height:"), 3, 0)
        self.height_spin = QSpinBox()
        self.height_spin.setRange(1, self.video_height)
        self.height_spin.setValue(self.video_height)
        self.height_spin.valueChanged.connect(self.update_crop_from_inputs)
        grid.addWidget(self.height_spin, 3, 1)

        controls_layout.addLayout(grid)

        # Output size preview
        self.output_label = QLabel(f"Output: {self.video_width} x {self.video_height}")
        self.output_label.setStyleSheet("color: #00D9FF; font-weight: bold; padding: 10px;")
        controls_layout.addWidget(self.output_label)

        controls_layout.addStretch()

        controls_group.setLayout(controls_layout)
        content_layout.addWidget(controls_group, 1)

        layout.addLayout(content_layout)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("❌ Cancel")
        cancel_btn.setStyleSheet("background-color: #5A5A5A;")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        apply_btn = QPushButton("✅ Apply Crop")
        apply_btn.setStyleSheet("background-color: #27AE60; padding: 10px 25px; font-size: 14px;")
        apply_btn.clicked.connect(self.apply_crop)
        button_layout.addWidget(apply_btn)

        layout.addLayout(button_layout)

        self.setLayout(layout)

        # Apply theme
        self.setStyleSheet("""
            QDialog {
                background-color: #1E1E1E;
                color: #FFFFFF;
            }
            QPushButton {
                background-color: #0078D4;
                color: #FFFFFF;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1084D8;
            }
            QGroupBox {
                border: 2px solid #3A3A3A;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 16px;
                font-weight: bold;
                color: #00D9FF;
            }
            QSpinBox {
                background-color: #2D2D2D;
                border: 1px solid #3A3A3A;
                border-radius: 4px;
                padding: 6px;
                color: #FFFFFF;
            }
            QLabel {
                color: #FFFFFF;
            }
        """)

    def load_video_preview(self):
        """Load video frame for preview"""
        try:
            # Try to load thumbnail
            from modules.video_editor.video_utils import get_video_first_frame

            thumb_path = get_video_first_frame(self.video_path, (600, 400))
            if thumb_path:
                pixmap = QPixmap(thumb_path)
                if not pixmap.isNull():
                    # Add pixmap to scene
                    self.scene.addPixmap(pixmap)

                    # Add crop rectangle
                    pen = QPen(QColor(0, 217, 255), 3, Qt.DashLine)
                    self.crop_rect = self.scene.addRect(
                        0, 0, pixmap.width(), pixmap.height(),
                        pen
                    )

                    # Scale to fit
                    self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)
                    return

        except Exception as e:
            logger.error(f"Failed to load preview: {e}")

        # Fallback: Draw placeholder
        self.scene.addText("Video Preview\n\nUse controls to set crop area")

    def apply_aspect_ratio(self, ratio: str):
        """Apply aspect ratio preset"""
        if ratio == "original":
            self.crop_x = 0
            self.crop_y = 0
            self.crop_width = self.video_width
            self.crop_height = self.video_height

        elif ratio == "1:1":
            # Square - crop to smallest dimension
            size = min(self.video_width, self.video_height)
            self.crop_width = size
            self.crop_height = size
            self.crop_x = (self.video_width - size) // 2
            self.crop_y = (self.video_height - size) // 2

        elif ratio == "9:16":
            # Vertical
            if self.video_width / self.video_height > 9 / 16:
                # Video is wider, crop width
                self.crop_height = self.video_height
                self.crop_width = int(self.video_height * 9 / 16)
                self.crop_x = (self.video_width - self.crop_width) // 2
                self.crop_y = 0
            else:
                # Video is taller, crop height
                self.crop_width = self.video_width
                self.crop_height = int(self.video_width * 16 / 9)
                self.crop_x = 0
                self.crop_y = (self.video_height - self.crop_height) // 2

        elif ratio == "16:9":
            # Horizontal
            if self.video_width / self.video_height > 16 / 9:
                # Video is wider, crop width
                self.crop_height = self.video_height
                self.crop_width = int(self.video_height * 16 / 9)
                self.crop_x = (self.video_width - self.crop_width) // 2
                self.crop_y = 0
            else:
                # Video is taller, crop height
                self.crop_width = self.video_width
                self.crop_height = int(self.video_width * 9 / 16)
                self.crop_x = 0
                self.crop_y = (self.video_height - self.crop_height) // 2

        self.update_ui_from_crop()

    def update_crop_from_inputs(self):
        """Update crop from manual inputs"""
        self.crop_x = self.x_spin.value()
        self.crop_y = self.y_spin.value()
        self.crop_width = self.width_spin.value()
        self.crop_height = self.height_spin.value()

        # Update output label
        self.output_label.setText(f"Output: {self.crop_width} x {self.crop_height}")

    def update_ui_from_crop(self):
        """Update UI controls from crop values"""
        self.x_spin.setValue(self.crop_x)
        self.y_spin.setValue(self.crop_y)
        self.width_spin.setValue(self.crop_width)
        self.height_spin.setValue(self.crop_height)

        self.output_label.setText(f"Output: {self.crop_width} x {self.crop_height}")

    def apply_crop(self):
        """Apply crop and close dialog"""
        # Calculate final crop coordinates
        x1 = self.crop_x
        y1 = self.crop_y
        x2 = self.crop_x + self.crop_width
        y2 = self.crop_y + self.crop_height

        # Validate
        if x2 > self.video_width:
            x2 = self.video_width
        if y2 > self.video_height:
            y2 = self.video_height

        self.result = {
            'x1': x1,
            'y1': y1,
            'x2': x2,
            'y2': y2,
            'width': x2 - x1,
            'height': y2 - y1
        }

        self.accept()

    def get_crop_params(self):
        """Get crop parameters"""
        return self.result
