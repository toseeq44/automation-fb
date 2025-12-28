"""
Enhanced Multilingual Title Generator
Complete content-aware title generation with audio, visual, and text analysis
Supports multiple languages with platform-specific optimization
"""

import re
from typing import Dict, Optional, List
from modules.logging.logger import get_logger

# Import all analyzers
from .api_manager import APIKeyManager
from .audio_analyzer import AudioAnalyzer
from .visual_analyzer import VisualAnalyzer
from .frame_analyzer import FrameAnalyzer
from .content_aggregator import ContentAggregator
from .multilingual_templates import MultilingualTemplates

logger = get_logger(__name__)


class EnhancedTitleGenerator:
    """
    Complete multilingual title generator with comprehensive content analysis

    Features:
    - Audio transcription and language detection (Whisper)
    - Visual object and scene detection (CLIP)
    - OCR text extraction (Tesseract)
    - Content aggregation and understanding
    - Multilingual title generation
    - Platform-specific optimization (Facebook/TikTok)
    - AI refinement (Groq API)
    """

    def __init__(self, model_size: str = 'base'):
        """
        Initialize enhanced title generator

        Args:
            model_size: Whisper model size ('tiny', 'base', 'small', 'medium')
                       'base' recommended for balance of speed and accuracy
        """
        logger.info("🚀 Initializing Enhanced Title Generator...")

        # Initialize all components
        self.api_manager = APIKeyManager()
        self.audio_analyzer = AudioAnalyzer(model_size=model_size)
        self.visual_analyzer = VisualAnalyzer()
        self.frame_analyzer = FrameAnalyzer()
        self.content_aggregator = ContentAggregator()
        self.templates = MultilingualTemplates()

        # Initialize Groq AI
        self.groq_client = None
        self._init_groq()

        logger.info("✅ Enhanced Title Generator initialized successfully")

    def _init_groq(self):
        """Initialize Groq API client"""
        try:
            from groq import Groq

            api_key = self.api_manager.get_api_key()
            if api_key:
                self.groq_client = Groq(api_key=api_key)
                logger.info("✅ Groq API initialized")
            else:
                logger.warning("⚠️ No Groq API key found (AI refinement disabled)")

        except ImportError:
            logger.warning("⚠️ Groq library not installed. Run: pip install groq")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Groq: {e}")

    def generate_title(
        self,
        video_info: Dict,
        platform: str = 'facebook',
        enable_ai: bool = True
    ) -> str:
        """
        Generate content-aware multilingual title

        Args:
            video_info: Video metadata with 'path', 'filename', etc.
            platform: Target platform ('facebook', 'tiktok', 'instagram')
            enable_ai: Use AI refinement if available

        Returns:
            Final title string in detected language
        """
        video_path = video_info['path']
        logger.info("=" * 60)
        logger.info(f"🎬 Generating title for: {video_info['filename']}")
        logger.info("=" * 60)

        try:
            # PHASE 1: MULTI-SOURCE CONTENT ANALYSIS
            logger.info("\n📊 PHASE 1: Content Analysis")
            logger.info("-" * 60)

            # 1.1 Audio Analysis (Language + Transcription)
            audio_analysis = self.audio_analyzer.analyze_audio(video_path)

            # 1.2 Visual Analysis (Objects + Scene + Niche)
            visual_analysis = self.visual_analyzer.analyze_video_visual(video_path)

            # 1.3 Text Analysis (OCR from frames)
            frame_analysis = self.frame_analyzer.analyze_video(video_path)

            # 1.4 Video Metadata
            metadata = self.frame_analyzer.get_video_metadata(video_path)

            # PHASE 2: CONTENT AGGREGATION
            logger.info("\n🔄 PHASE 2: Content Aggregation")
            logger.info("-" * 60)

            aggregated = self.content_aggregator.aggregate_content(
                audio_analysis,
                visual_analysis,
                frame_analysis,
                metadata
            )

            # PHASE 3: TITLE GENERATION
            logger.info("\n✍️ PHASE 3: Title Generation")
            logger.info("-" * 60)

            language = aggregated['language']
            niche = aggregated['niche']
            content_type = aggregated['content_type']

            # Get language-specific templates
            templates = self.templates.get_templates(
                language=language,
                niche=niche,
                template_type=content_type,
                platform=platform
            )

            if not templates:
                logger.warning("No templates found, using fallback")
                return self._fallback_title(video_info, language)

            # Fill templates with content
            filled_titles = self._fill_templates(templates, aggregated)

            logger.info(f"📝 Generated {len(filled_titles)} title variants:")
            for i, title in enumerate(filled_titles, 1):
                logger.info(f"   {i}. {title}")

            # PHASE 4: AI REFINEMENT (if enabled and available)
            if enable_ai and self.groq_client:
                logger.info("\n🤖 PHASE 4: AI Refinement")
                logger.info("-" * 60)

                best_title = self._ai_select_best_title(
                    filled_titles,
                    aggregated,
                    language,
                    platform
                )
            else:
                # No AI: Use first variant
                best_title = filled_titles[0] if filled_titles else ""
                logger.info("📌 Selected first variant (no AI)")

            # PHASE 5: FINAL CLEANUP
            final_title = self._clean_title(best_title, platform)

            logger.info("\n" + "=" * 60)
            logger.info(f"✨ FINAL TITLE: {final_title}")
            logger.info(f"🌐 Language: {aggregated['language']} ({aggregated['language_name']})")
            logger.info(f"📂 Niche: {niche}")
            logger.info(f"📱 Platform: {platform}")
            logger.info("=" * 60 + "\n")

            return final_title

        except Exception as e:
            logger.error(f"❌ Title generation failed: {e}", exc_info=True)
            return self._fallback_title(video_info, 'en')

    def _fill_templates(self, templates: List[str], aggregated: Dict) -> List[str]:
        """
        Fill template placeholders with actual content

        Placeholders:
        - {WHO}: Subject/person
        - {WHAT}: Action/topic
        - {TIME}: Duration
        - {FOOD}: Food item (cooking niche)
        - {GAME}: Game name (gaming niche)
        - {PRODUCT}: Product name (review niche)
        - {TOPIC}: General topic
        - {ACTION}: Action verb
        - {PLACE}: Location
        - {RESULT}: Outcome
        - {EXERCISE}: Exercise type (fitness niche)

        Args:
            templates: List of template strings
            aggregated: Aggregated content data

        Returns:
            List of filled title strings
        """
        filled = []

        # Extract content elements
        who = aggregated.get('who', 'I')
        what = aggregated.get('what', 'Video')
        time = aggregated.get('time', '')
        result = aggregated.get('result', '')
        difficulty = aggregated.get('difficulty', '')

        # Niche-specific extractions
        niche = aggregated.get('niche', 'general')
        keywords = aggregated.get('keywords', [])
        objects = aggregated.get('objects', [])

        # Extract niche-specific terms
        food = self._extract_food_term(keywords, objects) if niche == 'cooking' else 'Food'
        game = self._extract_game_term(keywords, objects) if niche == 'gaming' else 'Game'
        product = self._extract_product_term(keywords, objects) if niche == 'review' else 'Product'
        exercise = self._extract_exercise_term(keywords, objects) if niche == 'fitness' else 'Workout'

        # Get action verbs
        actions = aggregated.get('actions', [])
        action = actions[0] if actions else 'make'

        # Fill each template
        for template in templates:
            try:
                title = template.format(
                    WHO=who,
                    WHAT=what,
                    TIME=time,
                    RESULT=result,
                    DIFFICULTY=difficulty,
                    FOOD=food,
                    GAME=game,
                    PRODUCT=product,
                    TOPIC=what,
                    ACTION=action,
                    PLACE=aggregated.get('where', 'here'),
                    EXERCISE=exercise,
                    NUMBER='1'  # For series
                )

                # Remove empty sections (e.g., " in " if no TIME)
                title = self._cleanup_empty_sections(title)

                filled.append(title)

            except KeyError as e:
                logger.debug(f"Template missing key {e}: {template}")
                continue

        return filled

    def _extract_food_term(self, keywords: List[str], objects: List[str]) -> str:
        """Extract food item from keywords/objects"""
        food_terms = ['pizza', 'burger', 'pasta', 'cake', 'bread', 'chicken',
                      'rice', 'noodles', 'salad', 'soup', 'curry', 'biryani']

        # Check keywords first
        for kw in keywords:
            kw_lower = kw.lower()
            if kw_lower in food_terms:
                return kw.title()

        # Check objects
        for obj in objects:
            if obj in food_terms:
                return obj.title()

        return 'Food'

    def _extract_game_term(self, keywords: List[str], objects: List[str]) -> str:
        """Extract game name from keywords"""
        # Common games
        games = ['fortnite', 'minecraft', 'cod', 'valorant', 'pubg', 'fifa',
                 'gta', 'roblox', 'apex', 'warzone']

        for kw in keywords:
            kw_lower = kw.lower()
            if kw_lower in games:
                return kw.title()

        return 'Game'

    def _extract_product_term(self, keywords: List[str], objects: List[str]) -> str:
        """Extract product name from keywords"""
        # Check for brand names (capitalized)
        for kw in keywords:
            if kw and kw[0].isupper() and len(kw) > 3:
                return kw

        # Check objects
        if objects and 'phone' in objects:
            return 'Phone'
        if objects and 'laptop' in objects:
            return 'Laptop'

        return 'Product'

    def _extract_exercise_term(self, keywords: List[str], objects: List[str]) -> str:
        """Extract exercise type from keywords"""
        exercises = ['yoga', 'cardio', 'weights', 'hiit', 'running', 'abs',
                     'legs', 'arms', 'core', 'pilates']

        for kw in keywords:
            kw_lower = kw.lower()
            if kw_lower in exercises:
                return kw.title()

        return 'Workout'

    def _cleanup_empty_sections(self, title: str) -> str:
        """Remove empty template sections"""
        # Remove patterns like " in  |", " -  ", etc.
        title = re.sub(r'\s+in\s+\|', ' |', title)
        title = re.sub(r'\s+in\s+$', '', title)
        title = re.sub(r'\|\s+$', '', title)
        title = re.sub(r'\s+-\s+$', '', title)
        title = re.sub(r'\s+\|\s+', ' | ', title)
        title = re.sub(r'\s{2,}', ' ', title)  # Multiple spaces

        return title.strip()

    def _ai_select_best_title(
        self,
        variants: List[str],
        aggregated: Dict,
        language: str,
        platform: str
    ) -> str:
        """
        Use Groq AI to select/refine the best title

        Args:
            variants: List of title variants
            aggregated: Aggregated content data
            language: Target language
            platform: Target platform

        Returns:
            Best title selected/refined by AI
        """
        try:
            # Build comprehensive AI prompt
            language_name = aggregated.get('language_name', language.upper())
            niche = aggregated.get('niche', 'general')
            platform_limit = self.templates.get_platform_limit(platform)

            # Get content context
            transcription = aggregated.get('transcription', '')[:200]  # First 200 chars
            objects = ', '.join(aggregated.get('objects', [])[:10])
            keywords = ', '.join(aggregated.get('keywords', [])[:15])

            prompt = f"""You are an expert in creating viral {platform.upper()} titles in {language_name}.

VIDEO CONTENT ANALYSIS:
- Language: {language_name}
- Niche: {niche}
- Platform: {platform.upper()}

Audio Transcription:
{transcription if transcription else "No speech detected"}

Visual Objects Detected:
{objects if objects else "No objects detected"}

Keywords:
{keywords if keywords else "No keywords extracted"}

Has Person: {aggregated.get('has_person', False)}
Duration: {aggregated.get('time', 'Unknown')}
Scene: {aggregated.get('where', 'Unknown')}

TITLE VARIANTS:
{chr(10).join(f"{i+1}. {title}" for i, title in enumerate(variants))}

YOUR TASK:
1. Analyze the video content (what's ACTUALLY happening in the video)
2. Select the BEST variant OR create a better content-accurate title
3. The title MUST be in {language_name} language ONLY
4. Make it engaging, clickable, and SEO-friendly for {platform.upper()}
5. Character limit: {platform_limit} characters (STRICT)
6. Must reflect ACTUAL video content
7. NO generic words like "video", "content", "clip"
8. Use power words appropriate for {language_name}
9. NO invalid filename characters (/ \\ : * ? " < > |)
10. Return ONLY the final title in {language_name}, nothing else

EXAMPLES OF GREAT {platform.upper()} TITLES:
- Specific and content-accurate
- Engaging and clickable
- Natural in {language_name}
- Platform-optimized

Return the BEST title:"""

            logger.info("🤖 Sending to Groq AI for refinement...")

            # Call Groq API
            response = self.groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=150,
                timeout=30
            )

            ai_title = response.choices[0].message.content.strip()

            # Remove quotes if AI added them
            ai_title = ai_title.strip('"\'')

            logger.info(f"✅ AI selected: {ai_title}")

            return ai_title

        except Exception as e:
            logger.error(f"❌ AI selection failed: {e}")
            # Fallback to first variant
            return variants[0] if variants else ""

    def _clean_title(self, title: str, platform: str = 'facebook') -> str:
        """
        Clean and sanitize title for filename and platform

        Args:
            title: Raw title string
            platform: Target platform

        Returns:
            Cleaned title string
        """
        # Remove quotes
        title = title.strip('"\'')

        # Remove invalid filename characters
        invalid_chars = r'[<>:"/\\|?*]'
        title = re.sub(invalid_chars, '', title)

        # Replace multiple spaces
        title = re.sub(r'\s+', ' ', title)

        # Get platform limit
        max_length = self.templates.get_platform_limit(platform)

        # Truncate if too long
        if len(title) > max_length:
            title = title[:max_length - 3] + '...'

        # Ensure minimum length
        if len(title) < 10:
            title = title + " Video"

        return title.strip()

    def _fallback_title(self, video_info: Dict, language: str = 'en') -> str:
        """
        Fallback: Extract decent title from filename

        Args:
            video_info: Video metadata
            language: Target language

        Returns:
            Title extracted from filename
        """
        filename = video_info.get('filename', 'Video')

        # Remove extension
        name = filename.rsplit('.', 1)[0]

        # Replace separators
        name = name.replace('_', ' ').replace('-', ' ').replace('.', ' ')

        # Remove version numbers
        name = re.sub(r'_?(v\d+|final|edit|new|old|\d+)$', '', name, flags=re.IGNORECASE)

        # Title case
        name = name.title()

        # Clean
        name = self._clean_title(name)

        logger.info(f"⚠️ Using fallback title: {name}")

        return name
