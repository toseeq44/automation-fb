"""
modules/video_editor/videos_merger/folder_item_widget.py
Widget for displaying folder item in bulk merge list
"""

from pathlib import Path
from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QFrame
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
from .utils import get_videos_from_folder
from modules.logging.logger import get_logger

logger = get_logger(__name__)


class FolderItemWidget(QFrame):
    """Widget representing a folder in bulk merge list"""

    # Signals
    remove_clicked = pyqtSignal(object)  # Emits self
    folder_clicked = pyqtSignal(str)  # Folder path

    def __init__(self, folder_path: str, index: int):
        super().__init__()

        self.folder_path = folder_path
        self.index = index

        # Get video count
        self.video_paths = get_videos_from_folder(folder_path)
        self.video_count = len(self.video_paths)

        self.init_ui()

    def init_ui(self):
        """Initialize UI"""
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Raised)
        self.setLineWidth(1)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(5)

        # Top row: Index, folder name, video count, and remove button
        top_layout = QHBoxLayout()

        # Index label
        index_label = QLabel(f"{self.index + 1}.")
        index_label.setFont(QFont("Arial", 12, QFont.Bold))
        index_label.setFixedWidth(30)
        top_layout.addWidget(index_label)

        # Folder icon and name
        folder_name = Path(self.folder_path).name
        folder_label = QLabel(f"📁 {folder_name}")
        folder_label.setFont(QFont("Arial", 10, QFont.Bold))
        folder_label.setWordWrap(True)
        folder_label.setCursor(Qt.PointingHandCursor)
        folder_label.mousePressEvent = lambda e: self.folder_clicked.emit(self.folder_path)
        top_layout.addWidget(folder_label, 1)

        # Video count badge
        count_label = QLabel(f"[{self.video_count} videos]")
        count_label.setStyleSheet("""
            QLabel {
                background-color: #0066cc;
                color: white;
                padding: 2px 8px;
                border-radius: 10px;
                font-size: 9pt;
                font-weight: bold;
            }
        """)
        count_label.setFixedHeight(20)
        top_layout.addWidget(count_label)

        # Remove button
        remove_btn = QPushButton("×")
        remove_btn.setFixedSize(30, 30)
        remove_btn.setToolTip("Remove folder")
        remove_btn.setStyleSheet("QPushButton { color: red; font-size: 18px; font-weight: bold; }")
        remove_btn.clicked.connect(lambda: self.remove_clicked.emit(self))
        top_layout.addWidget(remove_btn)

        main_layout.addLayout(top_layout)

        # Folder path (small text)
        path_label = QLabel(self.folder_path)
        path_label.setStyleSheet("color: #888; font-size: 8pt;")
        path_label.setWordWrap(True)
        main_layout.addWidget(path_label)

        # Warning if no videos
        if self.video_count == 0:
            warning_label = QLabel("⚠️ No videos found in this folder")
            warning_label.setStyleSheet("color: #ff6600; font-size: 9pt; font-weight: bold;")
            main_layout.addWidget(warning_label)

        self.setLayout(main_layout)

        # Dark theme style
        self.setStyleSheet("""
            FolderItemWidget {
                background-color: #252525;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
            }
            FolderItemWidget:hover {
                background-color: #2f2f2f;
                border: 1px solid #0066cc;
            }
            QLabel {
                color: #e0e0e0;
                background-color: transparent;
            }
            QPushButton {
                background-color: #2a2a2a;
                color: #e0e0e0;
                border: 1px solid #3a3a3a;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #353535;
                border-color: #0066cc;
            }
        """)

    def get_folder_path(self) -> str:
        """Get folder path"""
        return self.folder_path

    def get_video_count(self) -> int:
        """Get video count"""
        return self.video_count

    def get_video_paths(self):
        """Get list of video paths"""
        return self.video_paths

    def set_index(self, index: int):
        """Update index"""
        self.index = index
