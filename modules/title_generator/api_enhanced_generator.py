"""
API-Enhanced Title Generator (No PyTorch Required!)
Works with Python 3.14, no DLL dependencies
Uses Groq API + lightweight tools for content-aware titles
"""

from typing import Dict, List
from pathlib import Path
from modules.logging.logger import get_logger
from .api_content_analyzer import APIContentAnalyzer
from .multilingual_templates import MultilingualTemplates
import re

logger = get_logger(__name__)


class APIEnhancedTitleGenerator:
    """
    Enhanced title generator using API-based analysis
    NO PyTorch, Whisper, or Transformers needed!

    Works with ANY Python version (including 3.14+)
    No DLL dependencies
    Small installation footprint
    """

    def __init__(self, groq_client=None):
        """
        Initialize API-enhanced generator

        Args:
            groq_client: Groq API client (optional but recommended)
        """
        self.groq_client = groq_client
        self.analyzer = APIContentAnalyzer(groq_client)
        self.templates = MultilingualTemplates()

        logger.info("✨ API-Enhanced Title Generator initialized")
        logger.info("   Using: Groq API + Lightweight OCR")
        logger.info("   No PyTorch/Whisper/Transformers needed!")

    def generate_title(
        self,
        video_info: Dict,
        platform: str = 'facebook',
        enable_ai: bool = True
    ) -> str:
        """
        Generate content-aware, multilingual title using API approach

        Args:
            video_info: Dict with video metadata
            platform: Target platform (facebook/tiktok/instagram/youtube)
            enable_ai: Use Groq AI for refinement

        Returns:
            Generated title string
        """
        try:
            video_path = video_info.get('path', '')
            filename = video_info.get('filename', '')

            logger.info("=" * 60)
            logger.info(f"🎬 Generating API-enhanced title: {filename}")
            logger.info("=" * 60)

            # PHASE 1: CONTENT ANALYSIS
            logger.info("\n📊 PHASE 1: API-Based Content Analysis")
            logger.info("-" * 60)

            analysis = self.analyzer.analyze_video_content(
                video_path,
                video_info
            )

            logger.info(f"   🌐 Language: {analysis['language_name']} ({analysis['language_confidence']:.0%})")
            logger.info(f"   📂 Niche: {analysis['niche']}")
            if analysis['detected_objects']:
                logger.info(f"   👁️ Objects: {', '.join(analysis['detected_objects'][:5])}")
            if analysis['ocr_text']:
                logger.info(f"   📝 OCR text: {len(analysis['ocr_text'])} items found")

            # PHASE 2: EXTRACT CONTENT ELEMENTS
            logger.info("\n🔄 PHASE 2: Content Element Extraction")
            logger.info("-" * 60)

            elements = self._extract_content_elements(analysis, video_info)
            logger.info(f"   👤 Who: {elements['who']}")
            logger.info(f"   🎬 What: {elements['what']}")
            logger.info(f"   ⏱️ Duration: {elements['time']}")

            # PHASE 3: TEMPLATE SELECTION
            logger.info("\n✍️ PHASE 3: Template-Based Title Generation")
            logger.info("-" * 60)

            language = analysis['language']
            niche = analysis['niche']
            content_type = self._determine_content_type(video_info, elements)

            templates = self.templates.get_templates(
                language=language,
                niche=niche,
                template_type=content_type,
                platform=platform
            )

            if not templates:
                logger.warning("No templates found, using fallback")
                return self._fallback_title(video_info, language)

            # Fill templates
            filled_titles = self._fill_templates(templates, elements, analysis)
            logger.info(f"📝 Generated {len(filled_titles)} title variants:")
            for i, title in enumerate(filled_titles[:5], 1):
                logger.info(f"   {i}. {title}")

            # PHASE 4: AI REFINEMENT
            best_title = filled_titles[0] if filled_titles else ""

            if enable_ai and self.groq_client:
                logger.info("\n🤖 PHASE 4: AI Refinement via Groq")
                logger.info("-" * 60)

                refined_title = self._ai_refine_title(
                    filled_titles,
                    analysis,
                    platform
                )

                if refined_title:
                    best_title = refined_title
                    logger.info(f"✅ AI selected: {best_title}")
                else:
                    logger.info(f"📌 Using template: {best_title}")
            else:
                logger.info("\n📌 Using best template (AI disabled)")

            # PHASE 5: CLEANUP
            final_title = self._clean_title(best_title, platform)

            logger.info("\n" + "=" * 60)
            logger.info(f"✨ FINAL TITLE: {final_title}")
            logger.info(f"🌐 Language: {language} ({analysis['language_name']})")
            logger.info(f"📂 Niche: {niche}")
            logger.info(f"📱 Platform: {platform}")
            logger.info("=" * 60 + "\n")

            return final_title

        except Exception as e:
            logger.error(f"❌ Title generation failed: {e}", exc_info=True)
            return self._fallback_title(video_info, 'en')

    def _extract_content_elements(self, analysis: Dict, video_info: Dict) -> Dict:
        """Extract content elements from analysis"""
        # Get duration
        duration = video_info.get('duration', 0)
        if duration > 0:
            if duration < 60:
                time_str = f"{int(duration)} Seconds"
            else:
                minutes = int(duration // 60)
                seconds = int(duration % 60)
                if seconds > 0:
                    time_str = f"{minutes}:{seconds:02d}"
                else:
                    time_str = f"{minutes} Minutes"
        else:
            time_str = ""

        # Extract WHO from OCR text or filename
        who = "I"
        ocr_text = ' '.join(analysis.get('ocr_text', []))
        if ocr_text:
            # Try to find a name/entity
            words = ocr_text.split()
            capitalized = [w for w in words if w and w[0].isupper() and len(w) > 2]
            if capitalized:
                who = capitalized[0]

        # Extract WHAT from content description, objects, or filename
        what = analysis.get('content_description', '')

        if not what and analysis.get('detected_objects'):
            what = analysis['detected_objects'][0]

        # Last resort: extract from filename (NO more "Amazing Content"!)
        if not what:
            import re
            filename = video_info.get('filename', '')

            # Clean filename: remove extension, special chars
            clean_name = re.sub(r'\.[a-zA-Z0-9]+$', '', filename)
            clean_name = re.sub(r'[_\-\.]', ' ', clean_name)

            # Remove generic terms
            generic_terms = {
                'amazing', 'content', 'video', 'clip', 'new', 'latest', 'best',
                'story', 'see', 'watch', 'check', 'viral', 'trending', 'secs', 'seconds',
                'in', 'the', 'a', 'an', 'and', 'or', 'of', 'to', 'for'
            }

            words = clean_name.split()
            meaningful = [w for w in words if w.lower() not in generic_terms and len(w) > 2]

            if meaningful:
                # Use first 2-3 meaningful words
                what = ' '.join(meaningful[:3])
            else:
                # Absolute last resort
                what = "This Video"

        # Extract FOOD/GAME/PRODUCT specific
        objects = analysis.get('detected_objects', [])
        food = self._find_food_term(objects + analysis.get('ocr_text', []))
        game = self._find_game_term(objects + analysis.get('ocr_text', []))
        product = self._find_product_term(objects + analysis.get('ocr_text', []))

        return {
            'who': who,
            'what': what,
            'time': time_str,
            'food': food,
            'game': game,
            'product': product,
            'difficulty': '',
            'result': ''
        }

    def _find_food_term(self, texts: List[str]) -> str:
        """Find food-related term"""
        food_terms = ['pizza', 'burger', 'pasta', 'cake', 'bread', 'chicken',
                      'rice', 'noodles', 'salad', 'soup', 'curry', 'biryani',
                      'sandwich', 'dessert', 'coffee', 'tea']

        combined = ' '.join(texts).lower()
        for term in food_terms:
            if term in combined:
                return term.title()

        return 'Food'

    def _find_game_term(self, texts: List[str]) -> str:
        """Find game-related term"""
        games = ['fortnite', 'minecraft', 'cod', 'valorant', 'pubg', 'fifa',
                 'gta', 'roblox', 'apex', 'warzone', 'call of duty']

        combined = ' '.join(texts).lower()
        for game in games:
            if game in combined:
                return game.title()

        return 'Game'

    def _find_product_term(self, texts: List[str]) -> str:
        """Find product-related term"""
        for text in texts:
            if text and len(text) > 3 and text[0].isupper():
                return text

        return 'Product'

    def _determine_content_type(self, metadata: Dict, elements: Dict) -> str:
        """Determine content type for template selection"""
        duration = metadata.get('duration', 0)
        what = elements.get('what', '').lower()

        # Tutorial by default (most versatile)
        content_type = 'tutorial'

        # Speed only if very short AND about speed
        if duration <= 30:
            speed_keywords = ['quick', 'fast', 'seconds', 'rapid', 'instant']
            if any(kw in what for kw in speed_keywords):
                content_type = 'speed'

        return content_type

    def _fill_templates(self, templates: List[str], elements: Dict, analysis: Dict) -> List[str]:
        """Fill template placeholders with actual content"""
        filled = []

        for template in templates:
            try:
                title = template.format(
                    WHO=elements.get('who', 'I'),
                    WHAT=elements.get('what', 'Content'),
                    TIME=elements.get('time', ''),
                    FOOD=elements.get('food', 'Food'),
                    GAME=elements.get('game', 'Game'),
                    PRODUCT=elements.get('product', 'Product'),
                    TOPIC=elements.get('what', 'Topic'),
                    ACTION=analysis.get('detected_actions', ['make'])[0] if analysis.get('detected_actions') else 'make',
                    PLACE=analysis.get('scene_type', 'here'),
                    EXERCISE='Workout',
                    DIFFICULTY=elements.get('difficulty', ''),
                    RESULT=elements.get('result', ''),
                    NUMBER='1'
                )

                # Clean empty sections
                title = re.sub(r'\s+in\s+\|', ' |', title)
                title = re.sub(r'\s+in\s+$', '', title)
                title = re.sub(r'\|\s+$', '', title)
                title = re.sub(r'\s{2,}', ' ', title)
                title = title.strip()

                if title:
                    filled.append(title)

            except KeyError as e:
                logger.debug(f"Template missing key {e}: {template}")
                continue

        return filled[:10]  # Max 10 variants

    def _ai_refine_title(
        self,
        title_variants: List[str],
        analysis: Dict,
        platform: str
    ) -> str:
        """Use Groq AI to refine/select best title"""
        if not self.groq_client or not title_variants:
            return ""

        try:
            language_name = analysis.get('language_name', 'English')
            niche = analysis.get('niche', 'general')
            platform_limit = self.templates.get_platform_limit(platform)

            # Build content context
            content_desc = analysis.get('content_description', 'Unknown')
            objects = ', '.join(analysis.get('detected_objects', [])[:10])
            ocr_text = ', '.join(analysis.get('ocr_text', [])[:10])

            prompt = f"""You are an expert in creating viral {platform.upper()} titles in {language_name}.

VIDEO CONTENT:
- Language: {language_name}
- Niche: {niche}
- Platform: {platform.upper()}
- Description: {content_desc}
- Objects visible: {objects if objects else 'Unknown'}
- On-screen text: {ocr_text if ocr_text else 'None'}

TITLE OPTIONS:
{chr(10).join(f"{i+1}. {title}" for i, title in enumerate(title_variants[:5]))}

YOUR TASK:
Select the BEST option OR create a better title that:
✅ Is content-accurate (matches what's ACTUALLY in video)
✅ Is in {language_name} language ONLY
✅ Is under {platform_limit} characters
✅ Is engaging and clickable for {platform.upper()}
✅ NO generic words like "content", "video", "clip"
✅ NO invalid filename characters (/ \\ : * ? " < > |)

Return ONLY the final title in {language_name}, nothing else:"""

            response = self.groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=150,
                timeout=30
            )

            ai_title = response.choices[0].message.content.strip()
            ai_title = ai_title.strip('"\'')

            return ai_title

        except Exception as e:
            logger.warning(f"AI refinement failed: {e}")
            return ""

    def _clean_title(self, title: str, platform: str) -> str:
        """Clean and sanitize title"""
        # Remove quotes
        title = title.strip('"\'')

        # Remove invalid filename characters
        invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        for char in invalid_chars:
            title = title.replace(char, '')

        # Enforce platform limits
        platform_limit = self.templates.get_platform_limit(platform)
        if len(title) > platform_limit:
            title = title[:platform_limit].rsplit(' ', 1)[0]  # Cut at word boundary

        # Title case
        title = ' '.join(word.capitalize() if len(word) > 2 else word for word in title.split())

        return title.strip()

    def _fallback_title(self, video_info: Dict, language: str = 'en') -> str:
        """Generate fallback title from filename"""
        filename = Path(video_info.get('filename', 'Video')).stem

        # Clean filename
        title = re.sub(r'[_\-]+', ' ', filename)
        title = re.sub(r'\s{2,}', ' ', title)
        title = title.strip()

        # Title case
        title = ' '.join(word.capitalize() if len(word) > 2 else word for word in title.split())

        logger.warning(f"⚠️ Using fallback title: {title}")
        return title
