"""
API-Based Content Analyzer (No PyTorch Required!)
Uses Groq Vision API + Text API for content analysis
Works with ANY Python version, no DLL dependencies
"""

import base64
from pathlib import Path
from typing import Dict, List, Optional
import re
from modules.logging.logger import get_logger

logger = get_logger(__name__)


class APIContentAnalyzer:
    """
    Content analyzer using cloud APIs instead of local models
    No PyTorch, Whisper, or Transformers needed!
    """

    def __init__(self, groq_client=None):
        """
        Initialize API-based analyzer

        Args:
            groq_client: Groq API client instance
        """
        self.groq_client = groq_client

        # Language detection patterns
        self.language_patterns = {
            'ur': r'[\u0600-\u06FF]',  # Urdu/Arabic script
            'hi': r'[\u0900-\u097F]',  # Hindi/Devanagari
            'ar': r'[\u0600-\u06FF]',  # Arabic
            'zh': r'[\u4E00-\u9FFF]',  # Chinese
            'ja': r'[\u3040-\u309F\u30A0-\u30FF]',  # Japanese
            'ko': r'[\uAC00-\uD7AF]',  # Korean
            'ru': r'[\u0400-\u04FF]',  # Russian/Cyrillic
        }

        # Language-specific keywords
        self.language_keywords = {
            'pt': ['em', 'de', 'para', 'com', 'fazer', 'como', 'receita', 'minutos'],
            'fr': ['le', 'la', 'de', 'pour', 'avec', 'faire', 'comment', 'recette', 'minutes'],
            'es': ['el', 'la', 'de', 'para', 'con', 'hacer', 'cómo', 'receta', 'minutos'],
            'de': ['der', 'die', 'das', 'mit', 'für', 'machen', 'wie', 'rezept', 'minuten'],
            'it': ['il', 'la', 'di', 'per', 'con', 'fare', 'come', 'ricetta', 'minuti'],
        }

    def analyze_video_content(self, video_path: str, video_metadata: Dict) -> Dict:
        """
        Analyze video content using API-based approach

        Args:
            video_path: Path to video file
            video_metadata: Video metadata dict

        Returns:
            Analysis results dict:
            {
                'language': str,
                'language_name': str,
                'language_confidence': float,
                'niche': str,
                'niche_confidence': float,
                'content_description': str,
                'detected_objects': List[str],
                'detected_actions': List[str],
                'keywords': List[str],
                'ocr_text': List[str],
                'has_person': bool,
                'scene_type': str
            }
        """
        logger.info("📊 Analyzing video content via API (no local models)...")

        results = {
            'language': 'en',
            'language_name': 'English',
            'language_confidence': 0.5,
            'niche': 'general',
            'niche_confidence': 0.3,
            'content_description': '',
            'detected_objects': [],
            'detected_actions': [],
            'keywords': [],
            'ocr_text': [],
            'has_person': False,
            'scene_type': 'unknown'
        }

        try:
            # Step 1: Audio analysis using Groq Whisper API (PRIORITY for language!)
            audio_analysis = None
            if self.groq_client:
                audio_analysis = self._analyze_audio_via_groq(video_path, video_metadata)
                if audio_analysis:
                    # Audio provides BEST language detection
                    if not audio_analysis.get('is_music', False):
                        results['language'] = audio_analysis.get('language', 'en')
                        results['language_name'] = audio_analysis.get('language_name', 'English')
                        results['language_confidence'] = audio_analysis.get('language_confidence', 0.9)
                        results['keywords'].extend(audio_analysis.get('keywords', []))
                        logger.info(f"   🎙️  Audio: {audio_analysis.get('transcription_preview', 'N/A')}")
                        logger.info(f"   🌐 Language (from audio): {results['language_name']} ({results['language_confidence']:.0%})")
                    else:
                        logger.info(f"   🎵 Music detected - ignoring audio for language detection")

            # Step 2: Extract video frames (ONE PER SECOND, up to 60 seconds)
            all_frames = self._extract_key_frames(video_path, max_frames=60)

            if not all_frames:
                logger.warning("   ⚠️  No frames extracted from video!")

            # Step 3: Extract text from ALL frames (comprehensive OCR)
            ocr_texts = []
            if all_frames:
                logger.info(f"   Running OCR on {len(all_frames)} frames...")
                ocr_texts = self._extract_text_from_frames(all_frames)
                results['ocr_text'] = ocr_texts
                if ocr_texts:
                    logger.info(f"   ✅ Found {len(ocr_texts)} unique text items via OCR")

            # Step 4: Detect language from text (fallback if no audio)
            if not audio_analysis and ocr_texts:
                lang_result = self._detect_language_from_text(ocr_texts)
                results['language'] = lang_result['language']
                results['language_name'] = lang_result['language_name']
                results['language_confidence'] = lang_result['confidence']
                logger.info(f"   Language (from text): {lang_result['language_name']} ({lang_result['confidence']:.0%})")

            # Step 5: Analyze content via Groq Vision API (use REPRESENTATIVE frames)
            # Use beginning, middle, end frames for vision analysis (cost-efficient)
            api_success = False
            if self.groq_client and all_frames:
                representative_frames = self._select_representative_frames(all_frames, count=3)
                logger.info(f"   Analyzing {len(representative_frames)} representative frames with Vision API...")

                # Try vision analysis on first representative frame
                api_analysis = self._analyze_via_groq_vision(representative_frames[0], video_metadata)
                if api_analysis:
                    results.update(api_analysis)
                    logger.info(f"   👁️  Visual: {api_analysis.get('content_description', 'N/A')}")
                    api_success = True

            # Step 6: Fallback heuristics if API failed or not available
            if not api_success:
                heuristic_analysis = self._heuristic_analysis(video_metadata, ocr_texts)
                results.update(heuristic_analysis)
                logger.info(f"   🔄 Heuristic fallback: {heuristic_analysis.get('niche', 'general')}")

            logger.info("✅ Content analysis complete (API-based)")
            return results

        except Exception as e:
            logger.error(f"❌ Content analysis failed: {e}")
            return results

    def _select_representative_frames(self, all_frames: List[str], count: int = 3) -> List[str]:
        """
        Select representative frames from all extracted frames
        Returns: beginning, middle, and end frames

        Args:
            all_frames: List of all frame paths
            count: Number of frames to select (default 3)

        Returns:
            List of selected frame paths
        """
        if not all_frames:
            return []

        if len(all_frames) <= count:
            return all_frames

        # Select evenly distributed frames
        indices = []
        if count >= 1:
            indices.append(0)  # Beginning
        if count >= 2:
            indices.append(len(all_frames) // 2)  # Middle
        if count >= 3:
            indices.append(len(all_frames) - 1)  # End

        return [all_frames[i] for i in indices]

    def _extract_key_frames(self, video_path: str, max_frames: int = 60) -> List[str]:
        """
        Extract frames from video - ONE FRAME PER SECOND

        Example: 59 second video = 59 frames

        Args:
            video_path: Path to video file
            max_frames: Maximum frames to extract (default 60 = 1 minute)

        Returns:
            List of frame file paths
        """
        try:
            import cv2
            import tempfile
            import os

            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

            if total_frames == 0 or fps == 0:
                cap.release()
                return []

            # Calculate video duration in seconds
            duration_seconds = int(total_frames / fps)

            # Extract ONE frame per second (up to max_frames)
            frames_to_extract = min(duration_seconds, max_frames)

            logger.info(f"   Extracting {frames_to_extract} frames (1 per second) from {duration_seconds}s video")

            frame_paths = []
            for second in range(frames_to_extract):
                # Get frame at this second
                frame_number = int(second * fps)

                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
                ret, frame = cap.read()

                if ret:
                    # Save frame temporarily
                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
                    cv2.imwrite(temp_file.name, frame)
                    frame_paths.append(temp_file.name)

            cap.release()
            logger.info(f"   ✅ Extracted {len(frame_paths)} frames successfully")
            return frame_paths

        except Exception as e:
            logger.error(f"   ❌ Frame extraction failed: {e}")
            return []

    def _extract_text_from_frames(self, frame_paths: List[str]) -> List[str]:
        """Extract text from frames using pytesseract (no torch needed)"""
        try:
            import pytesseract
            from PIL import Image

            all_text = []

            for frame_path in frame_paths:
                try:
                    img = Image.open(frame_path)
                    text = pytesseract.image_to_string(img, lang='eng+ara+hin+chi_sim+jpn+kor')

                    # Clean and filter text
                    lines = [line.strip() for line in text.split('\n') if line.strip()]
                    all_text.extend(lines)

                except Exception as e:
                    logger.debug(f"OCR failed for frame: {e}")

            # Remove duplicates, keep unique
            unique_text = list(set(all_text))[:20]  # Max 20 unique texts
            return unique_text

        except ImportError:
            logger.warning("pytesseract not available, skipping OCR")
            return []
        except Exception as e:
            logger.warning(f"Text extraction failed: {e}")
            return []

    def _detect_language_from_text(self, texts: List[str]) -> Dict:
        """
        Detect language from extracted text using pattern matching

        Returns:
            {
                'language': str (ISO code),
                'language_name': str,
                'confidence': float
            }
        """
        if not texts:
            return {'language': 'en', 'language_name': 'English', 'confidence': 0.3}

        combined_text = ' '.join(texts).lower()

        # Check script patterns (high confidence)
        for lang, pattern in self.language_patterns.items():
            if re.search(pattern, combined_text):
                lang_names = {
                    'ur': 'Urdu', 'hi': 'Hindi', 'ar': 'Arabic',
                    'zh': 'Chinese', 'ja': 'Japanese', 'ko': 'Korean', 'ru': 'Russian'
                }
                return {
                    'language': lang,
                    'language_name': lang_names.get(lang, lang.upper()),
                    'confidence': 0.9
                }

        # Check keyword patterns (medium confidence)
        for lang, keywords in self.language_keywords.items():
            matches = sum(1 for kw in keywords if kw in combined_text)
            if matches >= 3:  # At least 3 keyword matches
                lang_names = {
                    'pt': 'Portuguese', 'fr': 'French', 'es': 'Spanish',
                    'de': 'German', 'it': 'Italian'
                }
                return {
                    'language': lang,
                    'language_name': lang_names.get(lang, lang.upper()),
                    'confidence': 0.7
                }

        # Default to English
        return {'language': 'en', 'language_name': 'English', 'confidence': 0.5}

    def _analyze_via_groq_vision(self, frame_path: str, metadata: Dict) -> Optional[Dict]:
        """
        Analyze video content using multiple Vision API providers

        Priority:
        1. OpenAI GPT-4 Vision (most reliable)
        2. Groq Vision models (if available)
        3. HuggingFace BLIP (free, no auth needed)

        Args:
            frame_path: Path to video frame image
            metadata: Video metadata

        Returns:
            Analysis results or None if all APIs fail
        """
        if not self.groq_client:
            return None

        # Try OpenAI Vision API first (most reliable)
        result = self._try_openai_vision(frame_path, metadata)
        if result:
            return result

        # Try Groq Vision models
        result = self._try_groq_vision(frame_path, metadata)
        if result:
            return result

        # Try HuggingFace BLIP (free, no auth)
        result = self._try_huggingface_vision(frame_path, metadata)
        if result:
            return result

        logger.error("   ❌ All Vision APIs failed")
        return None

    def _try_openai_vision(self, frame_path: str, metadata: Dict) -> Optional[Dict]:
        """Try OpenAI GPT-4 Vision API"""
        try:
            # Check if OpenAI client available
            from openai import OpenAI

            # Try to get API key from environment or config
            import os
            api_key = os.getenv('OPENAI_API_KEY')

            if not api_key:
                logger.debug("   OpenAI API key not found, skipping")
                return None

            client = OpenAI(api_key=api_key)

            # Encode image
            with open(frame_path, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode('utf-8')

            logger.info("   Trying OpenAI GPT-4 Vision API...")

            response = client.chat.completions.create(
                model="gpt-4-vision-preview",
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": """Analyze this video frame. Provide:
1. Objects visible (comma-separated)
2. Main action happening
3. Is person visible? (yes/no)
4. Scene type (kitchen/outdoor/indoor/etc)
5. Content category (cooking/gaming/tutorial/review/vlog/fitness/music/beauty/general)
6. Brief description (1 sentence)

Format:
OBJECTS: [list]
ACTION: [action]
PERSON: [yes/no]
SCENE: [type]
NICHE: [category]
DESCRIPTION: [text]"""
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_data}"
                            }
                        }
                    ]
                }],
                max_tokens=300
            )

            analysis_text = response.choices[0].message.content.strip()
            logger.info("   ✅ OpenAI Vision API success!")
            return self._parse_vision_response(analysis_text)

        except ImportError:
            logger.debug("   OpenAI library not installed")
            return None
        except Exception as e:
            logger.debug(f"   OpenAI Vision failed: {str(e)[:100]}")
            return None

    def _try_groq_vision(self, frame_path: str, metadata: Dict) -> Optional[Dict]:
        """Try Groq Vision models with fallback - UPDATED WITH NEW MODELS"""
        # NEW Groq Vision models (December 2024+)
        vision_models = [
            "llama-4-scout",              # NEW! Llama 4 Scout (vision)
            "llama-4-maverick",           # NEW! Llama 4 Maverick (vision)
            "llama-3.2-90b-vision-preview",  # Old fallback (decommissioned)
            "llama-3.2-11b-vision-preview",   # Old fallback (decommissioned)
            "llava-v1.5-7b-4096-preview"     # Old fallback (decommissioned)
        ]

        try:
            # Encode frame
            with open(frame_path, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode('utf-8')

            prompt = f"""Analyze this video frame and provide:

1. What objects/items are visible? (list them)
2. What action/activity is happening?
3. Is there a person visible? (yes/no)
4. What type of scene is this? (indoor/outdoor/kitchen/office/etc)
5. What niche/category does this belong to? (cooking/gaming/tutorial/review/vlog/fitness/music/beauty/general)
6. Brief content description (1 sentence)

Video duration: {metadata.get('duration', 'unknown')}

Respond in this exact format:
OBJECTS: [comma-separated list]
ACTION: [single action]
PERSON: [yes/no]
SCENE: [scene type]
NICHE: [niche category]
DESCRIPTION: [brief description]
"""

            # Try each Groq model
            for model_name in vision_models:
                try:
                    logger.info(f"   Trying Groq model: {model_name}")
                    response = self.groq_client.chat.completions.create(
                        model=model_name,
                        messages=[{
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{image_data}"
                                    }
                                }
                            ]
                        }],
                        temperature=0.5,
                        max_tokens=300
                    )

                    analysis_text = response.choices[0].message.content.strip()
                    logger.info(f"   ✅ Groq Vision success with: {model_name}")
                    return self._parse_vision_response(analysis_text)

                except Exception as e:
                    if "decommissioned" in str(e):
                        logger.debug(f"   Model {model_name} decommissioned")
                    else:
                        logger.debug(f"   Model {model_name} failed: {str(e)[:100]}")
                    continue

            return None

        except Exception as e:
            logger.debug(f"   Groq Vision failed: {str(e)[:100]}")
            return None

    def _try_huggingface_vision(self, frame_path: str, metadata: Dict) -> Optional[Dict]:
        """Try HuggingFace BLIP model (free, no auth needed)"""
        try:
            import requests
            from PIL import Image

            logger.info("   Trying HuggingFace BLIP (free vision model)...")

            # Use Salesforce BLIP model via HF Inference API
            API_URL = "https://api-inference.huggingface.co/models/Salesforce/blip-image-captioning-large"

            with open(frame_path, "rb") as f:
                data = f.read()

            response = requests.post(API_URL, data=data, timeout=10)

            if response.status_code == 200:
                result = response.json()
                if isinstance(result, list) and len(result) > 0:
                    description = result[0].get('generated_text', '')

                    # Parse description to extract niche
                    niche = self._infer_niche_from_description(description)

                    logger.info(f"   ✅ HuggingFace Vision success!")
                    logger.info(f"   Description: {description}")

                    return {
                        'content_description': description,
                        'niche': niche,
                        'niche_confidence': 0.6,
                        'detected_objects': [],
                        'detected_actions': [],
                        'has_person': 'person' in description.lower(),
                        'scene_type': 'unknown'
                    }

            return None

        except Exception as e:
            logger.debug(f"   HuggingFace Vision failed: {str(e)[:100]}")
            return None

    def _infer_niche_from_description(self, description: str) -> str:
        """Infer niche from image description"""
        desc_lower = description.lower()

        niche_keywords = {
            'cooking': ['cook', 'food', 'kitchen', 'recipe', 'meal', 'dish', 'eat'],
            'gaming': ['game', 'play', 'screen', 'controller', 'gaming'],
            'fitness': ['workout', 'exercise', 'gym', 'fitness', 'training'],
            'music': ['music', 'instrument', 'guitar', 'piano', 'singing'],
            'tutorial': ['tutorial', 'learning', 'teaching', 'demonstration']
        }

        for niche, keywords in niche_keywords.items():
            if any(kw in desc_lower for kw in keywords):
                return niche

        return 'general'

    def _parse_vision_response(self, response_text: str) -> Dict:
        """Parse Groq Vision API response into structured data"""
        result = {
            'detected_objects': [],
            'detected_actions': [],
            'has_person': False,
            'scene_type': 'unknown',
            'niche': 'general',
            'niche_confidence': 0.7,
            'content_description': ''
        }

        try:
            lines = response_text.split('\n')
            for line in lines:
                line = line.strip()

                if line.startswith('OBJECTS:'):
                    objects = line.replace('OBJECTS:', '').strip()
                    result['detected_objects'] = [obj.strip() for obj in objects.split(',') if obj.strip()]

                elif line.startswith('ACTION:'):
                    action = line.replace('ACTION:', '').strip()
                    result['detected_actions'] = [action] if action else []

                elif line.startswith('PERSON:'):
                    person = line.replace('PERSON:', '').strip().lower()
                    result['has_person'] = 'yes' in person

                elif line.startswith('SCENE:'):
                    result['scene_type'] = line.replace('SCENE:', '').strip()

                elif line.startswith('NICHE:'):
                    result['niche'] = line.replace('NICHE:', '').strip().lower()

                elif line.startswith('DESCRIPTION:'):
                    result['content_description'] = line.replace('DESCRIPTION:', '').strip()

        except Exception as e:
            logger.warning(f"Failed to parse vision response: {e}")

        return result

    def _heuristic_analysis(self, metadata: Dict, ocr_texts: List[str]) -> Dict:
        """
        Improved fallback heuristic analysis when API not available
        Extracts actual content from filename, OCR text, and metadata
        """
        import re

        filename = metadata.get('filename', '')
        combined_text = (filename + ' ' + ' '.join(ocr_texts))

        # Initialize result
        result = {
            'niche': 'general',
            'niche_confidence': 0.5,
            'detected_objects': [],
            'detected_actions': [],
            'has_person': False,
            'scene_type': 'unknown',
            'content_description': ''
        }

        # ========================================
        # STEP 1: Extract actual content from filename and OCR
        # ========================================

        # Clean filename: remove file extension, special chars
        clean_name = re.sub(r'\.[a-zA-Z0-9]+$', '', filename)  # Remove extension
        clean_name = re.sub(r'[_\-\.]', ' ', clean_name)  # Replace _ - . with space
        clean_name = re.sub(r'[^\w\s]', '', clean_name)  # Remove special chars

        # Extract meaningful words (ignore generic terms)
        generic_terms = {
            'amazing', 'content', 'video', 'clip', 'new', 'latest', 'best',
            'story', 'see', 'watch', 'check', 'viral', 'trending', 'secs', 'seconds'
        }

        words = clean_name.lower().split()
        meaningful_words = [w for w in words if w not in generic_terms and len(w) > 2]

        # Combine with OCR text
        all_text = ' '.join(meaningful_words + ocr_texts)

        # ========================================
        # STEP 2: Detect objects/actions from text
        # ========================================

        # Common objects
        object_keywords = {
            # Food items
            'food', 'recipe', 'pasta', 'pizza', 'burger', 'cake', 'bread', 'chicken',
            'rice', 'noodles', 'salad', 'soup', 'dessert', 'coffee', 'tea',
            # People
            'man', 'woman', 'person', 'chef', 'player', 'gamer', 'trainer',
            # Objects
            'phone', 'laptop', 'car', 'bike', 'camera', 'guitar', 'piano'
        }

        action_keywords = {
            # Cooking actions
            'cook', 'cooking', 'bake', 'fry', 'grill', 'boil', 'mix', 'chop',
            # Activity actions
            'play', 'playing', 'run', 'running', 'dance', 'dancing', 'workout',
            'exercise', 'sing', 'singing', 'teach', 'teaching', 'review', 'unbox'
        }

        detected_objects = [obj for obj in object_keywords if obj in all_text.lower()]
        detected_actions = [act for act in action_keywords if act in all_text.lower()]

        result['detected_objects'] = detected_objects[:5]  # Top 5
        result['detected_actions'] = detected_actions[:3]  # Top 3

        # ========================================
        # STEP 3: Niche detection (improved)
        # ========================================

        niche_keywords = {
            'cooking': ['cook', 'recipe', 'food', 'kitchen', 'chef', 'bake', 'fry', 'taste',
                       'pasta', 'pizza', 'burger', 'cake', 'chicken', 'delicious'],
            'gaming': ['game', 'gaming', 'play', 'player', 'level', 'win', 'score', 'gamer',
                      'controller', 'console', 'mobile', 'pubg', 'fortnite'],
            'tutorial': ['tutorial', 'how to', 'guide', 'learn', 'teach', 'step', 'lesson',
                        'tips', 'tricks', 'hacks', 'diy'],
            'review': ['review', 'unbox', 'unboxing', 'test', 'testing', 'vs', 'comparison',
                      'honest', 'opinion', 'pros', 'cons'],
            'fitness': ['workout', 'fitness', 'exercise', 'gym', 'yoga', 'cardio', 'abs',
                       'training', 'muscle', 'weight', 'strength'],
            'music': ['music', 'song', 'beat', 'cover', 'sing', 'singing', 'guitar',
                     'piano', 'drum', 'rap', 'dance'],
            'vlog': ['vlog', 'day in', 'life', 'daily', 'routine', 'morning', 'night',
                    'lifestyle', 'behind', 'scenes'],
            'entertainment': ['funny', 'comedy', 'prank', 'meme', 'joke', 'laugh', 'fun',
                             'entertainment', 'react', 'reaction']
        }

        combined_lower = all_text.lower()
        best_niche = 'general'
        best_score = 0

        # DEBUG: Show what text we're analyzing
        logger.debug(f"   DEBUG: Analyzing text: '{combined_lower[:100]}'")

        for niche, keywords in niche_keywords.items():
            matches = sum(1 for kw in keywords if kw in combined_lower)
            if matches > 0:
                logger.debug(f"   DEBUG: {niche} = {matches} matches")
            if matches > best_score:
                best_score = matches
                best_niche = niche

        if best_score >= 1:  # Even 1 match is enough (lowered threshold)
            result['niche'] = best_niche
            result['niche_confidence'] = min(0.9, 0.4 + (best_score * 0.15))
            logger.info(f"   ✅ Niche detected: {best_niche} ({matches} keywords matched)")

        # ========================================
        # STEP 4: Build content description
        # ========================================

        # Use detected objects/actions to build description
        if detected_objects or detected_actions:
            desc_parts = []
            if detected_actions:
                desc_parts.append(detected_actions[0])
            if detected_objects:
                desc_parts.append(detected_objects[0])

            result['content_description'] = ' '.join(desc_parts)
        else:
            # Use first few meaningful words from filename
            if meaningful_words:
                result['content_description'] = ' '.join(meaningful_words[:3])

        # ========================================
        # STEP 5: Person detection
        # ========================================

        person_indicators = ['person', 'man', 'woman', 'people', 'chef', 'player', 'i ', 'my ', 'me ']
        result['has_person'] = any(ind in combined_lower for ind in person_indicators)

        logger.info(f"   Heuristic analysis: {result['niche']} (confidence: {result['niche_confidence']:.0%})")
        if result['content_description']:
            logger.info(f"   Content: {result['content_description']}")
        if detected_objects:
            logger.info(f"   Objects: {', '.join(detected_objects[:3])}")
        if detected_actions:
            logger.info(f"   Actions: {', '.join(detected_actions[:3])}")

        return result

    def _analyze_audio_via_groq(self, video_path: str, metadata: Dict) -> Optional[Dict]:
        """
        Analyze audio using Groq Whisper API
        - Transcribes audio
        - Detects language (MOST ACCURATE!)
        - Extracts content keywords
        - Detects if music (to ignore)

        Returns:
            Dict with audio analysis or None if failed
        """
        try:
            # Check imports first
            try:
                import tempfile
                import os
                from moviepy.editor import VideoFileClip
            except ImportError as ie:
                logger.warning("   ⚠️  MoviePy not installed - audio analysis disabled")
                logger.warning("   💡 Install: pip install moviepy")
                logger.warning("   📌 Audio analysis provides accurate language detection!")
                return None

            logger.info("🎙️  Analyzing audio with Groq Whisper API...")

            # Step 1: Extract audio from video (first 60 seconds for speed)
            duration = metadata.get('duration', 0)
            sample_duration = min(60, duration) if duration > 0 else 60

            with tempfile.TemporaryDirectory() as temp_dir:
                audio_path = os.path.join(temp_dir, 'audio.mp3')

                # Extract audio using moviepy
                video_clip = VideoFileClip(video_path)
                audio_clip = video_clip.audio

                if not audio_clip:
                    logger.warning("   ⚠️  No audio track found in video")
                    return None

                # Sample first 60 seconds
                if duration > sample_duration:
                    audio_clip = audio_clip.subclip(0, sample_duration)

                audio_clip.write_audiofile(audio_path, logger=None, verbose=False)
                audio_clip.close()
                video_clip.close()

                # Step 2: Transcribe using Groq Whisper API
                # Try Turbo model first (faster), fall back to standard
                whisper_models = ["whisper-large-v3-turbo", "whisper-large-v3"]
                transcription = None

                for model in whisper_models:
                    try:
                        with open(audio_path, 'rb') as audio_file:
                            transcription = self.groq_client.audio.transcriptions.create(
                                file=audio_file,
                                model=model,
                                response_format="verbose_json",  # Get language info
                                language=None  # Auto-detect
                            )
                        logger.info(f"   ✅ Using Whisper model: {model}")
                        break
                    except Exception as e:
                        if model == whisper_models[-1]:  # Last model failed
                            raise
                        logger.debug(f"   Model {model} failed, trying next...")
                        continue

                # Step 3: Parse results
                transcription_text = transcription.text.strip()
                detected_language = transcription.language  # ISO code (e.g., 'en', 'pt', 'ur')

                # Language code to name mapping
                LANGUAGE_NAMES = {
                    'en': 'English', 'pt': 'Portuguese', 'fr': 'French',
                    'es': 'Spanish', 'ur': 'Urdu', 'hi': 'Hindi', 'ar': 'Arabic',
                    'zh': 'Chinese', 'ja': 'Japanese', 'ko': 'Korean',
                    'de': 'German', 'it': 'Italian', 'ru': 'Russian'
                }

                language_name = LANGUAGE_NAMES.get(detected_language, detected_language.upper())

                # Step 4: Detect if music (low confidence in transcription)
                is_music = self._is_music_audio(transcription_text, transcription)

                if is_music:
                    logger.info("   🎵 Music detected (no speech)")
                    return {
                        'is_music': True,
                        'language': 'en',  # Default
                        'language_name': 'English',
                        'language_confidence': 0.3,
                        'transcription': '',
                        'keywords': []
                    }

                # Step 5: Extract keywords from transcription
                keywords = self._extract_keywords_from_text(transcription_text, detected_language)

                logger.info(f"   ✅ Audio transcribed: {len(transcription_text)} chars")
                logger.info(f"   🌐 Language: {language_name} ({detected_language})")

                return {
                    'is_music': False,
                    'language': detected_language,
                    'language_name': language_name,
                    'language_confidence': 0.95,  # Whisper is very accurate
                    'transcription': transcription_text,
                    'transcription_preview': transcription_text[:100] + '...' if len(transcription_text) > 100 else transcription_text,
                    'keywords': keywords
                }

        except Exception as e:
            logger.error(f"   ❌ Audio analysis failed: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None

    def _is_music_audio(self, transcription_text: str, transcription_obj) -> bool:
        """
        Detect if audio is primarily music (no speech)

        Indicators:
        - Very short transcription (< 10 chars)
        - Repetitive patterns
        - Low confidence
        - Musical terms only
        """
        # Empty or very short transcription = likely music
        if len(transcription_text.strip()) < 10:
            return True

        # Check for musical patterns
        musical_terms = ['[music]', '(music)', 'instrumental', 'beat', 'melody']
        if any(term in transcription_text.lower() for term in musical_terms):
            return True

        # Check for repetitive characters (instrumental sounds transcribed)
        if len(set(transcription_text.lower().replace(' ', ''))) < 5:
            return True

        return False

    def _extract_keywords_from_text(self, text: str, language: str = 'en') -> List[str]:
        """Extract meaningful keywords from transcription"""
        import re

        # Common stopwords per language
        stopwords = {
            'en': {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                   'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were', 'be', 'been',
                   'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they'},
            'pt': {'o', 'a', 'de', 'do', 'da', 'em', 'para', 'com', 'por', 'um', 'uma',
                   'os', 'as', 'dos', 'das', 'no', 'na', 'nos', 'nas', 'e', 'ou', 'mas'},
            'es': {'el', 'la', 'de', 'del', 'en', 'para', 'con', 'por', 'un', 'una',
                   'los', 'las', 'y', 'o', 'pero', 'al'},
            'fr': {'le', 'la', 'de', 'du', 'des', 'en', 'pour', 'avec', 'par', 'un', 'une',
                   'les', 'et', 'ou', 'mais'},
            'ur': {'کا', 'کی', 'کے', 'میں', 'پر', 'سے', 'کو', 'نے', 'ہے', 'ہیں', 'تھا', 'تھے'},
            'hi': {'का', 'की', 'के', 'में', 'पर', 'से', 'को', 'ने', 'है', 'हैं', 'था', 'थे'},
            'ar': {'في', 'من', 'إلى', 'على', 'عن', 'هو', 'هي', 'كان', 'كانت'}
        }

        lang_stopwords = stopwords.get(language, stopwords['en'])

        # Extract words
        words = re.findall(r'\b\w+\b', text.lower())

        # Filter: length > 3, not stopword, not number
        keywords = []
        for word in words:
            if (len(word) > 3 and
                word not in lang_stopwords and
                not word.isdigit()):
                keywords.append(word)

        # Return top 10 unique keywords
        unique_keywords = list(dict.fromkeys(keywords))  # Preserve order, remove duplicates
        return unique_keywords[:10]
