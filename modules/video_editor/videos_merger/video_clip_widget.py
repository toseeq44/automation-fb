"""
modules/video_editor/videos_merger/video_clip_widget.py
Widget for displaying individual video clip in merge list
"""

from pathlib import Path
from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QComboBox, QDoubleSpinBox, QFrame
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
from modules.logging.logger import get_logger

logger = get_logger(__name__)

# Try to import MoviePy (MoviePy 2.x structure)
try:
    from moviepy import VideoFileClip
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False
    logger.warning("MoviePy not available. Video info will not be loaded.")


class VideoClipWidget(QFrame):
    """Widget representing a single video clip in the merge list"""

    # Signals
    remove_clicked = pyqtSignal(object)  # Emits self
    move_up_clicked = pyqtSignal(object)
    move_down_clicked = pyqtSignal(object)
    transition_changed = pyqtSignal(str)  # New transition type
    transition_duration_changed = pyqtSignal(float)  # New duration

    # Available transitions
    TRANSITIONS = [
        ('Crossfade', 'crossfade'),
        ('Fade', 'fade'),
        ('Slide Left', 'slide_left'),
        ('Slide Right', 'slide_right'),
        ('Slide Up', 'slide_up'),
        ('Slide Down', 'slide_down'),
        ('Zoom In', 'zoom_in'),
        ('Zoom Out', 'zoom_out'),
        ('Wipe', 'wipe'),
        ('None', 'none')
    ]

    def __init__(self, video_path: str, index: int, show_transition: bool = True):
        super().__init__()

        self.video_path = video_path
        self.index = index
        self.show_transition = show_transition

        # Video info
        self.duration = 0.0
        self.fps = 0
        self.width = 0
        self.height = 0
        self.trimmed_duration = 0.0

        # Load video info
        self._load_video_info()

        self.init_ui()

    def _load_video_info(self):
        """Load video information"""
        if not MOVIEPY_AVAILABLE:
            logger.warning("MoviePy not available - using default video info")
            self.duration = 60.0  # Default 1 minute
            self.fps = 30
            self.width = 1920
            self.height = 1080
            self.trimmed_duration = self.duration
            return

        try:
            clip = VideoFileClip(self.video_path)
            self.duration = clip.duration
            self.fps = clip.fps
            self.width, self.height = clip.size
            self.trimmed_duration = self.duration
            clip.close()
        except Exception as e:
            logger.error(f"Error loading video info: {e}")

    def init_ui(self):
        """Initialize UI"""
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Raised)
        self.setLineWidth(1)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        # Top row: Index, filename, and remove button
        top_layout = QHBoxLayout()

        # Index label
        index_label = QLabel(f"{self.index + 1}.")
        index_label.setFont(QFont("Arial", 14, QFont.Bold))
        index_label.setFixedWidth(30)
        top_layout.addWidget(index_label)

        # Filename
        filename = Path(self.video_path).name
        filename_label = QLabel(f"📹 {filename}")
        filename_label.setFont(QFont("Arial", 10, QFont.Bold))
        filename_label.setWordWrap(True)
        top_layout.addWidget(filename_label, 1)

        # Move up button
        self.move_up_btn = QPushButton("↑")
        self.move_up_btn.setFixedSize(30, 30)
        self.move_up_btn.setToolTip("Move up")
        self.move_up_btn.clicked.connect(lambda: self.move_up_clicked.emit(self))
        top_layout.addWidget(self.move_up_btn)

        # Move down button
        self.move_down_btn = QPushButton("↓")
        self.move_down_btn.setFixedSize(30, 30)
        self.move_down_btn.setToolTip("Move down")
        self.move_down_btn.clicked.connect(lambda: self.move_down_clicked.emit(self))
        top_layout.addWidget(self.move_down_btn)

        # Remove button
        remove_btn = QPushButton("×")
        remove_btn.setFixedSize(30, 30)
        remove_btn.setToolTip("Remove video")
        remove_btn.setStyleSheet("QPushButton { color: red; font-size: 18px; font-weight: bold; }")
        remove_btn.clicked.connect(lambda: self.remove_clicked.emit(self))
        top_layout.addWidget(remove_btn)

        main_layout.addLayout(top_layout)

        # Video info row
        info_text = f"⏱️ {self._format_duration(self.duration)}  |  " \
                    f"📐 {self.width}x{self.height}  |  " \
                    f"🎬 {self.fps:.0f}fps"
        info_label = QLabel(info_text)
        info_label.setStyleSheet("color: #666; font-size: 9pt;")
        main_layout.addWidget(info_label)

        # Trimmed duration (updated when trim settings change)
        self.trimmed_label = QLabel(f"After trim: {self._format_duration(self.trimmed_duration)}")
        self.trimmed_label.setStyleSheet("color: #0066cc; font-size: 9pt; font-weight: bold;")
        main_layout.addWidget(self.trimmed_label)

        # Transition row (if enabled)
        if self.show_transition:
            transition_layout = QHBoxLayout()

            transition_label = QLabel("🔁 Transition:")
            transition_layout.addWidget(transition_label)

            # Transition type combo
            self.transition_combo = QComboBox()
            for display_name, value in self.TRANSITIONS:
                self.transition_combo.addItem(display_name, value)
            self.transition_combo.setCurrentIndex(0)  # Default: Crossfade
            self.transition_combo.currentIndexChanged.connect(self._on_transition_changed)
            transition_layout.addWidget(self.transition_combo, 1)

            # Duration spinbox
            self.duration_spin = QDoubleSpinBox()
            self.duration_spin.setRange(0.1, 5.0)
            self.duration_spin.setSingleStep(0.1)
            self.duration_spin.setValue(1.0)
            self.duration_spin.setSuffix("s")
            self.duration_spin.setFixedWidth(80)
            self.duration_spin.valueChanged.connect(self._on_duration_changed)
            transition_layout.addWidget(self.duration_spin)

            main_layout.addLayout(transition_layout)

        self.setLayout(main_layout)

        # Style
        self.setStyleSheet("""
            VideoClipWidget {
                background-color: #f5f5f5;
                border: 1px solid #ccc;
                border-radius: 5px;
            }
            VideoClipWidget:hover {
                background-color: #e8f4f8;
                border: 1px solid #0066cc;
            }
        """)

    def _format_duration(self, seconds: float) -> str:
        """Format duration as MM:SS"""
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins:02d}:{secs:02d}"

    def _on_transition_changed(self):
        """Transition type changed"""
        transition = self.transition_combo.currentData()
        self.transition_changed.emit(transition)

    def _on_duration_changed(self):
        """Transition duration changed"""
        duration = self.duration_spin.value()
        self.transition_duration_changed.emit(duration)

    def update_trimmed_duration(self, trim_start: float, trim_end: float):
        """
        Update trimmed duration display

        Args:
            trim_start: Seconds to trim from start
            trim_end: Seconds to trim from end
        """
        new_duration = max(0, self.duration - trim_start - trim_end)
        self.trimmed_duration = new_duration

        if trim_start > 0 or trim_end > 0:
            self.trimmed_label.setText(
                f"After trim: {self._format_duration(new_duration)} "
                f"(✂️ -{trim_start:.0f}s start, -{trim_end:.0f}s end)"
            )
            self.trimmed_label.setVisible(True)
        else:
            self.trimmed_label.setVisible(False)

    def get_transition(self) -> str:
        """Get selected transition type"""
        if self.show_transition:
            return self.transition_combo.currentData()
        return 'crossfade'

    def get_transition_duration(self) -> float:
        """Get transition duration"""
        if self.show_transition:
            return self.duration_spin.value()
        return 1.0

    def set_transition(self, transition_type: str):
        """Set transition type"""
        if self.show_transition:
            for i in range(self.transition_combo.count()):
                if self.transition_combo.itemData(i) == transition_type:
                    self.transition_combo.setCurrentIndex(i)
                    break

    def set_transition_duration(self, duration: float):
        """Set transition duration"""
        if self.show_transition:
            self.duration_spin.setValue(duration)

    def set_index(self, index: int):
        """Update index display"""
        self.index = index
        # Update index label if needed (would need to store reference)

    def get_video_path(self) -> str:
        """Get video file path"""
        return self.video_path

    def get_duration(self) -> float:
        """Get original duration"""
        return self.duration

    def get_trimmed_duration(self) -> float:
        """Get trimmed duration"""
        return self.trimmed_duration
