"""
Frame Analyzer for Title Generator
Extracts frames from video and analyzes content using advanced OCR
Implements professional-grade frame extraction and text detection
"""

import os
import tempfile
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from modules.logging.logger import get_logger

logger = get_logger(__name__)


class FrameAnalyzer:
    """Analyze video frames to extract content information using advanced OCR"""

    def __init__(self):
        """Initialize frame analyzer"""
        self.temp_dir = tempfile.gettempdir()

        # OCR configuration for better accuracy
        self.ocr_config = '--psm 11 --oem 3'  # PSM 11: Sparse text, OEM 3: Default LSTM

    def analyze_video(self, video_path: str) -> Dict:
        """
        Analyze video frames and extract content information
        Uses 9 frames for comprehensive analysis

        Args:
            video_path: Path to video file

        Returns:
            Dictionary with analysis results
        """
        try:
            # Extract 9 key frames (professional approach)
            logger.info("Extracting 9 key frames for comprehensive analysis...")
            frames = self._extract_key_frames(video_path, num_frames=9)

            # Analyze frames
            analysis = {
                'text_found': [],
                'keywords': [],
                'actions': [],
                'entities': [],
                'frame_count': len(frames),
                'has_text': False,
                'quality_frames': 0
            }

            # Extract text from frames
            all_text = []
            for i, frame_path in enumerate(frames):
                logger.debug(f"Processing frame {i+1}/{len(frames)}")
                text = self._extract_text_from_frame(frame_path)
                if text:
                    all_text.extend(text)
                    analysis['has_text'] = True
                    analysis['quality_frames'] += 1

            # Process all extracted text
            if all_text:
                # Remove duplicates while preserving order
                unique_text = list(dict.fromkeys(all_text))
                analysis['text_found'] = unique_text[:20]  # Limit to top 20

                # Extract keywords (words appearing multiple times)
                analysis['keywords'] = self._extract_keywords(all_text)

                # Extract action words
                analysis['actions'] = self._extract_actions(all_text)

                # Extract entities (names, places)
                analysis['entities'] = self._extract_entities(all_text)

            logger.info(f"Analysis complete: {len(analysis['text_found'])} unique texts found")

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
                'keywords': [],
                'actions': [],
                'entities': [],
                'frame_count': 0,
                'has_text': False,
                'quality_frames': 0
            }

    def _extract_key_frames(self, video_path: str, num_frames: int = 9) -> List[str]:
        """
        Extract key frames from video at strategic positions
        Professional approach: Extract 9 frames for comprehensive coverage

        Args:
            video_path: Path to video
            num_frames: Number of frames to extract (default: 9)

        Returns:
            List of high-quality frame file paths
        """
        try:
            from moviepy import VideoFileClip
            from PIL import Image

            frames = []
            clip = VideoFileClip(video_path)
            duration = clip.duration

            if duration <= 0:
                clip.close()
                return []

            # Calculate timestamps for frame extraction
            # Professional approach: Cover entire video evenly
            timestamps = []

            if duration < 5:
                # Very short video - fewer frames
                timestamps = [duration * 0.5]  # Just middle
            elif duration < 15:
                # Short video - 3 frames
                timestamps = [
                    duration * 0.25,
                    duration * 0.5,
                    duration * 0.75
                ]
            else:
                # Normal/long video - 9 frames for comprehensive analysis
                # Extract at: 10%, 20%, 30%, 40%, 50%, 60%, 70%, 80%, 90%
                timestamps = [
                    duration * 0.1,
                    duration * 0.2,
                    duration * 0.3,
                    duration * 0.4,
                    duration * 0.5,
                    duration * 0.6,
                    duration * 0.7,
                    duration * 0.8,
                    duration * 0.9
                ]

            # Extract frames with blur detection
            for i, t in enumerate(timestamps[:num_frames]):
                try:
                    frame = clip.get_frame(t)

                    # Check if frame is blurry (skip if too blurry)
                    if not self._is_frame_blurry(frame):
                        # Save high-quality frame
                        frame_path = os.path.join(
                            self.temp_dir,
                            f"frame_{i}_{os.getpid()}.jpg"
                        )

                        img = Image.fromarray(frame)
                        # Save at higher quality for better OCR
                        img.save(frame_path, quality=95, dpi=(300, 300))
                        frames.append(frame_path)
                        logger.debug(f"Extracted quality frame at {t:.2f}s")
                    else:
                        logger.debug(f"Skipped blurry frame at {t:.2f}s")

                except Exception as e:
                    logger.warning(f"Failed to extract frame at {t}s: {e}")

            clip.close()
            logger.info(f"Extracted {len(frames)} quality frames from video")
            return frames

        except Exception as e:
            logger.error(f"Frame extraction failed: {e}")
            return []

    def _is_frame_blurry(self, frame: np.ndarray, threshold: float = 100.0) -> bool:
        """
        Detect if frame is too blurry using Laplacian variance
        Professional approach from PyImageSearch

        Args:
            frame: Frame array
            threshold: Blur threshold (lower = more blurry)

        Returns:
            True if frame is blurry
        """
        try:
            # Convert to grayscale
            if len(frame.shape) == 3:
                # RGB to grayscale
                gray = np.dot(frame[..., :3], [0.299, 0.587, 0.114]).astype(np.uint8)
            else:
                gray = frame

            # Compute Laplacian variance (blur detection)
            # Higher variance = sharper image
            laplacian_var = self._laplacian_variance(gray)

            return laplacian_var < threshold

        except Exception as e:
            logger.debug(f"Blur detection failed: {e}")
            return False  # If detection fails, assume frame is OK

    def _laplacian_variance(self, image: np.ndarray) -> float:
        """
        Calculate Laplacian variance for blur detection

        Args:
            image: Grayscale image array

        Returns:
            Variance value
        """
        try:
            # Simple Laplacian kernel
            kernel = np.array([[0, 1, 0],
                             [1, -4, 1],
                             [0, 1, 0]])

            # Compute Laplacian
            from scipy import signal
            laplacian = signal.convolve2d(image, kernel, mode='same', boundary='symm')

            # Return variance
            return float(np.var(laplacian))

        except ImportError:
            # scipy not available, use simple approximation
            # Calculate variance of pixel differences
            diff_x = np.diff(image, axis=1)
            diff_y = np.diff(image, axis=0)
            variance = np.var(diff_x) + np.var(diff_y)
            return float(variance)
        except Exception as e:
            logger.debug(f"Laplacian calculation failed: {e}")
            return 100.0  # Default to non-blurry

    def _extract_text_from_frame(self, frame_path: str) -> List[str]:
        """
        Extract text from frame using advanced OCR with preprocessing
        Professional approach: Image preprocessing + optimal PSM mode

        Args:
            frame_path: Path to frame image

        Returns:
            List of extracted text strings
        """
        try:
            import pytesseract
            from PIL import Image, ImageEnhance, ImageFilter

            # Open and preprocess image for better OCR
            img = Image.open(frame_path)

            # Resize if too small (Tesseract works best at 300 DPI)
            width, height = img.size
            if width < 1000:
                scale_factor = 1000 / width
                new_size = (int(width * scale_factor), int(height * scale_factor))
                img = img.resize(new_size, Image.Resampling.LANCZOS)

            # Convert to RGB if needed
            if img.mode != 'RGB':
                img = img.convert('RGB')

            # Enhance image for better OCR
            # 1. Increase contrast
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.5)

            # 2. Increase sharpness
            enhancer = ImageEnhance.Sharpness(img)
            img = enhancer.enhance(1.3)

            # Extract text using optimized config
            # PSM 11: Sparse text (best for video frames with scattered text)
            # OEM 3: Default LSTM OCR engine
            text = pytesseract.image_to_string(img, config=self.ocr_config)

            # Also try PSM 6 for uniform text blocks
            text_psm6 = pytesseract.image_to_string(img, config='--psm 6 --oem 3')

            # Combine results
            combined_text = text + '\n' + text_psm6

            # Clean and filter text
            lines = [line.strip() for line in combined_text.split('\n') if line.strip()]

            # Advanced filtering for meaningful text
            meaningful_text = []
            for line in lines:
                cleaned = self._clean_ocr_text(line)
                if cleaned and len(cleaned) >= 3:
                    # Must have at least one letter
                    if any(c.isalpha() for c in cleaned):
                        # Not just special characters
                        if not all(c in '!@#$%^&*()_+-=[]{}|;:,.<>?/' for c in cleaned):
                            meaningful_text.append(cleaned)

            # Remove duplicates while preserving order
            unique_text = list(dict.fromkeys(meaningful_text))

            return unique_text

        except ImportError:
            # pytesseract not installed
            logger.debug("pytesseract not available for OCR")
            return []
        except Exception as e:
            logger.debug(f"OCR failed: {e}")
            return []

    def _clean_ocr_text(self, text: str) -> str:
        """
        Clean OCR text output

        Args:
            text: Raw OCR text

        Returns:
            Cleaned text
        """
        # Remove extra whitespace
        text = ' '.join(text.split())

        # Remove common OCR errors
        text = text.replace('|', 'I').replace('0', 'O').replace('5', 'S')

        # Remove leading/trailing special chars
        text = text.strip('.,!?;:')

        return text

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

    def _extract_keywords(self, text_list: List[str]) -> List[str]:
        """
        Extract important keywords from text list
        Words that appear multiple times are likely important

        Args:
            text_list: List of text strings

        Returns:
            List of keywords sorted by frequency
        """
        # Count word frequency
        word_count = {}

        for text in text_list:
            words = text.lower().split()
            for word in words:
                # Clean word
                word = word.strip('.,!?;:()')
                # Must be at least 3 chars and alphabetic
                if len(word) >= 3 and word.isalpha():
                    word_count[word] = word_count.get(word, 0) + 1

        # Filter words that appear at least 2 times
        keywords = [
            word for word, count in word_count.items()
            if count >= 2
        ]

        # Sort by frequency
        keywords.sort(key=lambda w: word_count[w], reverse=True)

        return keywords[:10]  # Top 10 keywords

    def _extract_actions(self, text_list: List[str]) -> List[str]:
        """
        Extract action verbs from text
        Common action words that indicate what's happening in video

        Args:
            text_list: List of text strings

        Returns:
            List of action verbs found
        """
        # Common action verbs in videos
        action_verbs = {
            'find', 'found', 'make', 'made', 'create', 'created',
            'build', 'built', 'solve', 'solved', 'complete', 'completed',
            'finish', 'finished', 'win', 'won', 'beat', 'challenge',
            'cook', 'cooked', 'play', 'played', 'show', 'showing',
            'learn', 'learning', 'teach', 'teaching', 'try', 'trying',
            'test', 'testing', 'review', 'reviewing', 'explore', 'exploring',
            'discover', 'discovered', 'reveal', 'revealing', 'unlock',
            'master', 'mastering', 'achieve', 'achieving', 'get', 'getting',
            'do', 'doing', 'go', 'going', 'see', 'seeing', 'watch', 'watching',
            'use', 'using', 'start', 'starting', 'stop', 'stopping',
            'open', 'opening', 'close', 'closing', 'run', 'running',
            'jump', 'jumping', 'climb', 'climbing', 'fight', 'fighting',
            'race', 'racing', 'fly', 'flying', 'drive', 'driving'
        }

        actions_found = []

        for text in text_list:
            words = text.lower().split()
            for word in words:
                word = word.strip('.,!?;:()')
                if word in action_verbs:
                    actions_found.append(word.title())

        # Remove duplicates while preserving order
        unique_actions = list(dict.fromkeys(actions_found))

        return unique_actions[:5]  # Top 5 actions

    def _extract_entities(self, text_list: List[str]) -> List[str]:
        """
        Extract named entities (names, places, brands)
        Capitalized words are likely names/entities

        Args:
            text_list: List of text strings

        Returns:
            List of potential entities
        """
        entities = []

        # Common words to ignore (not entities)
        ignore_words = {
            'the', 'a', 'an', 'this', 'that', 'these', 'those',
            'is', 'are', 'was', 'were', 'be', 'been', 'being',
            'have', 'has', 'had', 'do', 'does', 'did', 'will',
            'would', 'should', 'could', 'may', 'might', 'must',
            'can', 'shall', 'to', 'of', 'in', 'on', 'at', 'by',
            'for', 'with', 'about', 'as', 'into', 'through', 'during',
            'before', 'after', 'above', 'below', 'between', 'under',
            'video', 'part', 'episode', 'chapter', 'tutorial', 'guide',
            'how', 'what', 'when', 'where', 'why', 'who', 'which'
        }

        for text in text_list:
            words = text.split()
            for word in words:
                # Clean word
                word = word.strip('.,!?;:()')

                # Check if capitalized (likely a name)
                if word and len(word) >= 3:
                    if word[0].isupper():
                        # Not in ignore list
                        if word.lower() not in ignore_words:
                            # Has some lowercase letters (not all caps)
                            if any(c.islower() for c in word):
                                entities.append(word)

        # Remove duplicates while preserving order
        unique_entities = list(dict.fromkeys(entities))

        return unique_entities[:10]  # Top 10 entities
