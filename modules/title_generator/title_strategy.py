"""
Advanced Title Generation Strategy
High-CTR, Content-Accurate Title Generation System
Based on 9-Step Workflow
"""

import re
from typing import Dict, List, Optional
from modules.logging.logger import get_logger

logger = get_logger(__name__)


class TitleStrategy:
    """Complete title generation system with content understanding and optimization"""

    # Power words for optimization
    POWER_WORDS = [
        "Unbelievable", "Insane", "Fastest", "Crazy", "Amazing",
        "Incredible", "Shocking", "Epic", "Ultimate", "Perfect"
    ]

    # Emotion/curiosity markers
    EMOTION_MARKERS = ["Just", "...", "!", "😱", "🔥", "💯"]

    # Title types
    TYPE_SPEED = "speed"
    TYPE_SHOCK = "shock"
    TYPE_CHALLENGE = "challenge"
    TYPE_STORY = "story"

    def __init__(self):
        """Initialize title strategy"""
        pass

    # ═══════════════════════════════════════════════════════════════════
    # STEP 1: CONTENT UNDERSTANDING (CORE DATA EXTRACTION)
    # ═══════════════════════════════════════════════════════════════════

    def extract_content_elements(self, frame_analysis: Dict, metadata: Dict) -> Dict:
        """
        Extract 5 core elements from video content using advanced analysis

        Args:
            frame_analysis: Frame analysis with extracted text, keywords, actions, entities
            metadata: Video metadata

        Returns:
            Dict with WHO, WHAT, TIME, DIFFICULTY/SPEED, RESULT
        """
        text_found = frame_analysis.get('text_found', [])
        keywords = frame_analysis.get('keywords', [])
        actions = frame_analysis.get('actions', [])
        entities = frame_analysis.get('entities', [])
        duration = metadata.get('duration', 0)

        elements = {
            'who': self._extract_who(entities, text_found),
            'what': self._extract_what(actions, keywords, text_found),
            'time': self._extract_time(duration),
            'difficulty': self._extract_difficulty(keywords, text_found, duration),
            'result': self._extract_result(keywords, text_found)
        }

        logger.debug(f"Content elements: {elements}")
        return elements

    def _extract_who(self, entities: List[str], text_found: List[str]) -> str:
        """
        Extract WHO from entities (names detected by frame analyzer)

        Args:
            entities: List of detected entities (names, brands)
            text_found: Fallback text list

        Returns:
            WHO string (name or pronoun)
        """
        # Use first entity if available
        if entities:
            return entities[0]

        # Fallback: Look for capitalized words in text
        for text in text_found:
            words = text.split()
            for word in words:
                if word and word[0].isupper() and len(word) > 2:
                    # Skip common words
                    if word.lower() not in ['the', 'this', 'that', 'video', 'part']:
                        return word

        # Default to generic pronoun
        return "This"

    def _extract_what(self, actions: List[str], keywords: List[str], text_found: List[str]) -> str:
        """
        Extract WHAT action using detected actions and keywords

        Args:
            actions: List of action verbs detected
            keywords: List of important keywords
            text_found: Fallback text list

        Returns:
            WHAT action string
        """
        # Use first detected action if available
        if actions:
            return actions[0]

        # Check keywords for action hints
        for keyword in keywords:
            if keyword.lower() in ['tutorial', 'guide', 'review', 'challenge', 'test']:
                return keyword.title()

        # Fallback: Generic action based on common patterns
        return "Amazing Content"

    def _extract_time(self, duration: float) -> str:
        """Extract TIME from duration"""
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

    def _extract_difficulty(self, keywords: List[str], text_found: List[str], duration: float) -> str:
        """
        Extract DIFFICULTY/SPEED indicator using keywords

        Args:
            keywords: Important keywords from video
            text_found: Fallback text list
            duration: Video duration

        Returns:
            Difficulty/speed string
        """
        # Check keywords first (more reliable)
        difficulty_keywords = {
            'fast': 'Fast',
            'quick': 'Quick',
            'speed': 'Speed',
            'hard': 'Hard',
            'difficult': 'Difficult',
            'challenge': 'Challenge',
            'impossible': 'Impossible',
            'easy': 'Easy',
            'extreme': 'Extreme'
        }

        for keyword in keywords:
            keyword_lower = keyword.lower()
            if keyword_lower in difficulty_keywords:
                return difficulty_keywords[keyword_lower]

        # Fallback: Check all text
        for text in text_found:
            text_lower = text.lower()
            for keyword, label in difficulty_keywords.items():
                if keyword in text_lower:
                    return label

        # Auto-detect based on duration
        if duration > 0 and duration <= 30:
            return "Fast"
        elif duration > 0 and duration <= 60:
            return "Quick"

        return ""

    def _extract_result(self, keywords: List[str], text_found: List[str]) -> str:
        """
        Extract RESULT (most important) using keywords

        Args:
            keywords: Important keywords from video
            text_found: Fallback text list

        Returns:
            Result string
        """
        # Look for result indicators in keywords first
        result_keywords = {
            'success': 'Success',
            'win': 'Win',
            'victory': 'Victory',
            'complete': 'Complete',
            'done': 'Done',
            'fail': 'Fail',
            'lose': 'Lost',
            'surprise': 'Surprise',
            'shocking': 'Shocking',
            'unbelievable': 'Unbelievable',
            'amazing': 'Amazing'
        }

        for keyword in keywords:
            keyword_lower = keyword.lower()
            if keyword_lower in result_keywords:
                return result_keywords[keyword_lower]

        # Fallback: Check all text
        for text in text_found:
            text_lower = text.lower()
            for keyword, label in result_keywords.items():
                if keyword in text_lower:
                    return label

        # Default to neutral
        return "Result"

    # ═══════════════════════════════════════════════════════════════════
    # STEP 2: HOOK MOMENT DETECTION
    # ═══════════════════════════════════════════════════════════════════

    def detect_hook(self, elements: Dict) -> str:
        """
        Detect hook type based on content elements

        Args:
            elements: Content elements dict

        Returns:
            Hook type string
        """
        result = elements.get('result', '').lower()
        difficulty = elements.get('difficulty', '').lower()

        # Hook detection rules
        shock_indicators = ['shocking', 'unbelievable', 'surprise', 'amazing']
        challenge_indicators = ['hard', 'difficult', 'impossible', 'extreme', 'challenge']
        success_indicators = ['success', 'win', 'victory', 'complete', 'done']
        fail_indicators = ['fail', 'lost']

        if any(word in result for word in shock_indicators):
            return "shock"
        elif any(word in result for word in fail_indicators):
            return "curiosity"
        elif any(word in difficulty for word in challenge_indicators):
            return "challenge"
        elif any(word in result for word in success_indicators):
            return "achievement"
        else:
            return "moment_of_change"

    # ═══════════════════════════════════════════════════════════════════
    # STEP 3: TITLE TYPE DECISION (RULE-BASED)
    # ═══════════════════════════════════════════════════════════════════

    def select_title_type(self, elements: Dict, hook_type: str) -> str:
        """
        Select title type based on rules

        Rules:
        - IF time <= 30s → SPEED TYPE
        - ELSE IF result shocking → SHOCK TYPE
        - ELSE IF task difficult → CHALLENGE TYPE
        - ELSE → STORY / CURIOSITY TYPE

        Args:
            elements: Content elements
            hook_type: Hook type from detection

        Returns:
            Title type string
        """
        time_str = elements.get('time', '')
        result = elements.get('result', '').lower()
        difficulty = elements.get('difficulty', '').lower()

        # Extract numeric time
        time_seconds = 0
        if 'seconds' in time_str.lower():
            try:
                time_seconds = int(re.search(r'\d+', time_str).group())
            except:
                pass

        # Rule-based selection
        if time_seconds > 0 and time_seconds <= 30:
            return self.TYPE_SPEED
        elif 'shock' in result or 'unbelievable' in result or 'surprise' in result:
            return self.TYPE_SHOCK
        elif difficulty in ['hard', 'difficult', 'impossible', 'extreme', 'challenge']:
            return self.TYPE_CHALLENGE
        else:
            return self.TYPE_STORY

    # ═══════════════════════════════════════════════════════════════════
    # STEP 4: BASE TITLE (BORING BUT CLEAN)
    # ═══════════════════════════════════════════════════════════════════

    def generate_base_title(self, elements: Dict) -> str:
        """
        Generate base title without emotion or emojis
        Format: [WHO] + [WHAT] + [TIME/RESULT]

        Args:
            elements: Content elements

        Returns:
            Base title string
        """
        who = elements.get('who', 'This')
        what = elements.get('what', 'Video')
        time = elements.get('time', '')
        result = elements.get('result', '')

        # Build base title
        if time:
            base = f"{who} {what} in {time}"
        elif result and result != 'Result':
            base = f"{who} {what} {result}"
        else:
            base = f"{who} {what}"

        logger.debug(f"Base title: {base}")
        return base

    # ═══════════════════════════════════════════════════════════════════
    # STEP 5: OPTIMIZATION LAYER (MAKE IT CLICKABLE)
    # ═══════════════════════════════════════════════════════════════════

    def optimize_title(self, base_title: str, title_type: str, elements: Dict) -> List[str]:
        """
        Apply optimization layer to base title

        - Add ONLY ONE power word
        - Add emotion / curiosity
        - Add human angle

        Args:
            base_title: Base title
            title_type: Type of title
            elements: Content elements

        Returns:
            List of optimized title variants
        """
        variants = []
        who = elements.get('who', 'This')
        what = elements.get('what', 'Video')
        time = elements.get('time', '')
        result = elements.get('result', '')

        # Generate variants based on type
        if title_type == self.TYPE_SPEED:
            variants = self._generate_speed_variants(who, what, time, result)
        elif title_type == self.TYPE_SHOCK:
            variants = self._generate_shock_variants(who, what, time, result)
        elif title_type == self.TYPE_CHALLENGE:
            variants = self._generate_challenge_variants(who, what, time, result)
        else:  # STORY
            variants = self._generate_story_variants(who, what, time, result)

        logger.debug(f"Generated {len(variants)} variants")
        return variants

    # ═══════════════════════════════════════════════════════════════════
    # STEP 6: TITLE FORMULAS (TEMPLATES)
    # ═══════════════════════════════════════════════════════════════════

    def _generate_speed_variants(self, who: str, what: str, time: str, result: str) -> List[str]:
        """
        Formula A – Speed: [WHO] + [WHAT] + in + [TIME] + [POWER/EMOTION]
        Professional approach: Minimal emoji usage (only 1 variant with emoji)
        """
        variants = []

        if time:
            # Variant 1: Just + time (NO emoji - clean professional)
            variants.append(f"{who} {what} in Just {time}")

            # Variant 2: Power word at end (NO emoji)
            variants.append(f"{who} {what} in {time}... Insane!")

            # Variant 3: Challenge format (NO emoji)
            variants.append(f"{time} Challenge: {what.title()}")

            # Variant 4: Speed emphasis (NO emoji)
            variants.append(f"Fastest {what} in {time}")

            # Variant 5: ONLY ONE with emoji (if really needed)
            if int(time.split()[0]) <= 15:  # Only for very short times
                variants.append(f"{who} {what} in {time} 🔥")

        return variants

    def _generate_shock_variants(self, who: str, what: str, time: str, result: str) -> List[str]:
        """
        Formula B – Shock: Power word + [WHO] + [WHAT] + [RESULT]
        Professional approach: Minimal emoji usage
        """
        variants = []

        # Variant 1: Unbelievable start (NO emoji)
        variants.append(f"Unbelievable: {who} {what}")

        # Variant 2: You won't believe (NO emoji)
        variants.append(f"You Won't Believe This {what}!")

        # Variant 3: Shocking result (NO emoji)
        variants.append(f"Shocking {what} {result}")

        # Variant 4: Question format (NO emoji)
        variants.append(f"Can {who} {what}? The Answer Will Shock You")

        # Variant 5: Clean power word
        variants.append(f"Incredible {what}: {result}")

        return variants

    def _generate_challenge_variants(self, who: str, what: str, time: str, result: str) -> List[str]:
        """
        Formula C – Challenge: [TIME/DIFFICULTY] Challenge + [RESULT]
        Professional approach: Minimal emoji usage
        """
        variants = []

        # Variant 1: Challenge accepted (NO emoji)
        if time:
            variants.append(f"{time} {what} Challenge: {result}")
        else:
            variants.append(f"{what} Challenge: {result}")

        # Variant 2: Can she/he format (NO emoji)
        pronoun = "She" if who != "This" else "They"
        variants.append(f"Can {pronoun} Complete This {what}?")

        # Variant 3: Ultimate challenge (NO emoji)
        variants.append(f"Ultimate {what} Challenge")

        # Variant 4: Impossible format (NO emoji)
        variants.append(f"Impossible {what}: {result}")

        # Variant 5: Achievement format (NO emoji)
        variants.append(f"{what} Mastery: {result}")

        return variants

    def _generate_story_variants(self, who: str, what: str, time: str, result: str) -> List[str]:
        """
        Formula D – Story: Curiosity + [WHAT] + [RESULT]
        Professional approach: Minimal emoji usage
        """
        variants = []

        # Variant 1: What happened (NO emoji)
        variants.append(f"What Happened When {who} {what}")

        # Variant 2: Amazing result (NO emoji)
        variants.append(f"Amazing {what} {result}")

        # Variant 3: Story format (NO emoji)
        variants.append(f"{who} {what}: The {result} Story")

        # Variant 4: Curiosity hook (NO emoji)
        variants.append(f"This {what} Will Surprise You")

        # Variant 5: Direct format (NO emoji)
        variants.append(f"{who}'s {what}: {result}")

        return variants

    # ═══════════════════════════════════════════════════════════════════
    # STEP 7-9: QUALITY CHECK & FINAL SELECTION
    # ═══════════════════════════════════════════════════════════════════

    def quality_check(self, title: str) -> bool:
        """
        Quality check: Does title make sense WITHOUT watching video?
        Golden Question: "Would I click on this title?"

        Args:
            title: Title to check

        Returns:
            True if passes quality check
        """
        # Basic checks
        if len(title) < 20 or len(title) > 80:
            return False

        # Must contain at least 2 words
        words = title.split()
        if len(words) < 2:
            return False

        # Should not be too generic
        generic_words = ['video', 'content', 'clip', 'footage']
        if any(word.lower() in title.lower() for word in generic_words):
            return False

        # Should have some intrigue (question mark, ellipsis, or power word)
        has_intrigue = (
            '?' in title or
            '...' in title or
            any(word in title for word in self.POWER_WORDS) or
            '!' in title
        )

        return has_intrigue

    def select_best_titles(self, variants: List[str], top_n: int = 3) -> List[str]:
        """
        Select best titles from variants

        Args:
            variants: List of title variants
            top_n: Number of top titles to return

        Returns:
            Top N titles that pass quality check
        """
        # Filter by quality check
        quality_titles = [t for t in variants if self.quality_check(t)]

        # If not enough quality titles, add some variants anyway
        if len(quality_titles) < top_n:
            for variant in variants:
                if variant not in quality_titles:
                    quality_titles.append(variant)
                if len(quality_titles) >= top_n:
                    break

        # Return top N (limited by available titles)
        return quality_titles[:top_n]

    # ═══════════════════════════════════════════════════════════════════
    # MAIN WORKFLOW
    # ═══════════════════════════════════════════════════════════════════

    def generate_titles(self, frame_analysis: Dict, metadata: Dict) -> Dict:
        """
        Complete 9-step title generation workflow

        Args:
            frame_analysis: Frame analysis results
            metadata: Video metadata

        Returns:
            Dict with content elements, base title, and optimized variants
        """
        logger.info("Starting complete title generation workflow...")

        # STEP 1: Content Understanding
        elements = self.extract_content_elements(frame_analysis, metadata)

        # STEP 2: Hook Detection
        hook_type = self.detect_hook(elements)
        logger.debug(f"Hook type: {hook_type}")

        # STEP 3: Title Type Selection
        title_type = self.select_title_type(elements, hook_type)
        logger.debug(f"Title type: {title_type}")

        # STEP 4: Base Title Generation
        base_title = self.generate_base_title(elements)

        # STEP 5-6: Optimization & Formula Application
        all_variants = self.optimize_title(base_title, title_type, elements)

        # STEP 7-9: Quality Check & Selection
        optimized_titles = self.select_best_titles(all_variants, top_n=5)

        result = {
            'who': elements['who'],
            'what': elements['what'],
            'time': elements['time'],
            'difficulty': elements['difficulty'],
            'result': elements['result'],
            'hook_type': hook_type,
            'title_type': title_type,
            'base_title': base_title,
            'optimized_titles': optimized_titles
        }

        logger.info(f"Generated {len(optimized_titles)} optimized titles")
        return result
