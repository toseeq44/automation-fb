"""
Visual Content Analyzer for Title Generator
Analyzes video frames using CLIP and scene change detection
Detects objects, scenes, actions, and niche classification
"""

import cv2
import numpy as np
import os
import tempfile
from typing import Dict, List, Tuple, Optional
from PIL import Image
from collections import Counter
from modules.logging.logger import get_logger

logger = get_logger(__name__)


class VisualAnalyzer:
    """Analyze visual content using CLIP and advanced scene detection"""

    # Niche categories with detection keywords
    NICHE_KEYWORDS = {
        'cooking': ['food', 'kitchen', 'chef', 'cooking', 'recipe', 'ingredients',
                    'plate', 'stove', 'oven', 'knife', 'pan', 'pot', 'dish'],
        'gaming': ['game', 'gaming', 'controller', 'console', 'screen', 'player',
                   'keyboard', 'mouse', 'headset', 'playstation', 'xbox'],
        'tutorial': ['computer', 'laptop', 'screen', 'code', 'typing', 'software',
                     'monitor', 'keyboard', 'programming', 'coding'],
        'review': ['product', 'box', 'unboxing', 'phone', 'camera', 'packaging',
                   'hands', 'table', 'smartphone', 'gadget'],
        'vlog': ['person', 'talking', 'outdoor', 'camera', 'selfie', 'street',
                 'travel', 'city', 'nature'],
        'fitness': ['gym', 'exercise', 'yoga', 'running', 'workout', 'weights',
                    'mat', 'sports', 'training', 'fitness'],
        'music': ['guitar', 'piano', 'singing', 'microphone', 'instrument',
                  'studio', 'stage', 'concert', 'musician'],
        'beauty': ['makeup', 'cosmetics', 'mirror', 'brush', 'face', 'beauty',
                   'skincare', 'hair', 'nail'],
        'education': ['book', 'writing', 'classroom', 'teaching', 'learning',
                      'student', 'teacher', 'study'],
        'fashion': ['clothing', 'fashion', 'dress', 'outfit', 'style', 'shoes',
                    'accessories', 'wardrobe']
    }

    # CLIP candidate labels for object detection
    CLIP_LABELS = [
        # People & Faces
        'person', 'man', 'woman', 'child', 'people', 'face', 'hand',

        # Cooking & Food
        'food', 'kitchen', 'chef', 'cooking', 'plate', 'ingredients',
        'stove', 'oven', 'knife', 'pan', 'pot', 'recipe', 'dish',
        'pizza', 'burger', 'pasta', 'cake', 'bread', 'meat', 'vegetable',

        # Gaming & Tech
        'game', 'gaming', 'controller', 'console', 'screen', 'computer',
        'keyboard', 'mouse', 'headset', 'laptop', 'phone', 'tablet',
        'monitor', 'smartphone', 'technology',

        # Products & Items
        'product', 'box', 'packaging', 'unboxing', 'camera', 'gadget',

        # Places & Scenes
        'outdoor', 'indoor', 'office', 'studio', 'street', 'nature',
        'city', 'room', 'bedroom', 'living room', 'bathroom', 'garden',

        # Activities & Actions
        'talking', 'working', 'typing', 'writing', 'reading', 'playing',
        'dancing', 'singing', 'running', 'walking',

        # Fitness & Sports
        'gym', 'exercise', 'workout', 'yoga', 'running', 'weights',
        'sports', 'football', 'basketball', 'tennis',

        # Music & Entertainment
        'guitar', 'piano', 'microphone', 'instrument', 'music', 'stage',

        # Beauty & Fashion
        'makeup', 'cosmetics', 'mirror', 'beauty', 'fashion', 'clothing',
        'dress', 'shoes',

        # Education
        'book', 'classroom', 'teaching', 'learning', 'study', 'writing'
    ]

    def __init__(self):
        """Initialize CLIP model for visual analysis"""
        self.clip_model = None
        self.clip_processor = None
        self.clip_available = False

        try:
            from transformers import CLIPProcessor, CLIPModel
            import torch

            logger.info("Loading CLIP model for visual analysis...")
            self.clip_model = CLIPModel.from_pretrained(
                "openai/clip-vit-base-patch32"
            )
            self.clip_processor = CLIPProcessor.from_pretrained(
                "openai/clip-vit-base-patch32"
            )

            # Move to GPU if available
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            self.clip_model.to(self.device)

            self.clip_available = True
            logger.info(f"✅ CLIP model loaded successfully (device: {self.device})")

        except ImportError:
            logger.warning("⚠️ CLIP not available. Run: pip install transformers torch")
        except Exception as e:
            logger.error(f"❌ Failed to load CLIP model: {e}")

    def analyze_video_visual(self, video_path: str, max_frames: int = 12) -> Dict:
        """
        Complete visual analysis of video

        Args:
            video_path: Path to video file
            max_frames: Maximum frames to analyze (default: 12)

        Returns:
            {
                'objects': List[str],          # Detected objects
                'scene': str,                  # Scene type (indoor/outdoor/studio)
                'niche': str,                  # Video niche category
                'actions': List[str],          # Detected actions
                'has_person': bool,            # Person present?
                'dominant_colors': List[str],  # Main colors
                'key_frames': int,             # Number of frames analyzed
                'confidence': float            # Analysis confidence
            }
        """
        logger.info(f"👁️ Starting visual analysis of: {os.path.basename(video_path)}")

        # Extract key frames using scene change detection
        frame_paths = self._extract_scene_change_frames(video_path, max_frames)

        if not frame_paths:
            logger.warning("No frames extracted for analysis")
            return self._empty_result()

        logger.info(f"📊 Analyzing {len(frame_paths)} key frames...")

        # Analyze each frame with CLIP
        all_objects = []
        has_person = False

        for i, frame_path in enumerate(frame_paths):
            logger.debug(f"Analyzing frame {i+1}/{len(frame_paths)}")

            objects = self._detect_objects_clip(frame_path)
            all_objects.extend(objects)

            # Check for person
            if any(obj in ['person', 'man', 'woman', 'people', 'face'] for obj in objects):
                has_person = True

        # Get unique objects with frequency
        object_freq = Counter(all_objects)
        unique_objects = [obj for obj, _ in object_freq.most_common(25)]

        # Classify niche based on detected objects
        niche = self._classify_niche(unique_objects)

        # Classify scene type
        scene = self._classify_scene(unique_objects)

        # Detect actions
        actions = self._detect_actions(unique_objects, niche)

        # Analyze dominant colors (use first frame)
        colors = self._extract_dominant_colors(frame_paths[0])

        # Calculate confidence based on detection quality
        confidence = min(len(unique_objects) / 10, 1.0)  # More objects = higher confidence

        # Clean up temp frames
        for frame_path in frame_paths:
            try:
                os.remove(frame_path)
            except:
                pass

        result = {
            'objects': unique_objects,
            'scene': scene,
            'niche': niche,
            'actions': actions,
            'has_person': has_person,
            'dominant_colors': colors,
            'key_frames': len(frame_paths),
            'confidence': confidence
        }

        logger.info(f"✅ Visual analysis complete:")
        logger.info(f"   📂 Niche: {niche}")
        logger.info(f"   🎬 Scene: {scene}")
        logger.info(f"   👤 Person: {'Yes' if has_person else 'No'}")
        logger.info(f"   🔍 Objects: {', '.join(unique_objects[:10])}")
        logger.info(f"   🎯 Actions: {', '.join(actions)}")

        return result

    def _extract_scene_change_frames(
        self,
        video_path: str,
        max_frames: int = 12,
        threshold: float = 30.0
    ) -> List[str]:
        """
        Extract frames at scene changes using histogram difference

        Args:
            video_path: Path to video
            max_frames: Maximum frames to extract
            threshold: Scene change sensitivity (higher = fewer frames)

        Returns:
            List of frame file paths
        """
        frames = []
        temp_dir = tempfile.gettempdir()

        try:
            cap = cv2.VideoCapture(video_path)

            if not cap.isOpened():
                logger.error("Failed to open video")
                return self._extract_even_frames(video_path, max_frames)

            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)

            logger.info(f"Video: {total_frames} frames @ {fps:.2f} FPS")

            prev_hist = None
            frame_count = 0
            extracted = 0

            # Sample every N frames for speed
            sample_rate = max(1, total_frames // (max_frames * 10))

            while cap.isOpened() and extracted < max_frames:
                ret, frame = cap.read()

                if not ret:
                    break

                # Sample frames for efficiency
                if frame_count % sample_rate == 0:
                    # Calculate color histogram
                    hist = cv2.calcHist(
                        [frame],
                        [0, 1, 2],
                        None,
                        [8, 8, 8],
                        [0, 256, 0, 256, 0, 256]
                    )
                    hist = cv2.normalize(hist, hist).flatten()

                    # Compare with previous frame
                    if prev_hist is not None:
                        # Calculate histogram difference
                        diff = cv2.compareHist(
                            prev_hist,
                            hist,
                            cv2.HISTCMP_BHATTACHARYYA
                        ) * 100

                        # Scene change detected
                        if diff > threshold:
                            # Save frame
                            frame_path = os.path.join(
                                temp_dir,
                                f"scene_{extracted}_{os.getpid()}.jpg"
                            )

                            # Resize frame for faster CLIP processing
                            frame_resized = cv2.resize(frame, (640, 480))
                            cv2.imwrite(frame_path, frame_resized, [cv2.IMWRITE_JPEG_QUALITY, 90])

                            frames.append(frame_path)
                            extracted += 1

                            logger.debug(f"Scene change at frame {frame_count} (diff: {diff:.1f})")

                    prev_hist = hist

                frame_count += 1

            cap.release()

            # If not enough scene changes, add evenly spaced frames
            if extracted < 5:
                logger.info("Adding evenly spaced frames to reach minimum...")
                additional = self._extract_even_frames(video_path, max_frames - extracted)
                frames.extend(additional)

            logger.info(f"Extracted {len(frames)} key frames")
            return frames

        except Exception as e:
            logger.error(f"Scene change detection failed: {e}")
            return self._extract_even_frames(video_path, max_frames)

    def _extract_even_frames(self, video_path: str, num_frames: int) -> List[str]:
        """Fallback: Extract evenly spaced frames"""
        frames = []
        temp_dir = tempfile.gettempdir()

        try:
            from moviepy import VideoFileClip

            clip = VideoFileClip(video_path)
            duration = clip.duration

            if duration <= 0:
                clip.close()
                return []

            # Calculate timestamps
            if duration < 5:
                timestamps = [duration * 0.5]
            elif duration < 15:
                timestamps = [duration * 0.25, duration * 0.5, duration * 0.75]
            else:
                step = duration / (num_frames + 1)
                timestamps = [step * (i + 1) for i in range(num_frames)]

            # Extract frames
            for i, t in enumerate(timestamps):
                try:
                    frame = clip.get_frame(t)
                    frame_path = os.path.join(
                        temp_dir,
                        f"even_{i}_{os.getpid()}.jpg"
                    )

                    img = Image.fromarray(frame)
                    img = img.resize((640, 480), Image.Resampling.LANCZOS)
                    img.save(frame_path, quality=90)
                    frames.append(frame_path)

                except Exception as e:
                    logger.warning(f"Failed to extract frame at {t}s: {e}")

            clip.close()
            return frames

        except Exception as e:
            logger.error(f"Even frame extraction failed: {e}")
            return []

    def _detect_objects_clip(self, frame_path: str) -> List[str]:
        """
        Detect objects in frame using CLIP zero-shot classification

        Args:
            frame_path: Path to frame image

        Returns:
            List of detected object labels
        """
        if not self.clip_available:
            return []

        try:
            import torch

            # Load image
            image = Image.open(frame_path).convert('RGB')

            # Prepare inputs
            inputs = self.clip_processor(
                text=self.CLIP_LABELS,
                images=image,
                return_tensors="pt",
                padding=True
            )

            # Move to device
            inputs = {k: v.to(self.device) for k, v in inputs.items()}

            # Get predictions
            with torch.no_grad():
                outputs = self.clip_model(**inputs)
                logits_per_image = outputs.logits_per_image
                probs = logits_per_image.softmax(dim=1)[0]

            # Get top 15 predictions above threshold
            threshold = 0.08  # 8% confidence minimum
            detected = []

            for i, prob in enumerate(probs):
                if prob > threshold:
                    label = self.CLIP_LABELS[i]
                    detected.append(label)

            # Sort by probability
            detected = sorted(detected, key=lambda x: probs[self.CLIP_LABELS.index(x)], reverse=True)

            return detected[:15]  # Top 15

        except Exception as e:
            logger.debug(f"CLIP detection failed: {e}")
            return []

    def _classify_niche(self, objects: List[str]) -> str:
        """
        Classify video niche based on detected objects

        Args:
            objects: List of detected objects

        Returns:
            Niche category string
        """
        scores = {}

        for niche, keywords in self.NICHE_KEYWORDS.items():
            # Count matching keywords
            score = sum(1 for obj in objects if obj in keywords)
            scores[niche] = score

        # Get best match
        if not scores or max(scores.values()) == 0:
            return 'general'

        best_niche = max(scores, key=scores.get)
        logger.debug(f"Niche scores: {scores}")
        logger.debug(f"Classified as: {best_niche}")

        return best_niche

    def _classify_scene(self, objects: List[str]) -> str:
        """Classify scene type (indoor/outdoor/studio)"""
        outdoor_keywords = ['outdoor', 'street', 'nature', 'city', 'park', 'sky', 'tree']
        studio_keywords = ['studio', 'stage', 'lights', 'microphone', 'equipment']
        indoor_keywords = ['room', 'office', 'kitchen', 'bedroom', 'living room']

        outdoor_score = sum(1 for obj in objects if obj in outdoor_keywords)
        studio_score = sum(1 for obj in objects if obj in studio_keywords)
        indoor_score = sum(1 for obj in objects if obj in indoor_keywords)

        if outdoor_score > indoor_score and outdoor_score > studio_score:
            return 'outdoor'
        elif studio_score > indoor_score:
            return 'studio'
        else:
            return 'indoor'

    def _detect_actions(self, objects: List[str], niche: str) -> List[str]:
        """
        Detect actions based on objects and niche

        Args:
            objects: Detected objects
            niche: Video niche

        Returns:
            List of action verbs
        """
        # Niche-specific action verbs
        action_map = {
            'cooking': ['cooking', 'making', 'preparing', 'baking', 'frying'],
            'gaming': ['playing', 'gaming', 'streaming', 'competing'],
            'tutorial': ['teaching', 'showing', 'explaining', 'coding', 'demonstrating'],
            'review': ['reviewing', 'unboxing', 'testing', 'comparing'],
            'vlog': ['talking', 'vlogging', 'traveling', 'exploring'],
            'fitness': ['exercising', 'working out', 'training', 'running'],
            'music': ['playing', 'singing', 'performing', 'practicing'],
            'beauty': ['applying', 'styling', 'demonstrating', 'testing'],
            'education': ['teaching', 'learning', 'studying', 'explaining'],
            'fashion': ['styling', 'wearing', 'showcasing', 'trying on']
        }

        # Get actions for niche
        actions = action_map.get(niche, ['showing', 'demonstrating'])

        # Also check for action-related objects
        action_objects = {
            'typing': 'typing',
            'talking': 'talking',
            'working': 'working',
            'playing': 'playing',
            'running': 'running',
            'dancing': 'dancing',
            'singing': 'singing'
        }

        for obj in objects:
            if obj in action_objects:
                actions.append(action_objects[obj])

        # Remove duplicates, keep order
        return list(dict.fromkeys(actions))[:5]

    def _extract_dominant_colors(self, frame_path: str) -> List[str]:
        """Extract dominant colors from frame"""
        try:
            image = cv2.imread(frame_path)
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

            # Resize for faster processing
            image = cv2.resize(image, (150, 150))

            # Reshape to list of pixels
            pixels = image.reshape(-1, 3)

            # Use K-means to find 3 dominant colors
            from sklearn.cluster import KMeans
            kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
            kmeans.fit(pixels)

            # Get dominant colors
            colors = kmeans.cluster_centers_.astype(int)

            # Convert to color names
            color_names = []
            for color in colors:
                name = self._rgb_to_color_name(color)
                if name not in color_names:
                    color_names.append(name)

            return color_names

        except Exception as e:
            logger.debug(f"Color extraction failed: {e}")
            return []

    def _rgb_to_color_name(self, rgb: np.ndarray) -> str:
        """Convert RGB to simple color name"""
        r, g, b = rgb

        # Define color ranges
        if max(r, g, b) < 60:
            return 'dark'
        elif min(r, g, b) > 200:
            return 'bright'
        elif r > 180 and g < 100 and b < 100:
            return 'red'
        elif r < 100 and g > 180 and b < 100:
            return 'green'
        elif r < 100 and g < 100 and b > 180:
            return 'blue'
        elif r > 180 and g > 180 and b < 100:
            return 'yellow'
        elif r > 180 and g < 100 and b > 180:
            return 'purple'
        elif r < 100 and g > 180 and b > 180:
            return 'cyan'
        else:
            return 'colorful'

    def _empty_result(self) -> Dict:
        """Return empty result when analysis fails"""
        return {
            'objects': [],
            'scene': 'unknown',
            'niche': 'general',
            'actions': [],
            'has_person': False,
            'dominant_colors': [],
            'key_frames': 0,
            'confidence': 0.0
        }
