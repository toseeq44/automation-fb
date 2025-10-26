"""
modules/video_editor/core/custom_video_player.py
FIXED Integrated Video Player with QObject Inheritance
"""

import cv2
import os
from PyQt5.QtCore import QThread, pyqtSignal, QTimer, QObject
from PyQt5.QtGui import QPixmap, QImage
import numpy as np

from modules.logging.logger import get_logger

logger = get_logger(__name__)


class VideoPlaybackThread(QThread):
    """Lightweight video playback thread for integration"""
    
    # Signals for integration
    frame_ready = pyqtSignal(QPixmap, bool)  # frame, is_before (True=before, False=after)
    position_changed = pyqtSignal(float)      # current time in seconds
    duration_changed = pyqtSignal(float)      # total duration in seconds
    state_changed = pyqtSignal(str)           # "playing", "paused", "stopped"
    
    def __init__(self):
        super().__init__()
        self.video_path = ""
        self.cap = None
        self.playing = False
        self.position = 0.0
        self.duration = 0.0
        self.fps = 30.0
        
    def load_video(self, video_path):
        """Load video file using OpenCV"""
        try:
            logger.info(f"🎥 Loading video: {video_path}")
            
            if not os.path.exists(video_path):
                logger.error(f"Video file not found: {video_path}")
                return False
                
            # Clean up previous video
            if self.cap:
                self.cap.release()
                
            # Open video with OpenCV
            self.cap = cv2.VideoCapture(video_path)
            if not self.cap.isOpened():
                logger.error(f"Failed to open video: {video_path}")
                return False
                
            # Get video properties
            self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
            frame_count = self.cap.get(cv2.CAP_PROP_FRAME_COUNT)
            self.duration = frame_count / self.fps
            self.video_path = video_path
            
            logger.info(f"✅ Video loaded: {self.duration:.2f}s, {self.fps}fps")
            
            # Emit duration
            self.duration_changed.emit(self.duration)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error loading video: {str(e)}")
            return False
            
    def play(self):
        """Start playback - ENHANCED"""
        try:
            print("DEBUG: 🎬 VideoPlaybackThread.play() called")
            
            if self.cap and self.cap.isOpened():
                self.playing = True
                self.state_changed.emit("playing")
                print("DEBUG: ✅ Playback started - playing=True")
            else:
                print("DEBUG: ❌ Cannot play - video not loaded")
                
        except Exception as e:
            print(f"DEBUG: ❌ Error in VideoPlaybackThread.play(): {str(e)}")
        
    def pause(self):
        """Pause playback - ENHANCED"""
        try:
            print("DEBUG: ⏸️ VideoPlaybackThread.pause() called")
            
            self.playing = False
            self.state_changed.emit("paused")
            print("DEBUG: ✅ Playback paused - playing=False")
            
        except Exception as e:
            print(f"DEBUG: ❌ Error in VideoPlaybackThread.pause(): {str(e)}")
        
    def stop(self):
        """Stop playback - ENHANCED"""
        try:
            print("DEBUG: ⏹️ VideoPlaybackThread.stop() called")
            
            self.playing = False
            self.position = 0.0
            if self.cap:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            self.state_changed.emit("stopped")
            print("DEBUG: ✅ Playback stopped - reset to start")
            
        except Exception as e:
            print(f"DEBUG: ❌ Error in VideoPlaybackThread.stop(): {str(e)}")
    def seek(self, position_seconds):
        """Seek to specific position in seconds"""
        try:
            if self.cap and self.cap.isOpened():
                frame_number = int(position_seconds * self.fps)
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
                
                # Read and emit the frame immediately
                ret, frame = self.cap.read()
                if ret:
                    pixmap = self.cv2_to_pixmap(frame)
                    self.frame_ready.emit(pixmap, True)   # Before window
                    self.frame_ready.emit(pixmap, False)  # After window
                    self.position = position_seconds
                    self.position_changed.emit(self.position)
                    
        except Exception as e:
            logger.error(f"Error seeking video: {str(e)}")
            
    def run(self):
        """Main playback loop - runs in separate thread"""
        while True:
            try:
                if self.playing and self.cap and self.cap.isOpened():
                    ret, frame = self.cap.read()
                    if ret:
                        # Convert frame to QPixmap
                        pixmap = self.cv2_to_pixmap(frame)
                        
                        # Update current position
                        self.position = self.cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
                        
                        # Emit frame to both preview windows
                        self.frame_ready.emit(pixmap, True)   # Before window
                        self.frame_ready.emit(pixmap, False)  # After window
                        self.position_changed.emit(self.position)
                        
                        # Control playback speed
                        delay = max(1, int(1000 / self.fps))
                        self.msleep(delay)
                    else:
                        # End of video reached
                        self.playing = False
                        self.seek(0)  # Reset to start
                        self.state_changed.emit("stopped")
                else:
                    # Small delay when not playing
                    self.msleep(50)
                    
            except Exception as e:
                logger.error(f"Error in playback loop: {str(e)}")
                self.msleep(50)
                
    def cv2_to_pixmap(self, frame):
        """Convert OpenCV frame to QPixmap"""
        try:
            if frame is None:
                # Return blank pixmap
                return QPixmap(640, 480)
                
            # Convert BGR to RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Get frame dimensions
            h, w, ch = frame_rgb.shape
            bytes_per_line = ch * w
            
            # Create QImage
            q_image = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
            
            return QPixmap.fromImage(q_image)
            
        except Exception as e:
            logger.error(f"Error converting frame to pixmap: {str(e)}")
            return QPixmap(640, 480)
            
    def cleanup(self):
        """Clean up resources"""
        self.playing = False
        if self.cap:
            self.cap.release()
            self.cap = None


class IntegratedVideoPlayer(QObject):  # ✅ FIX: Inherit from QObject
    """
    Lightweight video player for integration with dual preview
    No UI - just playback functionality
    """
    
    # Signals - MUST be class attributes
    frame_ready = pyqtSignal(QPixmap, bool)  # frame, is_before
    position_changed = pyqtSignal(float)      # current time in seconds
    duration_changed = pyqtSignal(float)      # total duration in seconds
    state_changed = pyqtSignal(str)           # "playing", "paused", "stopped"
    
    def __init__(self):
        super().__init__()  # ✅ FIX: Call QObject constructor
        
        self.thread = VideoPlaybackThread()
        
        # Connect signals
        self.thread.frame_ready.connect(self.frame_ready)
        self.thread.position_changed.connect(self.position_changed)
        self.thread.duration_changed.connect(self.duration_changed)
        self.thread.state_changed.connect(self.state_changed)
        
        # Start the thread
        self.thread.start()
        
    def load_video(self, video_path):
        """Load video file"""
        return self.thread.load_video(video_path)
        
    def play(self):
        """Start playback"""
        self.thread.play()
        
    def pause(self):
        """Pause playback"""
        self.thread.pause()
        
    def stop(self):
        """Stop playback"""
        self.thread.stop()
        
    def seek(self, position_seconds):
        """Seek to position in seconds"""
        self.thread.seek(position_seconds)
        
    def get_duration(self):
        """Get video duration in seconds"""
        return self.thread.duration
        
    def get_position(self):
        """Get current position in seconds"""
        return self.thread.position
        
    def cleanup(self):
        """Clean up resources"""
        self.thread.cleanup()