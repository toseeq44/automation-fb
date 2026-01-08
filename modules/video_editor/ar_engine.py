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

        # Create MediaPipe Image (correct import path for 0.10.x)
        import mediapipe as mp
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

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
                # Increased parameters for more noticeable smoothing
                kernel_size = int(7 + intensity * 15)
                if kernel_size % 2 == 0:
                    kernel_size += 1  # Must be odd

                smoothed = cv2.bilateralFilter(
                    face_region,
                    kernel_size,
                    sigmaColor=int(80 * intensity),
                    sigmaSpace=int(80 * intensity)
                )

                # Apply a second pass for stronger smoothing
                if intensity > 0.5:
                    smoothed = cv2.bilateralFilter(
                        smoothed,
                        kernel_size,
                        sigmaColor=int(60 * intensity),
                        sigmaSpace=int(60 * intensity)
                    )

                # Slight brightness adjustment for glowing skin effect
                smoothed = cv2.convertScaleAbs(smoothed, alpha=1.0, beta=int(3 * intensity))

                # Blend original and smoothed based on intensity
                face_region = cv2.addWeighted(
                    face_region, 1 - intensity * 0.9,
                    smoothed, intensity * 0.9,
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
        Enhance eyes by making them appear larger using radial distortion (bulge effect)

        Args:
            frame: Input frame
            intensity: Enhancement intensity (0.0 - 1.0) - controls how much eyes are enlarged

        Returns:
            Enhanced frame with bigger eyes
        """
        try:
            faces = self.detect_faces(frame)

            if not faces:
                return frame

            result = frame.copy()
            h, w = frame.shape[:2]

            for face in faces:
                key_points = face['key_points']

                # Process both eyes
                for eye_key in ['left_eye', 'right_eye']:
                    eye_x, eye_y = key_points[eye_key]

                    # Define eye region for enlargement
                    # Larger radius for more natural effect
                    eye_radius = int(50 + intensity * 20)

                    x1 = max(0, eye_x - eye_radius)
                    y1 = max(0, eye_y - eye_radius)
                    x2 = min(w, eye_x + eye_radius)
                    y2 = min(h, eye_y + eye_radius)

                    if x2 <= x1 or y2 <= y1:
                        continue

                    # Extract region around eye
                    region_w = x2 - x1
                    region_h = y2 - y1
                    eye_region = result[y1:y2, x1:x2].copy()

                    if eye_region.size == 0:
                        continue

                    # Calculate eye center in region coordinates
                    center_x = eye_x - x1
                    center_y = eye_y - y1

                    # Create bulge effect using radial distortion
                    # This makes the eye area appear larger/enlarged
                    scale_factor = 1.0 + (intensity * 0.7)  # Scale up to 1.7x at max intensity (more noticeable)

                    # Create coordinate maps for remapping
                    map_x = np.zeros((region_h, region_w), dtype=np.float32)
                    map_y = np.zeros((region_h, region_w), dtype=np.float32)

                    for y in range(region_h):
                        for x in range(region_w):
                            # Calculate distance from eye center
                            dx = x - center_x
                            dy = y - center_y
                            distance = np.sqrt(dx*dx + dy*dy)

                            if distance == 0:
                                map_x[y, x] = x
                                map_y[y, x] = y
                                continue

                            # Apply radial distortion (bulge effect)
                            # Pixels closer to center are pulled outward more
                            if distance < eye_radius:
                                # Smooth falloff function
                                factor = (1.0 - (distance / eye_radius)) ** 2
                                scale = 1.0 - (factor * (scale_factor - 1.0))

                                # New position (scaled from center)
                                new_x = center_x + dx / scale
                                new_y = center_y + dy / scale

                                # Clamp to region bounds
                                map_x[y, x] = np.clip(new_x, 0, region_w - 1)
                                map_y[y, x] = np.clip(new_y, 0, region_h - 1)
                            else:
                                # Outside radius, no distortion
                                map_x[y, x] = x
                                map_y[y, x] = y

                    # Apply the warp using remap
                    warped = cv2.remap(eye_region, map_x, map_y, cv2.INTER_LINEAR)

                    # Add slight sharpening to enhanced eyes
                    kernel = np.array([[-0.5,-0.5,-0.5],
                                      [-0.5,  5,-0.5],
                                      [-0.5,-0.5,-0.5]])
                    warped = cv2.filter2D(warped, -1, kernel)

                    # Slight brightness increase
                    warped = cv2.convertScaleAbs(warped, alpha=1.02, beta=2)

                    # Blend with smooth edges to avoid harsh boundaries
                    mask = np.zeros((region_h, region_w), dtype=np.float32)
                    for y in range(region_h):
                        for x in range(region_w):
                            dx = x - center_x
                            dy = y - center_y
                            distance = np.sqrt(dx*dx + dy*dy)
                            if distance < eye_radius:
                                # Smooth edge falloff
                                mask[y, x] = 1.0 - (distance / eye_radius) ** 2

                    mask = cv2.GaussianBlur(mask, (15, 15), 5)
                    mask_3ch = cv2.merge([mask, mask, mask])

                    blended = (warped * mask_3ch + eye_region * (1 - mask_3ch)).astype(np.uint8)

                    result[y1:y2, x1:x2] = blended

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

    def apply_lip_color(self, frame: np.ndarray, intensity: float = 0.5, color: str = 'red') -> np.ndarray:
        """
        Apply color to lips (red, pink, etc.)

        Args:
            frame: Input frame
            intensity: Color intensity (0.0 - 1.0)
            color: Lip color ('red', 'pink', 'coral', 'nude')

        Returns:
            Frame with colored lips
        """
        try:
            faces = self.detect_faces(frame)

            if not faces:
                return frame

            result = frame.copy().astype(float)

            # Define lip colors in BGR format (OpenCV uses BGR, not RGB)
            lip_colors = {
                'red': (0, 0, 255),        # Pure bright red
                'pink': (180, 140, 255),   # Light pink
                'coral': (100, 140, 255),  # Coral
                'nude': (140, 160, 200),   # Nude/natural
                'berry': (85, 60, 180)     # Berry/wine
            }

            target_color = lip_colors.get(color, lip_colors['red'])

            for face in faces:
                landmarks = face['landmarks']

                # Get lip landmarks (MediaPipe lip indices)
                upper_outer = [61, 185, 40, 39, 37, 0, 267, 269, 270, 409, 291]
                lower_outer = [146, 91, 181, 84, 17, 314, 405, 321, 375, 291]
                upper_inner = [78, 191, 80, 81, 82, 13, 312, 311, 310, 415, 308]
                lower_inner = [78, 95, 88, 178, 87, 14, 317, 402, 318, 324, 308]

                # Combine all lip points
                lip_indices = list(set(upper_outer + lower_outer + upper_inner + lower_inner))

                # Get lip contour points
                lip_points = []
                for idx in lip_indices:
                    if idx < len(landmarks):
                        lip_points.append((landmarks[idx]['x'], landmarks[idx]['y']))

                if len(lip_points) < 3:
                    continue

                # Create lip mask on FULL FRAME (not rectangular region)
                lip_points_np = np.array(lip_points, dtype=np.int32)
                mask = np.zeros(frame.shape[:2], dtype=np.uint8)
                cv2.fillConvexPoly(mask, cv2.convexHull(lip_points_np), 255)

                # Apply strong smoothing for seamless edges
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
                mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
                mask = cv2.GaussianBlur(mask, (31, 31), 10)

                # Normalize mask for blending
                mask_normalized = mask.astype(float) / 255.0
                mask_3ch = np.stack([mask_normalized] * 3, axis=-1)

                # For red lips - work directly on full frame (no rectangular extraction!)
                if color == 'red':
                    # Step 1: Suppress blue/green channels by 80-95%
                    base_suppression = 0.85  # 85% removal

                    result[:, :, 0] = result[:, :, 0] * (1 - mask_3ch[:, :, 0] * base_suppression)  # Blue
                    result[:, :, 1] = result[:, :, 1] * (1 - mask_3ch[:, :, 1] * base_suppression)  # Green

                    # Step 2: Add red boost
                    red_boost = intensity * 100
                    result[:, :, 2] = np.clip(
                        result[:, :, 2] + (mask_3ch[:, :, 2] * red_boost),
                        0, 255
                    )
                else:
                    # Standard blending for other colors
                    for c in range(3):
                        result[:, :, c] = (
                            result[:, :, c] * (1 - mask_3ch[:, :, c] * intensity) +
                            target_color[c] * mask_3ch[:, :, c] * intensity
                        )

            return result.astype(np.uint8)

        except Exception as e:
            logger.error(f"Lip color error: {e}")
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
        Uses precise face contour instead of bounding box for better edge preservation

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

            # Create mask for all faces using actual face contour
            mask = np.zeros(frame.shape[:2], dtype=np.uint8)

            for face in faces:
                landmarks = face['landmarks']

                # Use face contour landmarks for precise masking
                # Face oval landmarks: 10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288,
                #                      397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136,
                #                      172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109
                face_contour_indices = [
                    10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288,
                    397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136,
                    172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109
                ]

                # Get contour points
                contour_points = []
                for idx in face_contour_indices:
                    if idx < len(landmarks):
                        contour_points.append([landmarks[idx]['x'], landmarks[idx]['y']])

                if len(contour_points) < 3:
                    # Fallback to bounding box if contour extraction fails
                    bbox = face['bbox']
                    padding = 50
                    x1 = max(0, bbox['x1'] - padding)
                    y1 = max(0, bbox['y1'] - padding)
                    x2 = min(frame.shape[1], bbox['x2'] + padding)
                    y2 = min(frame.shape[0], bbox['y2'] + padding)
                    cv2.rectangle(mask, (x1, y1), (x2, y2), 255, -1)
                else:
                    # Draw filled polygon for face contour
                    contour_np = np.array(contour_points, dtype=np.int32)

                    # Expand contour slightly to include more of face/hair
                    # Calculate center
                    center_x = int(np.mean([p[0] for p in contour_points]))
                    center_y = int(np.mean([p[1] for p in contour_points]))

                    # Scale points outward from center
                    expanded_contour = []
                    for point in contour_points:
                        dx = point[0] - center_x
                        dy = point[1] - center_y
                        # Expand by 30%
                        new_x = int(center_x + dx * 1.3)
                        new_y = int(center_y + dy * 1.3)
                        expanded_contour.append([new_x, new_y])

                    expanded_contour_np = np.array(expanded_contour, dtype=np.int32)
                    cv2.fillPoly(mask, [expanded_contour_np], 255)

            # Apply morphological operations to smooth mask
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

            # Apply stronger Gaussian blur to mask edges for very smooth transition
            mask = cv2.GaussianBlur(mask, (41, 41), 15)

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
