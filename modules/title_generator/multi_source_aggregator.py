"""
Multi-Source Aggregator
Intelligently combines data from ALL sources for maximum accuracy
"""

from typing import Dict, List, Optional
from modules.logging.logger import get_logger

logger = get_logger(__name__)


class MultiSourceAggregator:
    """
    Combine data from multiple sources with intelligent voting
    Sources: API, Local Models, OCR, Audio, Heuristics
    """

    def __init__(self):
        """Initialize aggregator"""
        pass

    def aggregate_analysis(
        self,
        api_result: Optional[Dict] = None,
        local_result: Optional[Dict] = None,
        ocr_texts: Optional[List[str]] = None,
        audio_result: Optional[Dict] = None,
        heuristic_result: Optional[Dict] = None,
        filename: str = ""
    ) -> Dict:
        """
        Aggregate all analysis sources with intelligent voting

        Args:
            api_result: Result from cloud API (Groq/OpenAI)
            local_result: Result from local models (YOLO/BLIP)
            ocr_texts: OCR extracted text
            audio_result: Audio transcription result
            heuristic_result: Heuristic analysis
            filename: Video filename

        Returns:
            Aggregated result with highest confidence
        """
        logger.info("🧠 Aggregating multi-source analysis...")

        # Track all votes for each field
        niche_votes = {}
        language_votes = {}
        objects_combined = []
        actions_combined = []
        descriptions = []

        # ========================================
        # NICHE DETECTION (Weighted Voting)
        # ========================================

        # API vote (highest weight - 1.0)
        if api_result and api_result.get('niche'):
            niche = api_result['niche']
            confidence = api_result.get('niche_confidence', 0.7)
            niche_votes[niche] = niche_votes.get(niche, 0) + (1.0 * confidence)
            logger.info(f"   📡 API vote: {niche} (weight: {1.0 * confidence:.2f})")

        # Local model vote (high weight - 0.9)
        if local_result and local_result.get('niche'):
            niche = local_result['niche']
            confidence = local_result.get('niche_confidence', 0.7)
            niche_votes[niche] = niche_votes.get(niche, 0) + (0.9 * confidence)
            logger.info(f"   🔍 Local model vote: {niche} (weight: {0.9 * confidence:.2f})")

        # OCR text vote (medium weight - 0.6)
        if ocr_texts:
            niche = self._infer_niche_from_text(' '.join(ocr_texts))
            if niche != 'general':
                niche_votes[niche] = niche_votes.get(niche, 0) + 0.6
                logger.info(f"   📝 OCR vote: {niche} (weight: 0.60)")

        # Audio keywords vote (high weight - 0.8)
        if audio_result and audio_result.get('keywords'):
            niche = self._infer_niche_from_keywords(audio_result['keywords'])
            if niche != 'general':
                niche_votes[niche] = niche_votes.get(niche, 0) + 0.8
                logger.info(f"   🎙️  Audio vote: {niche} (weight: 0.80)")

        # Filename vote (low weight - 0.4)
        if filename:
            niche = self._infer_niche_from_filename(filename)
            if niche != 'general':
                niche_votes[niche] = niche_votes.get(niche, 0) + 0.4
                logger.info(f"   📄 Filename vote: {niche} (weight: 0.40)")

        # Heuristic vote (fallback - 0.3)
        if heuristic_result and heuristic_result.get('niche'):
            niche = heuristic_result['niche']
            confidence = heuristic_result.get('niche_confidence', 0.5)
            niche_votes[niche] = niche_votes.get(niche, 0) + (0.3 * confidence)
            logger.info(f"   🔄 Heuristic vote: {niche} (weight: {0.3 * confidence:.2f})")

        # Select best niche
        if niche_votes:
            best_niche = max(niche_votes, key=niche_votes.get)
            best_niche_score = niche_votes[best_niche]
            # Normalize confidence (max possible score is ~3.0)
            niche_confidence = min(best_niche_score / 3.0, 1.0)
        else:
            best_niche = 'general'
            niche_confidence = 0.3

        logger.info(f"   ✅ FINAL NICHE: {best_niche} (confidence: {niche_confidence:.0%})")
        logger.info(f"   📊 All votes: {niche_votes}")

        # ========================================
        # LANGUAGE DETECTION (Priority Order)
        # ========================================

        best_language = 'en'
        best_language_name = 'English'
        language_confidence = 0.5

        # Priority 1: Audio (95% accurate)
        if audio_result and not audio_result.get('is_music', False):
            best_language = audio_result.get('language', 'en')
            best_language_name = audio_result.get('language_name', 'English')
            language_confidence = 0.95
            logger.info(f"   🎙️  Language from audio: {best_language_name} (95%)")

        # Priority 2: OCR (70% accurate)
        elif ocr_texts:
            lang_result = self._detect_language_from_text(ocr_texts)
            best_language = lang_result['language']
            best_language_name = lang_result['language_name']
            language_confidence = 0.7
            logger.info(f"   📝 Language from OCR: {best_language_name} (70%)")

        # Priority 3: Filename (50% accurate)
        elif filename:
            lang_result = self._detect_language_from_filename(filename)
            best_language = lang_result['language']
            best_language_name = lang_result['language_name']
            language_confidence = 0.5
            logger.info(f"   📄 Language from filename: {best_language_name} (50%)")

        # ========================================
        # OBJECTS & ACTIONS (Combine All)
        # ========================================

        # Combine objects from all sources
        if api_result and api_result.get('detected_objects'):
            objects_combined.extend(api_result['detected_objects'])

        if local_result and local_result.get('detected_objects'):
            objects_combined.extend(local_result['detected_objects'])

        # Deduplicate, keep top 10
        objects_combined = list(dict.fromkeys(objects_combined))[:10]

        # Combine actions
        if api_result and api_result.get('detected_actions'):
            actions_combined.extend(api_result['detected_actions'])

        if local_result and local_result.get('detected_actions'):
            actions_combined.extend(local_result['detected_actions'])

        # Deduplicate
        actions_combined = list(dict.fromkeys(actions_combined))[:5]

        # ========================================
        # CONTENT DESCRIPTION (Best Available)
        # ========================================

        best_description = ""

        # Priority 1: API description
        if api_result and api_result.get('content_description'):
            best_description = api_result['content_description']

        # Priority 2: Local model description
        elif local_result and local_result.get('content_description'):
            best_description = local_result['content_description']

        # Priority 3: Build from objects
        elif objects_combined:
            best_description = f"Content showing {', '.join(objects_combined[:3])}"

        # Priority 4: Heuristic
        elif heuristic_result and heuristic_result.get('content_description'):
            best_description = heuristic_result['content_description']

        # ========================================
        # HAS PERSON (Any source says yes)
        # ========================================

        has_person = False
        if api_result and api_result.get('has_person'):
            has_person = True
        if local_result and local_result.get('has_person'):
            has_person = True
        if 'person' in objects_combined:
            has_person = True

        # ========================================
        # SCENE TYPE (First available)
        # ========================================

        scene_type = 'unknown'
        if api_result and api_result.get('scene_type'):
            scene_type = api_result['scene_type']
        elif local_result and local_result.get('scene_type'):
            scene_type = local_result['scene_type']

        # ========================================
        # KEYWORDS (Combine unique)
        # ========================================

        keywords = []
        if audio_result and audio_result.get('keywords'):
            keywords.extend(audio_result['keywords'])
        if ocr_texts:
            keywords.extend(ocr_texts[:5])

        keywords = list(dict.fromkeys(keywords))[:15]

        # ========================================
        # RETURN AGGREGATED RESULT
        # ========================================

        result = {
            'language': best_language,
            'language_name': best_language_name,
            'language_confidence': language_confidence,
            'niche': best_niche,
            'niche_confidence': niche_confidence,
            'content_description': best_description,
            'detected_objects': objects_combined,
            'detected_actions': actions_combined,
            'keywords': keywords,
            'has_person': has_person,
            'scene_type': scene_type,
            '_source_votes': niche_votes  # Debug info
        }

        logger.info("✅ Multi-source aggregation complete!")
        return result

    def _infer_niche_from_text(self, text: str) -> str:
        """Infer niche from text"""
        text_lower = text.lower()

        niche_keywords = {
            'cooking': ['cook', 'recipe', 'food', 'kitchen', 'chef', 'bake', 'fry', 'taste',
                       'pasta', 'pizza', 'burger', 'cake', 'chicken', 'delicious', 'dish', 'meal'],
            'gaming': ['game', 'gaming', 'play', 'player', 'level', 'win', 'score', 'gamer',
                      'controller', 'console', 'mobile', 'pubg', 'fortnite', 'minecraft'],
            'tutorial': ['tutorial', 'how to', 'guide', 'learn', 'teach', 'step', 'lesson',
                        'tips', 'tricks', 'hacks', 'diy', 'easy', 'simple'],
            'review': ['review', 'unbox', 'unboxing', 'test', 'testing', 'vs', 'comparison',
                      'honest', 'opinion', 'pros', 'cons'],
            'fitness': ['workout', 'fitness', 'exercise', 'gym', 'yoga', 'cardio', 'abs',
                       'training', 'muscle', 'weight', 'strength'],
            'music': ['music', 'song', 'beat', 'cover', 'sing', 'singing', 'guitar',
                     'piano', 'drum', 'rap', 'dance'],
            'vlog': ['vlog', 'day in', 'life', 'daily', 'routine', 'morning', 'night',
                    'lifestyle', 'behind', 'scenes'],
            'entertainment': ['funny', 'comedy', 'prank', 'meme', 'joke', 'laugh', 'fun',
                             'entertainment', 'react', 'reaction'],
            'beauty': ['makeup', 'beauty', 'skincare', 'cosmetic', 'lipstick', 'foundation']
        }

        for niche, keywords in niche_keywords.items():
            matches = sum(1 for kw in keywords if kw in text_lower)
            if matches >= 1:  # Even 1 match
                return niche

        return 'general'

    def _infer_niche_from_keywords(self, keywords: List[str]) -> str:
        """Infer niche from audio keywords"""
        combined = ' '.join(keywords).lower()
        return self._infer_niche_from_text(combined)

    def _infer_niche_from_filename(self, filename: str) -> str:
        """Infer niche from filename"""
        import re

        # Clean filename
        clean_name = re.sub(r'\.[a-zA-Z0-9]+$', '', filename)
        clean_name = re.sub(r'[_\-\.]', ' ', clean_name)

        return self._infer_niche_from_text(clean_name)

    def _detect_language_from_text(self, texts: List[str]) -> Dict:
        """Detect language from text"""
        import re

        if not texts:
            return {'language': 'en', 'language_name': 'English'}

        combined = ' '.join(texts).lower()

        # Unicode patterns
        patterns = {
            'ur': r'[\u0600-\u06FF]',  # Urdu/Arabic
            'hi': r'[\u0900-\u097F]',  # Hindi
            'ar': r'[\u0600-\u06FF]',  # Arabic
            'zh': r'[\u4E00-\u9FFF]',  # Chinese
        }

        for lang, pattern in patterns.items():
            if re.search(pattern, combined):
                names = {'ur': 'Urdu', 'hi': 'Hindi', 'ar': 'Arabic', 'zh': 'Chinese'}
                return {'language': lang, 'language_name': names[lang]}

        return {'language': 'en', 'language_name': 'English'}

    def _detect_language_from_filename(self, filename: str) -> Dict:
        """Detect language from filename"""
        filename_lower = filename.lower()

        # Language indicators in filename
        lang_indicators = {
            'pt': ['portuguese', 'portugues', 'brasil', 'pt'],
            'es': ['spanish', 'espanol', 'español', 'es'],
            'fr': ['french', 'francais', 'français', 'fr'],
            'ur': ['urdu', 'ur'],
            'hi': ['hindi', 'hi'],
            'ar': ['arabic', 'ar']
        }

        for lang, indicators in lang_indicators.items():
            if any(ind in filename_lower for ind in indicators):
                names = {
                    'pt': 'Portuguese', 'es': 'Spanish', 'fr': 'French',
                    'ur': 'Urdu', 'hi': 'Hindi', 'ar': 'Arabic'
                }
                return {'language': lang, 'language_name': names[lang]}

        return {'language': 'en', 'language_name': 'English'}
