"""
modules/video_editor/ar_engine.py
AR Face Effects Engine using MediaPipe
Provides face detection, tracking, and AR filter application

Supports both MediaPipe APIs:
- Legacy solutions API (pre 0.10.x) - DEPRECATED
- Modern tasks API (0.10.x+) - RECOMMENDED
"""

import cv2
import numpy as np
from typing import Optional, Tuple, List, Dict, Any
from pathlib import Path
import sys
import urllib.request
import os

from modules.logging.logger import get_logger

logger = get_logger(__name__)

# MediaPipe imports - try both old and new APIs
MEDIAPIPE_AVAILABLE = False
MEDIAPIPE_API_VERSION = None  # 'tasks' or 'solutions'

# Try new tasks API first (MediaPipe 0.10+)
try:
    logger.info("🔍 Attempting MediaPipe tasks API (0.10.x+)...")
    from mediapipe import tasks
    from mediapipe.tasks import python
    from mediapipe.tasks.python import vision
    from mediapipe.tasks.python.vision import FaceLandmarkerOptions

    MEDIAPIPE_AVAILABLE = True
    MEDIAPIPE_API_VERSION = 'tasks'
    logger.info("✅ MediaPipe tasks API loaded (0.10.x+)")
except (ImportError, AttributeError, ModuleNotFoundError) as e:
    logger.debug(f"MediaPipe tasks API not available: {e}")

# Fallback to legacy solutions API (pre 0.10.x)
if not MEDIAPIPE_AVAILABLE:
    try:
        logger.info("🔍 Attempting MediaPipe solutions API (legacy)...")
        import mediapipe as mp
        if hasattr(mp, 'solutions'):
            from mediapipe.solutions import face_mesh as mp_face_mesh
            from mediapipe.solutions import drawing_utils as mp_drawing
            from mediapipe.solutions import drawing_styles as mp_drawing_styles

            MEDIAPIPE_AVAILABLE = True
            MEDIAPIPE_API_VERSION = 'solutions'
            logger.info("✅ MediaPipe solutions API loaded (legacy)")
        else:
            raise AttributeError("mp.solutions not found")
    except (ImportError, AttributeError, ModuleNotFoundError) as e:
        logger.warning(f"MediaPipe solutions API not available: {e}")

if not MEDIAPIPE_AVAILABLE:
    logger.error("=" * 60)
    logger.error("❌ MediaPipe AR Engine NOT AVAILABLE")
    logger.error("=" * 60)
    logger.error("MediaPipe is not installed or incompatible.")
    logger.error("Solutions:")
    logger.error("  1. Install MediaPipe: pip install mediapipe")
    logger.error("  2. Check version: pip show mediapipe")
    logger.error("  3. Run diagnostic: python test_mediapipe_api.py")
    logger.error("=" * 60)
else:
    logger.info(f"📦 Using MediaPipe API: {MEDIAPIPE_API_VERSION}")


