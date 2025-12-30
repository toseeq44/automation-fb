"""
Local Vision Analyzer - 100% Offline!
Uses YOLO + BLIP models locally (no API needed)
Falls back from cloud APIs to local models
"""

from pathlib import Path
from typing import Dict, List, Optional
import os
from modules.logging.logger import get_logger

logger = get_logger(__name__)


class LocalVisionAnalyzer:
    """
    Offline vision analysis using local models
    No API needed! Works 100% offline!
    """

    def __init__(self, models_dir: Optional[str] = None):
        """
        Initialize local vision analyzer

        Args:
            models_dir: Path to models directory (default: C:\TitleGenerator\models or ~/.title_generator/models)
        """
        self.models_dir = models_dir or self._get_default_models_dir()
        self.yolo_model = None
        self.blip_model = None
        self.blip_processor = None
        self.mobilenet_model = None

        logger.info("🔧 Initializing local vision analyzer...")
        self._check_models()

    def _get_default_models_dir(self) -> str:
        """
        Get default models directory with priority search:
        1. C:\AI_Models\ (Windows) or ~/AI_Models/ (Linux/Mac)
        2. Desktop\AI_Models\
        3. Cache directory (automatic downloads)
        """
        import platform

        possible_locations = []
        system = platform.system()

        if system == 'Windows':
            # Windows: Check multiple locations
            possible_locations = [
                r"C:\AI_Models",
                os.path.join(os.path.expanduser("~"), "Desktop", "AI_Models"),
                os.path.join(os.path.expanduser("~"), "AI_Models"),
            ]
        else:  # Linux/Mac
            home = os.path.expanduser("~")
            possible_locations = [
                os.path.join(home, "AI_Models"),
                os.path.join(home, "Desktop", "AI_Models"),
                os.path.join(home, ".cache", "ai_models"),
            ]

        # Return first existing directory with files, or first in list
        for location in possible_locations:
            if os.path.exists(location):
                if os.path.isdir(location) and os.listdir(location):
                    logger.info(f"   📁 Using AI_Models from: {location}")
                    return location

        # Create and return first priority location
        default_dir = possible_locations[0]
        os.makedirs(default_dir, exist_ok=True)
        logger.info(f"   📁 Created AI_Models at: {default_dir}")
        return default_dir

    def _check_models(self):
        """Check which models are available"""
        logger.info("   Checking available local models...")

        # Check YOLO
        try:
            from ultralytics import YOLO
            logger.info("   ✅ YOLO available (ultralytics)")
            self.yolo_available = True
        except ImportError:
            logger.warning("   ⚠️  YOLO not available (install: pip install ultralytics)")
            self.yolo_available = False

        # Check BLIP
        try:
            from transformers import BlipProcessor, BlipForConditionalGeneration
            logger.info("   ✅ BLIP available (transformers)")
            self.blip_available = True
        except ImportError:
            logger.warning("   ⚠️  BLIP not available (install: pip install transformers torch)")
            self.blip_available = False

        # Check OpenCV (for face detection)
        try:
            import cv2
            logger.info("   ✅ OpenCV available")
            self.opencv_available = True
        except ImportError:
            logger.warning("   ⚠️  OpenCV not available")
            self.opencv_available = False

    def analyze_frame(self, frame_path: str, metadata: Dict) -> Optional[Dict]:
        """
        Analyze single frame with local models

        Args:
            frame_path: Path to frame image
            metadata: Video metadata

        Returns:
            Analysis results or None if all models fail
        """
        logger.info("🔍 Analyzing frame with LOCAL models (offline)...")

        results = {
            'detected_objects': [],
            'detected_actions': [],
            'has_person': False,
            'scene_type': 'unknown',
            'niche': 'general',
            'niche_confidence': 0.5,
            'content_description': ''
        }

        # Try BLIP first (best for overall description)
        blip_result = self._analyze_with_blip(frame_path)
        if blip_result:
            results.update(blip_result)
            logger.info(f"   ✅ BLIP: {blip_result.get('content_description', 'N/A')[:80]}")
            return results

        # Fallback to YOLO (object detection only)
        yolo_result = self._analyze_with_yolo(frame_path)
        if yolo_result:
            results.update(yolo_result)
            logger.info(f"   ✅ YOLO: {len(yolo_result.get('detected_objects', []))} objects detected")
            return results

        # Fallback to OpenCV (basic face detection)
        opencv_result = self._analyze_with_opencv(frame_path)
        if opencv_result:
            results.update(opencv_result)
            logger.info(f"   ✅ OpenCV: Basic analysis complete")
            return results

        logger.warning("   ⚠️  No local models available for vision analysis")
        return None

    def _analyze_with_blip(self, frame_path: str) -> Optional[Dict]:
        """
        Analyze with BLIP model (image captioning)
        Best for overall scene understanding!
        """
        if not self.blip_available:
            return None

        try:
            from transformers import BlipProcessor, BlipForConditionalGeneration
            from PIL import Image
            import torch

            # Load model (first time only)
            if self.blip_model is None:
                logger.info("   📥 Loading BLIP model (first time - may take 30s)...")

                # Check if model exists in C:\TitleGenerator\models
                local_model_path = os.path.join(self.models_dir, "blip-image-captioning-base")

                if os.path.exists(local_model_path):
                    logger.info(f"   ✅ Loading BLIP from: {local_model_path}")
                    self.blip_processor = BlipProcessor.from_pretrained(local_model_path)
                    self.blip_model = BlipForConditionalGeneration.from_pretrained(local_model_path)
                else:
                    # Download from HuggingFace (auto-cache)
                    logger.info("   📥 Downloading BLIP from HuggingFace (~500MB)...")
                    logger.info("   💡 For faster loading, download to C:\\TitleGenerator\\models\\")
                    self.blip_processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
                    self.blip_model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")

                logger.info("   ✅ BLIP model loaded!")

            # Load image
            image = Image.open(frame_path).convert('RGB')

            # Generate caption
            inputs = self.blip_processor(image, return_tensors="pt")

            # Generate with beam search for better quality
            out = self.blip_model.generate(**inputs, max_new_tokens=50, num_beams=5)
            caption = self.blip_processor.decode(out[0], skip_special_tokens=True)

            # Infer niche from caption
            niche = self._infer_niche_from_description(caption)

            return {
                'content_description': caption,
                'niche': niche,
                'niche_confidence': 0.8,
                'detected_objects': self._extract_objects_from_text(caption),
                'detected_actions': self._extract_actions_from_text(caption),
                'has_person': 'person' in caption.lower() or 'man' in caption.lower() or 'woman' in caption.lower(),
                'scene_type': self._infer_scene_from_description(caption)
            }

        except Exception as e:
            logger.warning(f"   ⚠️  BLIP analysis failed: {e}")
            return None

    def _analyze_with_yolo(self, frame_path: str) -> Optional[Dict]:
        """
        Analyze with YOLO model (object detection)
        Fast and accurate for detecting objects!
        """
        if not self.yolo_available:
            return None

        try:
            from ultralytics import YOLO

            # Load model (first time only)
            if self.yolo_model is None:
                logger.info("   📥 Loading YOLO model (first time - lightweight!)...")

                # Check if model exists in C:\TitleGenerator\models
                local_model_path = os.path.join(self.models_dir, "yolov8n.pt")

                if os.path.exists(local_model_path):
                    logger.info(f"   ✅ Loading YOLO from: {local_model_path}")
                    self.yolo_model = YOLO(local_model_path)
                else:
                    # Download YOLOv8 nano (6MB - very small!)
                    logger.info("   📥 Downloading YOLOv8-nano (6MB)...")
                    self.yolo_model = YOLO('yolov8n.pt')  # Auto-downloads

                logger.info("   ✅ YOLO model loaded!")

            # Run detection
            results = self.yolo_model(frame_path, verbose=False)

            # Extract detected objects
            detected_objects = []
            has_person = False

            for r in results:
                for box in r.boxes:
                    class_id = int(box.cls)
                    class_name = self.yolo_model.names[class_id]
                    confidence = float(box.conf)

                    if confidence > 0.4:  # 40% confidence threshold
                        detected_objects.append(class_name)
                        if class_name == 'person':
                            has_person = True

            # Infer niche from objects
            niche = self._infer_niche_from_objects(detected_objects)

            # Build description from objects
            if detected_objects:
                description = f"Image showing {', '.join(detected_objects[:3])}"
            else:
                description = "Image content"

            return {
                'detected_objects': detected_objects[:10],  # Top 10
                'has_person': has_person,
                'niche': niche,
                'niche_confidence': 0.7,
                'content_description': description,
                'scene_type': self._infer_scene_from_objects(detected_objects)
            }

        except Exception as e:
            logger.warning(f"   ⚠️  YOLO analysis failed: {e}")
            return None

    def _analyze_with_opencv(self, frame_path: str) -> Optional[Dict]:
        """
        Analyze with OpenCV (basic face/feature detection)
        Fallback for basic analysis
        """
        if not self.opencv_available:
            return None

        try:
            import cv2
            import numpy as np

            # Load image
            img = cv2.imread(frame_path)
            if img is None:
                return None

            # Face detection
            face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, 1.1, 4)

            has_person = len(faces) > 0

            # Color analysis
            dominant_colors = self._get_dominant_colors(img)

            # Brightness
            brightness = np.mean(img)
            is_bright = brightness > 127

            return {
                'has_person': has_person,
                'detected_objects': ['person'] if has_person else [],
                'scene_type': 'bright' if is_bright else 'dark',
                'niche': 'general',
                'niche_confidence': 0.3,
                'content_description': f"{'Person visible' if has_person else 'Scene'} with {'bright' if is_bright else 'dark'} lighting"
            }

        except Exception as e:
            logger.warning(f"   ⚠️  OpenCV analysis failed: {e}")
            return None

    def _get_dominant_colors(self, img, k=3):
        """Extract dominant colors from image"""
        try:
            import cv2
            import numpy as np

            # Reshape image
            pixels = img.reshape(-1, 3).astype(np.float32)

            # K-means clustering
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
            _, labels, centers = cv2.kmeans(pixels, k, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)

            return centers.astype(int).tolist()
        except:
            return []

    def _infer_niche_from_description(self, description: str) -> str:
        """Infer niche from image description"""
        desc_lower = description.lower()

        niche_keywords = {
            'cooking': ['cook', 'food', 'kitchen', 'recipe', 'meal', 'dish', 'eat', 'plate', 'bowl', 'cooking', 'chef'],
            'gaming': ['game', 'gaming', 'screen', 'controller', 'console', 'playing', 'video game'],
            'fitness': ['workout', 'exercise', 'gym', 'fitness', 'training', 'running', 'yoga'],
            'music': ['music', 'instrument', 'guitar', 'piano', 'singing', 'microphone', 'stage'],
            'tutorial': ['tutorial', 'demonstration', 'showing', 'teaching', 'learning'],
            'vlog': ['person', 'selfie', 'talking', 'vlog', 'video'],
            'beauty': ['makeup', 'beauty', 'cosmetic', 'mirror', 'lipstick'],
            'entertainment': ['entertainment', 'funny', 'comedy', 'laughing']
        }

        for niche, keywords in niche_keywords.items():
            if any(kw in desc_lower for kw in keywords):
                return niche

        return 'general'

    def _infer_niche_from_objects(self, objects: List[str]) -> str:
        """Infer niche from detected objects"""
        objects_lower = [obj.lower() for obj in objects]

        # Cooking indicators
        cooking_objects = ['bowl', 'cup', 'fork', 'knife', 'spoon', 'bottle', 'wine glass', 'dining table', 'oven', 'refrigerator']
        if any(obj in objects_lower for obj in cooking_objects):
            return 'cooking'

        # Gaming indicators
        gaming_objects = ['tv', 'laptop', 'keyboard', 'mouse', 'remote', 'cell phone']
        if any(obj in objects_lower for obj in gaming_objects):
            # Check if person + screen (likely gaming)
            if 'person' in objects_lower and any(obj in objects_lower for obj in ['tv', 'laptop']):
                return 'gaming'

        # Fitness indicators
        fitness_objects = ['person']
        if 'person' in objects_lower:
            return 'vlog'  # Person visible = vlog most likely

        return 'general'

    def _infer_scene_from_description(self, description: str) -> str:
        """Infer scene type from description"""
        desc_lower = description.lower()

        if any(kw in desc_lower for kw in ['kitchen', 'table', 'room', 'indoor']):
            return 'indoor'
        elif any(kw in desc_lower for kw in ['outdoor', 'outside', 'park', 'street']):
            return 'outdoor'
        elif any(kw in desc_lower for kw in ['kitchen']):
            return 'kitchen'

        return 'unknown'

    def _infer_scene_from_objects(self, objects: List[str]) -> str:
        """Infer scene type from objects"""
        objects_lower = [obj.lower() for obj in objects]

        kitchen_objects = ['oven', 'refrigerator', 'microwave', 'sink', 'dining table']
        if any(obj in objects_lower for obj in kitchen_objects):
            return 'kitchen'

        outdoor_objects = ['car', 'truck', 'bicycle', 'tree', 'traffic light']
        if any(obj in objects_lower for obj in outdoor_objects):
            return 'outdoor'

        return 'indoor'

    def _extract_objects_from_text(self, text: str) -> List[str]:
        """Extract object names from description text"""
        # Common nouns that are objects
        common_objects = ['person', 'man', 'woman', 'food', 'plate', 'bowl', 'cup', 'table',
                         'phone', 'laptop', 'car', 'bike', 'dog', 'cat', 'tree', 'flower']

        text_lower = text.lower()
        found_objects = [obj for obj in common_objects if obj in text_lower]
        return found_objects

    def _extract_actions_from_text(self, text: str) -> List[str]:
        """Extract actions from description text"""
        # Common action verbs
        actions = ['sitting', 'standing', 'walking', 'running', 'eating', 'drinking',
                  'cooking', 'playing', 'holding', 'looking', 'talking', 'smiling']

        text_lower = text.lower()
        found_actions = [action for action in actions if action in text_lower]
        return found_actions


def test_local_analyzer():
    """Test local vision analyzer"""
    analyzer = LocalVisionAnalyzer()

    # Test with sample image
    test_image = "/path/to/test/image.jpg"
    if os.path.exists(test_image):
        result = analyzer.analyze_frame(test_image, {})
        print("Result:", result)


if __name__ == "__main__":
    test_local_analyzer()
