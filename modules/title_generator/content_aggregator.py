"""
Content Aggregator
Combines audio, visual, and text analysis into unified content understanding
Determines final language, niche, and content elements
"""

from typing import Dict, List, Optional
from modules.logging.logger import get_logger

logger = get_logger(__name__)


class ContentAggregator:
    """
    Aggregates multi-source content analysis (audio + visual + text)
    Produces unified content understanding for title generation
    """

    # Language code to name mapping
    LANGUAGE_NAMES = {
        'en': 'English',
        'pt': 'Portuguese',
        'fr': 'French',
        'es': 'Spanish',
        'ur': 'Urdu',
        'hi': 'Hindi',
        'ar': 'Arabic',
        'de': 'German',
        'it': 'Italian',
        'ja': 'Japanese',
        'ko': 'Korean',
        'zh': 'Chinese',
        'ru': 'Russian',
        'tr': 'Turkish',
        'nl': 'Dutch',
        'pl': 'Polish',
        'sv': 'Swedish',
        'da': 'Danish',
        'fi': 'Finnish',
        'no': 'Norwegian'
    }

    def __init__(self):
        """Initialize content aggregator"""
        pass

    def aggregate_content(
        self,
        audio_analysis: Dict,
        visual_analysis: Dict,
        frame_analysis: Dict,
        metadata: Dict
    ) -> Dict:
        """
        Combine all analysis sources into unified content understanding

        Args:
            audio_analysis: Audio transcription and language detection
            visual_analysis: Visual objects, scene, and niche detection
            frame_analysis: OCR text extraction from frames
            metadata: Video metadata (duration, resolution, etc.)

        Returns:
            Aggregated content dict with:
            {
                'language': str,              # Final detected language (ISO code)
                'language_name': str,         # Human-readable language name
                'language_confidence': float, # Confidence in language detection
                'niche': str,                 # Final video niche
                'niche_confidence': float,    # Confidence in niche detection
                'who': str,                   # Subject/person
                'what': str,                  # Main action/topic
                'where': str,                 # Location/scene
                'time': str,                  # Duration formatted
                'objects': List[str],         # All detected objects
                'keywords': List[str],        # Combined keywords
                'has_person': bool,           # Person visible?
                'content_type': str,          # speed/tutorial/viral/etc.
                'platform_optimized': str     # facebook/tiktok/etc.
            }
        """
        logger.info("🔄 Aggregating multi-source content analysis...")

        # 1. DETERMINE FINAL LANGUAGE
        language_result = self._determine_language(audio_analysis, frame_analysis)

        # 2. DETERMINE FINAL NICHE
        niche_result = self._determine_niche(audio_analysis, visual_analysis, frame_analysis)

        # 3. EXTRACT CONTENT ELEMENTS
        elements = self._extract_content_elements(
            audio_analysis,
            visual_analysis,
            frame_analysis,
            metadata,
            niche_result['niche']
        )

        # 4. DETERMINE CONTENT TYPE
        content_type = self._determine_content_type(metadata, elements)

        # 5. COMBINE KEYWORDS
        all_keywords = self._combine_keywords(audio_analysis, frame_analysis)

        # 6. DETERMINE PLATFORM OPTIMIZATION
        platform = self._determine_platform(metadata, niche_result['niche'])

        # Build aggregated result
        lang_code = language_result['language']
        aggregated = {
            'language': lang_code,
            'language_name': self.LANGUAGE_NAMES.get(lang_code, lang_code.upper()),
            'language_confidence': language_result['confidence'],
            'language_source': language_result['source'],

            'niche': niche_result['niche'],
            'niche_confidence': niche_result['confidence'],
            'niche_source': niche_result['source'],

            'who': elements['who'],
            'what': elements['what'],
            'where': elements['where'],
            'time': elements['time'],
            'difficulty': elements.get('difficulty', ''),
            'result': elements.get('result', ''),

            'objects': visual_analysis.get('objects', []),
            'keywords': all_keywords,
            'actions': visual_analysis.get('actions', []),

            'has_person': visual_analysis.get('has_person', False),
            'has_speech': audio_analysis.get('has_speech', False),
            'has_text': frame_analysis.get('has_text', False),

            'content_type': content_type,
            'platform_optimized': platform,

            'scene': visual_analysis.get('scene', 'unknown'),
            'dominant_colors': visual_analysis.get('dominant_colors', []),

            'transcription': audio_analysis.get('transcription', ''),
            'ocr_text': frame_analysis.get('text_found', [])
        }

        self._log_aggregation_summary(aggregated)

        return aggregated

    def _determine_language(
        self,
        audio_analysis: Dict,
        frame_analysis: Dict
    ) -> Dict:
        """
        Determine final language with confidence score

        Priority:
        1. Audio language (most reliable for spoken content)
        2. OCR text language (if no audio)
        3. Default to English

        Args:
            audio_analysis: Audio analysis with language detection
            frame_analysis: OCR text analysis

        Returns:
            {
                'language': str (ISO code),
                'confidence': float (0-1),
                'source': str ('audio', 'text', 'default')
            }
        """
        # Priority 1: Audio language (most reliable)
        if audio_analysis.get('has_speech', False):
            audio_lang = audio_analysis.get('language', 'en')
            audio_conf = audio_analysis.get('confidence', 0.0)

            if audio_conf > 0.5:  # Confident audio detection
                logger.info(f"📢 Language from audio: {audio_lang} (confidence: {audio_conf:.1%})")
                return {
                    'language': audio_lang,
                    'confidence': audio_conf,
                    'source': 'audio'
                }

        # Priority 2: OCR text language
        if frame_analysis.get('has_text', False):
            text_lang = self._detect_text_language(frame_analysis.get('text_found', []))
            if text_lang:
                logger.info(f"📝 Language from OCR: {text_lang} (estimated confidence: 0.6)")
                return {
                    'language': text_lang,
                    'confidence': 0.6,
                    'source': 'text'
                }

        # Priority 3: Default to English
        logger.info("🌐 No language detected, defaulting to English")
        return {
            'language': 'en',
            'confidence': 0.3,
            'source': 'default'
        }

    def _detect_text_language(self, texts: List[str]) -> Optional[str]:
        """
        Simple language detection from text patterns
        (For better accuracy, could use langdetect library)

        Args:
            texts: List of extracted texts

        Returns:
            ISO language code or None
        """
        if not texts:
            return None

        combined_text = ' '.join(texts[:10]).lower()  # First 10 texts

        # Simple pattern matching (basic detection)
        # Urdu: Arabic script
        if any(ord(c) >= 0x0600 and ord(c) <= 0x06FF for c in combined_text):
            return 'ur'

        # Arabic: Arabic script with specific chars
        if any(ord(c) >= 0x0600 and ord(c) <= 0x06FF for c in combined_text):
            if 'ا' in combined_text or 'ل' in combined_text:
                return 'ar'

        # Hindi: Devanagari script
        if any(ord(c) >= 0x0900 and ord(c) <= 0x097F for c in combined_text):
            return 'hi'

        # Portuguese: specific words
        if any(word in combined_text for word in ['em', 'de', 'fazer', 'receita', 'como']):
            return 'pt'

        # French: specific words
        if any(word in combined_text for word in ['le', 'la', 'faire', 'recette', 'comment']):
            return 'fr'

        # Spanish: specific words
        if any(word in combined_text for word in ['el', 'la', 'hacer', 'receta', 'cómo']):
            return 'es'

        # Default to English
        return 'en'

    def _determine_niche(
        self,
        audio_analysis: Dict,
        visual_analysis: Dict,
        frame_analysis: Dict
    ) -> Dict:
        """
        Determine video niche with confidence

        Priority:
        1. Visual object detection (most reliable)
        2. Audio keywords
        3. OCR text keywords
        4. Default to 'general'

        Returns:
            {
                'niche': str,
                'confidence': float,
                'source': str
            }
        """
        # Priority 1: Visual niche (CLIP detected)
        visual_niche = visual_analysis.get('niche', 'general')
        visual_conf = visual_analysis.get('confidence', 0.0)

        if visual_niche != 'general' and visual_conf > 0.3:
            logger.info(f"👁️ Niche from visuals: {visual_niche} (confidence: {visual_conf:.1%})")
            return {
                'niche': visual_niche,
                'confidence': visual_conf,
                'source': 'visual'
            }

        # Priority 2: Audio keywords
        audio_keywords = audio_analysis.get('keywords', [])
        if audio_keywords:
            audio_niche = self._infer_niche_from_keywords(audio_keywords)
            if audio_niche != 'general':
                logger.info(f"🎙️ Niche from audio: {audio_niche} (estimated confidence: 0.5)")
                return {
                    'niche': audio_niche,
                    'confidence': 0.5,
                    'source': 'audio'
                }

        # Priority 3: OCR keywords
        ocr_keywords = frame_analysis.get('keywords', [])
        if ocr_keywords:
            ocr_niche = self._infer_niche_from_keywords(ocr_keywords)
            if ocr_niche != 'general':
                logger.info(f"📝 Niche from OCR: {ocr_niche} (estimated confidence: 0.4)")
                return {
                    'niche': ocr_niche,
                    'confidence': 0.4,
                    'source': 'text'
                }

        # Default
        logger.info("📂 No specific niche detected, using 'general'")
        return {
            'niche': 'general',
            'confidence': 0.2,
            'source': 'default'
        }

    def _infer_niche_from_keywords(self, keywords: List[str]) -> str:
        """Infer niche from keyword patterns"""
        niche_patterns = {
            'cooking': ['recipe', 'food', 'cook', 'kitchen', 'chef', 'dish', 'meal', 'receita', 'cocina'],
            'gaming': ['game', 'play', 'level', 'win', 'player', 'jogo', 'juego'],
            'tutorial': ['how', 'learn', 'tutorial', 'guide', 'step', 'aprender', 'comment'],
            'review': ['review', 'unbox', 'test', 'product', 'opinion', 'resenha', 'revisión'],
            'vlog': ['vlog', 'day', 'life', 'routine', 'daily', 'vida', 'jour'],
            'fitness': ['workout', 'fitness', 'exercise', 'gym', 'training', 'treino', 'ejercicio'],
            'music': ['music', 'song', 'sing', 'play', 'guitar', 'música', 'musique'],
            'beauty': ['makeup', 'beauty', 'skin', 'hair', 'maquiagem', 'belleza']
        }

        scores = {}
        keywords_lower = [k.lower() for k in keywords]

        for niche, patterns in niche_patterns.items():
            score = sum(1 for pattern in patterns if any(pattern in kw for kw in keywords_lower))
            scores[niche] = score

        if max(scores.values()) > 0:
            return max(scores, key=scores.get)

        return 'general'

    def _extract_content_elements(
        self,
        audio_analysis: Dict,
        visual_analysis: Dict,
        frame_analysis: Dict,
        metadata: Dict,
        niche: str
    ) -> Dict:
        """
        Extract WHO, WHAT, WHERE, TIME elements from all sources

        Returns:
            {
                'who': str,
                'what': str,
                'where': str,
                'time': str,
                'difficulty': str,
                'result': str
            }
        """
        # Extract WHO (subject/person)
        who = self._extract_who(audio_analysis, visual_analysis, frame_analysis, niche)

        # Extract WHAT (action/topic)
        what = self._extract_what(audio_analysis, visual_analysis, frame_analysis, niche)

        # Extract WHERE (location/scene)
        where = visual_analysis.get('scene', 'unknown')

        # Extract TIME (formatted duration)
        time = self._format_duration(metadata.get('duration', 0))

        # Extract DIFFICULTY/SPEED
        difficulty = self._extract_difficulty(audio_analysis, frame_analysis, metadata.get('duration', 0))

        # Extract RESULT
        result = self._extract_result(audio_analysis, frame_analysis)

        return {
            'who': who,
            'what': what,
            'where': where,
            'time': time,
            'difficulty': difficulty,
            'result': result
        }

    def _extract_who(
        self,
        audio: Dict,
        visual: Dict,
        text: Dict,
        niche: str
    ) -> str:
        """Extract WHO element (subject/person)"""
        # Check if person is visible
        if visual.get('has_person', False):
            return "I"  # First person for personal content

        # Check entities from OCR
        entities = text.get('entities', [])
        if entities:
            return entities[0]  # Brand/person name

        # Niche-specific fallbacks
        niche_who = {
            'cooking': 'Chef',
            'gaming': 'Player',
            'tutorial': 'Expert',
            'review': 'Reviewer',
            'vlog': 'Vlogger',
            'fitness': 'Trainer',
            'music': 'Musician',
            'beauty': 'Artist'
        }

        return niche_who.get(niche, 'This')

    def _extract_what(
        self,
        audio: Dict,
        visual: Dict,
        text: Dict,
        niche: str
    ) -> str:
        """Extract WHAT element (action/topic)"""
        # Priority 1: Audio keywords (specific content)
        audio_keywords = audio.get('keywords', [])
        if audio_keywords:
            # Take most frequent keyword
            return audio_keywords[0].title()

        # Priority 2: Visual actions
        actions = visual.get('actions', [])
        if actions:
            return actions[0].title()

        # Priority 3: OCR keywords
        ocr_keywords = text.get('keywords', [])
        if ocr_keywords:
            return ocr_keywords[0].title()

        # Fallback to niche default
        niche_what = {
            'cooking': 'Recipe',
            'gaming': 'Gameplay',
            'tutorial': 'Tutorial',
            'review': 'Review',
            'vlog': 'Vlog',
            'fitness': 'Workout',
            'music': 'Performance',
            'beauty': 'Makeup'
        }

        return niche_what.get(niche, 'Video')

    def _format_duration(self, duration: float) -> str:
        """Format duration to readable string"""
        if duration <= 0:
            return ""

        minutes = int(duration // 60)
        seconds = int(duration % 60)

        if minutes == 0:
            return f"{seconds} Seconds"
        elif minutes < 2:
            return f"{minutes}:{seconds:02d}"
        else:
            return f"{minutes} Minutes"

    def _extract_difficulty(self, audio: Dict, text: Dict, duration: float) -> str:
        """Extract difficulty/speed indicator"""
        # Check keywords
        all_keywords = audio.get('keywords', []) + text.get('keywords', [])

        difficulty_keywords = {
            'fast': 'Fast',
            'quick': 'Quick',
            'easy': 'Easy',
            'hard': 'Hard',
            'difficult': 'Difficult',
            'impossible': 'Impossible'
        }

        for keyword in all_keywords:
            kw_lower = keyword.lower()
            if kw_lower in difficulty_keywords:
                return difficulty_keywords[kw_lower]

        # Auto-detect from duration
        if 0 < duration <= 30:
            return "Fast"
        elif 30 < duration <= 60:
            return "Quick"

        return ""

    def _extract_result(self, audio: Dict, text: Dict) -> str:
        """Extract result/outcome"""
        all_keywords = audio.get('keywords', []) + text.get('keywords', [])

        result_keywords = {
            'success': 'Success',
            'win': 'Win',
            'fail': 'Fail',
            'amazing': 'Amazing',
            'shocking': 'Shocking'
        }

        for keyword in all_keywords:
            kw_lower = keyword.lower()
            if kw_lower in result_keywords:
                return result_keywords[kw_lower]

        return ""

    def _determine_content_type(self, metadata: Dict, elements: Dict) -> str:
        """
        Determine content type for template selection

        Returns: 'speed', 'tutorial', 'viral', 'challenge', etc.
        """
        duration = metadata.get('duration', 0)

        # Speed type for short videos
        if 0 < duration <= 60:
            return 'speed'

        # Tutorial type if no specific result
        if not elements.get('result'):
            return 'tutorial'

        # Viral type if shocking result
        if elements.get('result', '').lower() in ['shocking', 'amazing', 'unbelievable']:
            return 'viral'

        # Challenge type if difficult
        if elements.get('difficulty', '').lower() in ['hard', 'impossible', 'difficult']:
            return 'challenge'

        return 'tutorial'

    def _combine_keywords(self, audio: Dict, frame: Dict) -> List[str]:
        """Combine keywords from all sources"""
        audio_kw = audio.get('keywords', [])
        frame_kw = frame.get('keywords', [])

        # Combine and remove duplicates
        all_kw = audio_kw + frame_kw

        # Remove duplicates while preserving order
        seen = set()
        unique_kw = []
        for kw in all_kw:
            if kw.lower() not in seen:
                seen.add(kw.lower())
                unique_kw.append(kw)

        return unique_kw[:20]  # Top 20

    def _determine_platform(self, metadata: Dict, niche: str) -> str:
        """
        Determine target platform based on video characteristics

        Args:
            metadata: Video metadata
            niche: Video niche

        Returns:
            'facebook' or 'tiktok'
        """
        duration = metadata.get('duration', 0)
        height = metadata.get('height', 0)
        width = metadata.get('width', 0)

        # TikTok: Short, vertical videos
        if duration < 180 and height > width:  # < 3 min, vertical
            return 'tiktok'

        # Facebook: Longer or horizontal videos
        return 'facebook'

    def _log_aggregation_summary(self, aggregated: Dict):
        """Log summary of aggregated content"""
        logger.info("✅ Content aggregation complete:")
        logger.info(f"   🌐 Language: {aggregated['language']} "
                   f"({aggregated['language_source']}, {aggregated['language_confidence']:.1%})")
        logger.info(f"   📂 Niche: {aggregated['niche']} "
                   f"({aggregated['niche_source']}, {aggregated['niche_confidence']:.1%})")
        logger.info(f"   👤 Who: {aggregated['who']}")
        logger.info(f"   🎬 What: {aggregated['what']}")
        logger.info(f"   📍 Where: {aggregated['where']}")
        logger.info(f"   ⏱️ Time: {aggregated['time']}")
        logger.info(f"   🎯 Content Type: {aggregated['content_type']}")
        logger.info(f"   📱 Platform: {aggregated['platform_optimized']}")
        logger.info(f"   🔊 Has Speech: {aggregated['has_speech']}")
        logger.info(f"   📝 Has Text: {aggregated['has_text']}")
        logger.info(f"   👥 Has Person: {aggregated['has_person']}")