class AREngine:
    """
    AR Face Effects Engine
    Uses MediaPipe for 468-point face landmark detection
    Supports real-time face tracking and AR filter application

    Compatible with both MediaPipe APIs:
    - Tasks API (0.10.x+) - Modern, recommended
    - Solutions API (pre 0.10.x) - Legacy, deprecated
    """

    # Model URLs for tasks API
    FACE_LANDMARKER_MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task"

    def __init__(self):
        """Initialize MediaPipe Face Detector"""
        if not MEDIAPIPE_AVAILABLE:
            raise ImportError(
                "MediaPipe not available. Install with: pip install mediapipe"
            )

        self.api_version = MEDIAPIPE_API_VERSION
        self.face_detector = None

        if self.api_version == 'tasks':
            self._init_tasks_api()
        elif self.api_version == 'solutions':
            self._init_solutions_api()
        else:
            raise ValueError(f"Unknown MediaPipe API version: {self.api_version}")

        logger.info(f"✅ AR Engine initialized with MediaPipe {self.api_version} API")

    def _init_tasks_api(self):
        """Initialize using MediaPipe tasks API (0.10+)"""
        # Download face landmarker model if needed
        model_path = self._ensure_face_landmarker_model()

        # Create FaceLandmarker options
        base_options = python.BaseOptions(model_asset_path=model_path)
        options = FaceLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.IMAGE,  # Process individual frames
            num_faces=5,  # Support multiple faces
            min_face_detection_confidence=0.5,
            min_face_presence_confidence=0.5,
            min_tracking_confidence=0.5
        )

        # Create face landmarker
        self.face_detector = vision.FaceLandmarker.create_from_options(options)
        logger.info("✅ FaceLandmarker initialized (tasks API)")

    def _init_solutions_api(self):
        """Initialize using MediaPipe solutions API (legacy)"""
        # Initialize face mesh detector
        self.face_detector = mp_face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=5,  # Support multiple faces
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        logger.info("✅ FaceMesh initialized (solutions API - legacy)")

    def _ensure_face_landmarker_model(self) -> str:
        """
        Download face landmarker model if not exists

        Returns:
            Path to model file
        """
        # Model directory
        model_dir = Path(__file__).parent / 'models'
        model_dir.mkdir(exist_ok=True)

        model_path = model_dir / 'face_landmarker.task'

        # Download if not exists
        if not model_path.exists():
            logger.info("📥 Downloading face landmarker model (~10MB)...")
            try:
                urllib.request.urlretrieve(self.FACE_LANDMARKER_MODEL_URL, str(model_path))
                logger.info(f"✅ Model downloaded: {model_path}")
            except Exception as e:
                logger.error(f"❌ Failed to download model: {e}")
                raise RuntimeError(
                    f"Failed to download face landmarker model. "
                    f"Please download manually from: {self.FACE_LANDMARKER_MODEL_URL}"
                )

        return str(model_path)

    def detect_faces(self, frame: np.ndarray) -> Optional[List[Dict[str, Any]]]:
        """
        Detect faces and landmarks in a frame

        Args:
            frame: BGR image from OpenCV

        Returns:
            List of face data dictionaries with landmarks, or None if no faces
        """
        try:
            if self.api_version == 'tasks':
                return self._detect_faces_tasks(frame)
            elif self.api_version == 'solutions':
                return self._detect_faces_solutions(frame)
            else:
                return None
        except Exception as e:
            logger.error(f"Face detection error: {e}")
            return None

    def _detect_faces_tasks(self, frame: np.ndarray) -> Optional[List[Dict[str, Any]]]:
        """Detect faces using tasks API (MediaPipe 0.10+)"""
        # Convert BGR to RGB for MediaPipe
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Create MediaPipe Image
        mp_image = python.vision.Image(image_format=python.vision.ImageFormat.SRGB, data=rgb_frame)

        # Detect faces
        detection_result = self.face_detector.detect(mp_image)

        if not detection_result.face_landmarks:
            return None

        # Extract face data
        faces = []
        h, w = frame.shape[:2]

        for face_landmarks_list in detection_result.face_landmarks:
            # Convert normalized landmarks to pixel coordinates
            landmarks = []
            for landmark in face_landmarks_list:
                x = int(landmark.x * w)
                y = int(landmark.y * h)
                z = landmark.z
                landmarks.append({'x': x, 'y': y, 'z': z})

            # Get face bounding box
            x_coords = [lm['x'] for lm in landmarks]
            y_coords = [lm['y'] for lm in landmarks]

            bbox = {
                'x1': min(x_coords),
                'y1': min(y_coords),
                'x2': max(x_coords),
                'y2': max(y_coords)
            }

            # Get key facial points
            key_points = self._extract_key_points(landmarks)

            faces.append({
                'landmarks': landmarks,
                'bbox': bbox,
                'key_points': key_points
            })

        return faces

    def _detect_faces_solutions(self, frame: np.ndarray) -> Optional[List[Dict[str, Any]]]:
        """Detect faces using solutions API (legacy)"""
        # Convert BGR to RGB for MediaPipe
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Process frame
        results = self.face_detector.process(rgb_frame)

        if not results.multi_face_landmarks:
            return None

        # Extract face data
        faces = []
        h, w = frame.shape[:2]

        for face_landmarks in results.multi_face_landmarks:
            # Convert normalized landmarks to pixel coordinates
            landmarks = []
            for landmark in face_landmarks.landmark:
                x = int(landmark.x * w)
                y = int(landmark.y * h)
                z = landmark.z
                landmarks.append({'x': x, 'y': y, 'z': z})

            # Get face bounding box
            x_coords = [lm['x'] for lm in landmarks]
            y_coords = [lm['y'] for lm in landmarks]

            bbox = {
                'x1': min(x_coords),
                'y1': min(y_coords),
                'x2': max(x_coords),
                'y2': max(y_coords)
            }

            # Get key facial points
            key_points = self._extract_key_points(landmarks)

            faces.append({
                'landmarks': landmarks,
                'bbox': bbox,
                'key_points': key_points
            })

        return faces

    def _extract_key_points(self, landmarks: List[Dict]) -> Dict[str, Tuple[int, int]]:
        """
        Extract key facial points from 468 landmarks

        Returns:
            Dictionary with key facial feature coordinates
        """
        # MediaPipe face mesh landmark indices
        # Reference: https://github.com/google/mediapipe/blob/master/mediapipe/modules/face_geometry/data/canonical_face_model_uv_visualization.png

        return {
            # Eyes
            'left_eye': (landmarks[33]['x'], landmarks[33]['y']),
            'right_eye': (landmarks[263]['x'], landmarks[263]['y']),

            # Nose
            'nose_tip': (landmarks[1]['x'], landmarks[1]['y']),
            'nose_bridge': (landmarks[168]['x'], landmarks[168]['y']),

            # Mouth
            'mouth_left': (landmarks[61]['x'], landmarks[61]['y']),
            'mouth_right': (landmarks[291]['x'], landmarks[291]['y']),
            'mouth_top': (landmarks[13]['x'], landmarks[13]['y']),
            'mouth_bottom': (landmarks[14]['x'], landmarks[14]['y']),

            # Face outline
            'chin': (landmarks[152]['x'], landmarks[152]['y']),
            'forehead': (landmarks[10]['x'], landmarks[10]['y']),
            'left_cheek': (landmarks[234]['x'], landmarks[234]['y']),
            'right_cheek': (landmarks[454]['x'], landmarks[454]['y']),
        }

    def apply_face_beautification(self, frame: np.ndarray, intensity: float = 0.5) -> np.ndarray:
        """
        Apply face beautification (skin smoothing)

        Args:
            frame: Input frame
            intensity: Beautification intensity (0.0 - 1.0)

        Returns:
            Beautified frame
        """
        try:
            faces = self.detect_faces(frame)

            if not faces:
                return frame

            result = frame.copy()

            for face in faces:
                bbox = face['bbox']

                # Extract face region with padding
                padding = 20
                x1 = max(0, bbox['x1'] - padding)
                y1 = max(0, bbox['y1'] - padding)
                x2 = min(frame.shape[1], bbox['x2'] + padding)
                y2 = min(frame.shape[0], bbox['y2'] + padding)

                face_region = result[y1:y2, x1:x2].copy()

                if face_region.size == 0:
                    continue

                # Apply bilateral filter for skin smoothing
                # Preserves edges while smoothing skin
                kernel_size = int(5 + intensity * 10)
                if kernel_size % 2 == 0:
                    kernel_size += 1  # Must be odd

                smoothed = cv2.bilateralFilter(
                    face_region,
                    kernel_size,
                    sigmaColor=int(50 * intensity),
                    sigmaSpace=int(50 * intensity)
                )

                # Blend original and smoothed based on intensity
                face_region = cv2.addWeighted(
                    face_region, 1 - intensity,
                    smoothed, intensity,
                    0
                )

                # Put back the smoothed face
                result[y1:y2, x1:x2] = face_region

            return result

        except Exception as e:
            logger.error(f"Face beautification error: {e}")
            return frame

    def apply_eye_enhancement(self, frame: np.ndarray, intensity: float = 0.3) -> np.ndarray:
        """
        Enhance eyes (sharpen and brighten)

        Args:
            frame: Input frame
            intensity: Enhancement intensity (0.0 - 1.0)

        Returns:
            Enhanced frame
        """
        try:
            faces = self.detect_faces(frame)

            if not faces:
                return frame

            result = frame.copy()

            for face in faces:
                key_points = face['key_points']

                # Process both eyes
                for eye_key in ['left_eye', 'right_eye']:
                    eye_x, eye_y = key_points[eye_key]

                    # Define eye region (square around eye center)
                    eye_size = 40
                    x1 = max(0, eye_x - eye_size)
                    y1 = max(0, eye_y - eye_size)
                    x2 = min(frame.shape[1], eye_x + eye_size)
                    y2 = min(frame.shape[0], eye_y + eye_size)

                    eye_region = result[y1:y2, x1:x2].copy()

                    if eye_region.size == 0:
                        continue

                    # Sharpen eye region
                    kernel = np.array([[-1,-1,-1],
                                     [-1, 9,-1],
                                     [-1,-1,-1]]) * intensity
                    sharpened = cv2.filter2D(eye_region, -1, kernel)

                    # Brighten slightly
                    brightened = cv2.convertScaleAbs(sharpened, alpha=1.0 + 0.1 * intensity, beta=5 * intensity)

                    # Blend
                    eye_region = cv2.addWeighted(eye_region, 1 - intensity, brightened, intensity, 0)

                    result[y1:y2, x1:x2] = eye_region

            return result

        except Exception as e:
            logger.error(f"Eye enhancement error: {e}")
            return frame

    def apply_teeth_whitening(self, frame: np.ndarray, intensity: float = 0.3) -> np.ndarray:
        """
        Whiten teeth

        Args:
            frame: Input frame
            intensity: Whitening intensity (0.0 - 1.0)

        Returns:
            Enhanced frame
        """
        try:
            faces = self.detect_faces(frame)

            if not faces:
                return frame

            result = frame.copy()

            for face in faces:
                key_points = face['key_points']

                # Get mouth region
                mouth_left = key_points['mouth_left']
                mouth_right = key_points['mouth_right']
                mouth_top = key_points['mouth_top']
                mouth_bottom = key_points['mouth_bottom']

                # Calculate mouth bounding box
                x1 = max(0, min(mouth_left[0], mouth_right[0]) - 10)
                y1 = max(0, mouth_top[1] - 5)
                x2 = min(frame.shape[1], max(mouth_left[0], mouth_right[0]) + 10)
                y2 = min(frame.shape[0], mouth_bottom[1] + 5)

                mouth_region = result[y1:y2, x1:x2].copy()

                if mouth_region.size == 0:
                    continue

                # Convert to HSV for better color manipulation
                hsv = cv2.cvtColor(mouth_region, cv2.COLOR_BGR2HSV)

                # Detect teeth (white/light colors)
                lower_white = np.array([0, 0, 150])
                upper_white = np.array([180, 50, 255])
                teeth_mask = cv2.inRange(hsv, lower_white, upper_white)

                # Brighten teeth area
                brightened = cv2.convertScaleAbs(mouth_region, alpha=1.0, beta=int(30 * intensity))

                # Apply whitening only to teeth areas
                mouth_region = np.where(
                    teeth_mask[:, :, np.newaxis] > 0,
                    cv2.addWeighted(mouth_region, 1 - intensity, brightened, intensity, 0),
                    mouth_region
                )

                result[y1:y2, x1:x2] = mouth_region

            return result

        except Exception as e:
            logger.error(f"Teeth whitening error: {e}")
            return frame

    def auto_crop_to_face(self, frame: np.ndarray, aspect_ratio: Tuple[int, int] = (9, 16),
                         margin: float = 0.3) -> Optional[np.ndarray]:
        """
        Automatically crop video to keep face centered (perfect for TikTok/Reels)

        Args:
            frame: Input frame
            aspect_ratio: Target aspect ratio (width, height)
            margin: Margin around face (0.0 - 1.0)

        Returns:
            Cropped frame or None if no face detected
        """
        try:
            faces = self.detect_faces(frame)

            if not faces:
                return None

            # Use the largest face (first face)
            face = faces[0]
            bbox = face['bbox']

            # Calculate face center
            face_center_x = (bbox['x1'] + bbox['x2']) // 2
            face_center_y = (bbox['y1'] + bbox['y2']) // 2

            # Calculate face size with margin
            face_width = bbox['x2'] - bbox['x1']
            face_height = bbox['y2'] - bbox['y1']

            target_width = int(face_width * (1 + margin * 2))
            target_height = int(target_width * aspect_ratio[1] / aspect_ratio[0])

            # Calculate crop coordinates
            crop_x1 = max(0, face_center_x - target_width // 2)
            crop_y1 = max(0, face_center_y - target_height // 2)
            crop_x2 = min(frame.shape[1], crop_x1 + target_width)
            crop_y2 = min(frame.shape[0], crop_y1 + target_height)

            # Adjust if crop goes out of bounds
            if crop_x2 - crop_x1 < target_width:
                crop_x1 = max(0, crop_x2 - target_width)
            if crop_y2 - crop_y1 < target_height:
                crop_y1 = max(0, crop_y2 - target_height)

            # Crop frame
            cropped = frame[crop_y1:crop_y2, crop_x1:crop_x2]

            return cropped

        except Exception as e:
            logger.error(f"Auto crop error: {e}")
            return None

    def blur_background(self, frame: np.ndarray, blur_strength: int = 15) -> np.ndarray:
        """
        Blur background while keeping face sharp (portrait mode effect)

        Args:
            frame: Input frame
            blur_strength: Blur kernel size (higher = more blur)

        Returns:
            Frame with blurred background
        """
        try:
            faces = self.detect_faces(frame)

            if not faces:
                # No face detected, return original
                return frame

            # Create mask for all faces
            mask = np.zeros(frame.shape[:2], dtype=np.uint8)

            for face in faces:
                bbox = face['bbox']

                # Expand face region slightly
                padding = 40
                x1 = max(0, bbox['x1'] - padding)
                y1 = max(0, bbox['y1'] - padding)
                x2 = min(frame.shape[1], bbox['x2'] + padding)
                y2 = min(frame.shape[0], bbox['y2'] + padding)

                # Draw filled rectangle for face region
                cv2.rectangle(mask, (x1, y1), (x2, y2), 255, -1)

            # Apply Gaussian blur to mask edges for smooth transition
            mask = cv2.GaussianBlur(mask, (21, 21), 11)

            # Blur the entire frame
            if blur_strength % 2 == 0:
                blur_strength += 1  # Must be odd
            blurred_frame = cv2.GaussianBlur(frame, (blur_strength, blur_strength), 0)

            # Blend original and blurred based on mask
            mask_3channel = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR) / 255.0
            result = (frame * mask_3channel + blurred_frame * (1 - mask_3channel)).astype(np.uint8)

            return result

        except Exception as e:
            logger.error(f"Background blur error: {e}")
            return frame

    def draw_face_landmarks(self, frame: np.ndarray, show_mesh: bool = True) -> np.ndarray:
        """
        Draw face landmarks on frame (for debugging/visualization)

        Args:
            frame: Input frame
            show_mesh: If True, draw full mesh; if False, draw only key points

        Returns:
            Frame with landmarks drawn
        """
        try:
            faces = self.detect_faces(frame)

            if not faces:
                return frame

            result = frame.copy()

            for face in faces:
                if show_mesh:
                    # Draw all 468 landmarks
                    for landmark in face['landmarks']:
                        cv2.circle(result, (landmark['x'], landmark['y']), 1, (0, 255, 0), -1)
                else:
                    # Draw only key points
                    key_points = face['key_points']
                    for point_name, (x, y) in key_points.items():
                        cv2.circle(result, (x, y), 3, (0, 255, 0), -1)
                        cv2.putText(result, point_name, (x + 5, y - 5),
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 255, 255), 1)

                # Draw bounding box
                bbox = face['bbox']
                cv2.rectangle(result, (bbox['x1'], bbox['y1']), (bbox['x2'], bbox['y2']),
                            (255, 0, 0), 2)

            return result

        except Exception as e:
            logger.error(f"Draw landmarks error: {e}")
            return frame

    def cleanup(self):
        """Cleanup MediaPipe resources"""
        if hasattr(self, 'face_detector') and self.face_detector:
            try:
                if self.api_version == 'tasks':
                    self.face_detector.close()
                elif self.api_version == 'solutions':
                    self.face_detector.close()
            except Exception as e:
                logger.debug(f"Cleanup error (non-critical): {e}")

        logger.info("AR Engine cleaned up")
