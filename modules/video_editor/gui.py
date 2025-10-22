"""
modules/video_editor/gui.py
Placeholder for Video Editor module.
"""
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
from PyQt5.QtCore import Qt

class VideoEditorPage(QWidget):
    def __init__(self, back_callback=None):
        super().__init__()
        self.back_callback = back_callback
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(20)
        layout.setContentsMargins(15, 15, 15, 15)

        self.setStyleSheet("background-color: #23272A; color: #F5F6F5;")

        title = QLabel("✂️ Video Editor (Coming Soon)")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #1ABC9C;")
        layout.addWidget(title)

        message = QLabel("This feature is under development.")
        message.setStyleSheet("font-size: 16px;")
        layout.addWidget(message)

        back_btn = QPushButton("⬅ Back")
        back_btn.setStyleSheet("""
            QPushButton {
                background-color: #1ABC9C;
                color: #F5F6F5;
                border: none;
                padding: 10px 20px;
                border-radius: 8px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #16A085;
            }
            QPushButton:pressed {
                background-color: #128C7E;
            }
        """)
        back_btn.clicked.connect(self.back_callback if self.back_callback else lambda: None)
        layout.addWidget(back_btn)

        layout.addStretch()
        self.setLayout(layout)