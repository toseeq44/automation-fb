"""
Frame Analyzer for Title Generator
Extracts frames from video and analyzes content
"""

import os
import tempfile
from pathlib import Path
from typing import Dict, List, Optional
from modules.logging.logger import get_logger

logger = get_logger(__name__)


class FrameAnalyzer:
    """Analyze video frames to extract content information"""

    def __init__(self):
        """Initialize frame analyzer"""
        self.temp_dir = tempfile.gettempdir()

    def analyze_video(self, video_path: str) -> Dict:
        """
        Analyze video frames and extract content information

        Args:
            video_path: Path to video file

        Returns:
            Dictionary with analysis results
        """
        try:
            # Extract key frames
            frames = self._extract_key_frames(video_path)

            # Analyze frames
            analysis = {
                'text_found': [],
                'frame_count': len(frames),
                'has_text': False
            }

            # Extract text from frames
            for frame_path in frames:
                text = self._extract_text_from_frame(frame_path)
                if text:
                    analysis['text_found'].extend(text)
                    analysis['has_text'] = True

            # Clean up temp frames
            for frame_path in frames:
                try:
                    os.remove(frame_path)
                except:
                    pass

            return analysis

        except Exception as e:
            logger.error(f"Frame analysis failed: {e}")
            return {
                'text_found': [],
                'frame_count': 0,
                'has_text': False
            }

    def _extract_key_frames(self, video_path: str, num_frames: int = 3) -> List[str]:
        """
        Extract key frames from video

        Args:
            video_path: Path to video
            num_frames: Number of frames to extract

        Returns:
            List of frame file paths
        """
        try:
            from moviepy import VideoFileClip

            frames = []
            clip = VideoFileClip(video_path)
            duration = clip.duration

            if duration <= 0:
                clip.close()
                return []

            # Extract frames at different timestamps
            timestamps = []
            if duration < 10:
                # Short video - just middle frame
                timestamps = [duration / 2]
            else:
                # Longer video - start, middle, end
                timestamps = [
                    duration * 0.2,  # 20% into video
                    duration * 0.5,  # Middle
                    duration * 0.8   # 80% into video
                ]

            for i, t in enumerate(timestamps[:num_frames]):
                try:
                    frame = clip.get_frame(t)

                    # Save frame to temp file
                    frame_path = os.path.join(
                        self.temp_dir,
                        f"frame_{i}_{os.getpid()}.jpg"
                    )

                    from PIL import Image
                    img = Image.fromarray(frame)
                    img.save(frame_path, quality=85)
                    frames.append(frame_path)

                except Exception as e:
                    logger.warning(f"Failed to extract frame at {t}s: {e}")

            clip.close()
            return frames

        except Exception as e:
            logger.error(f"Frame extraction failed: {e}")
            return []

    def _extract_text_from_frame(self, frame_path: str) -> List[str]:
        """
        Extract text from frame using OCR

        Args:
            frame_path: Path to frame image

        Returns:
            List of extracted text strings
        """
        try:
            import pytesseract
            from PIL import Image

            # Open image
            img = Image.open(frame_path)

            # Extract text
            text = pytesseract.image_to_string(img)

            # Clean and filter text
            lines = [line.strip() for line in text.split('\n') if line.strip()]

            # Filter meaningful text (at least 3 chars, not just numbers/symbols)
            meaningful_text = []
            for line in lines:
                # Remove pure numbers and short text
                if len(line) >= 3 and any(c.isalpha() for c in line):
                    meaningful_text.append(line)

            return meaningful_text

        except ImportError:
            # pytesseract not installed
            logger.debug("pytesseract not available for OCR")
            return []
        except Exception as e:
            logger.debug(f"OCR failed: {e}")
            return []

    def get_video_metadata(self, video_path: str) -> Dict:
        """
        Get detailed video metadata

        Args:
            video_path: Path to video

        Returns:
            Dictionary with metadata
        """
        try:
            from moviepy import VideoFileClip

            metadata = {}

            with VideoFileClip(video_path) as clip:
                metadata['duration'] = clip.duration
                metadata['fps'] = clip.fps
                metadata['size'] = clip.size
                metadata['width'] = clip.size[0] if clip.size else 0
                metadata['height'] = clip.size[1] if clip.size else 0
                metadata['has_audio'] = clip.audio is not None

            return metadata

        except Exception as e:
            logger.error(f"Metadata extraction failed: {e}")
            return {}
