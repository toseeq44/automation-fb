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
            # Step 1: Extract video frames for analysis
            frames = self._extract_key_frames(video_path, max_frames=3)
            logger.info(f"   Extracted {len(frames)} key frames")

            # Step 2: Extract text from frames (lightweight OCR)
            ocr_texts = self._extract_text_from_frames(frames)
            results['ocr_text'] = ocr_texts
            logger.info(f"   Found {len(ocr_texts)} text items via OCR")

            # Step 3: Detect language from text
            if ocr_texts:
                lang_result = self._detect_language_from_text(ocr_texts)
                results['language'] = lang_result['language']
                results['language_name'] = lang_result['language_name']
                results['language_confidence'] = lang_result['confidence']
                logger.info(f"   Language detected: {lang_result['language_name']} ({lang_result['confidence']:.0%})")

            # Step 4: Analyze content via Groq Vision API (if available)
            if self.groq_client and frames:
                api_analysis = self._analyze_via_groq_vision(frames[0], video_metadata)
                if api_analysis:
                    results.update(api_analysis)
                    logger.info(f"   API analysis: {api_analysis.get('content_description', 'N/A')}")

            # Step 5: Fallback heuristics if API not available
            else:
                heuristic_analysis = self._heuristic_analysis(video_metadata, ocr_texts)
                results.update(heuristic_analysis)
                logger.info(f"   Heuristic analysis: {heuristic_analysis.get('niche', 'general')}")

            logger.info("✅ Content analysis complete (API-based)")
            return results

        except Exception as e:
            logger.error(f"❌ Content analysis failed: {e}")
            return results

    def _extract_key_frames(self, video_path: str, max_frames: int = 3) -> List[str]:
        """Extract key frames from video (lightweight, no torch needed)"""
        try:
            import cv2
            import tempfile
            import os

            cap = cv2.VideoCapture(video_path)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

            if total_frames == 0:
                return []

            # Extract frames at intervals
            frame_paths = []
            interval = max(1, total_frames // max_frames)

            for i in range(0, total_frames, interval):
                if len(frame_paths) >= max_frames:
                    break

                cap.set(cv2.CAP_PROP_POS_FRAMES, i)
                ret, frame = cap.read()

                if ret:
                    # Save frame temporarily
                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
                    cv2.imwrite(temp_file.name, frame)
                    frame_paths.append(temp_file.name)

            cap.release()
            return frame_paths

        except Exception as e:
            logger.warning(f"Frame extraction failed: {e}")
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
        Analyze video content using Groq Vision API

        Args:
            frame_path: Path to video frame image
            metadata: Video metadata

        Returns:
            Analysis results or None if API unavailable
        """
        if not self.groq_client:
            return None

        try:
            # Encode frame as base64
            with open(frame_path, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode('utf-8')

            # Call Groq Vision API
            prompt = f"""Analyze this video frame and provide:

1. What objects/items are visible? (list them)
2. What action/activity is happening?
3. Is there a person visible? (yes/no)
4. What type of scene is this? (indoor/outdoor/kitchen/office/etc)
5. What niche/category does this belong to? (cooking/gaming/tutorial/review/vlog/fitness/music/beauty/general)
6. Brief content description (1 sentence)

Video duration: {metadata.get('duration', 'unknown')}
Video resolution: {metadata.get('resolution', 'unknown')}

Respond in this exact format:
OBJECTS: [comma-separated list]
ACTION: [single action]
PERSON: [yes/no]
SCENE: [scene type]
NICHE: [niche category]
DESCRIPTION: [brief description]
"""

            response = self.groq_client.chat.completions.create(
                model="llama-3.2-90b-vision-preview",  # Groq vision model
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

            # Parse response
            analysis_text = response.choices[0].message.content.strip()
            return self._parse_vision_response(analysis_text)

        except Exception as e:
            logger.warning(f"Groq Vision API failed: {e}")
            return None

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

        for niche, keywords in niche_keywords.items():
            matches = sum(1 for kw in keywords if kw in combined_lower)
            if matches > best_score:
                best_score = matches
                best_niche = niche

        if best_score >= 1:  # Even 1 match is enough (lowered threshold)
            result['niche'] = best_niche
            result['niche_confidence'] = min(0.9, 0.4 + (best_score * 0.15))

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
