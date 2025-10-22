"""
main.py
Main application to launch the Video Tool Suite.
"""
import sys
from PyQt5.QtWidgets import QApplication
from gui import VideoToolSuiteGUI

def main():
    """Launch the Video Tool Suite application"""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # Modern look across platforms
    window = VideoToolSuiteGUI()
    window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()