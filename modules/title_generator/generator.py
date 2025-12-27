"""
Intelligent Title Generator using Groq API
Analyzes video metadata and generates engaging titles
"""

import re
from typing import Dict, Optional
from modules.logging.logger import get_logger
from .api_manager import APIKeyManager
from .frame_analyzer import FrameAnalyzer

logger = get_logger(__name__)


class TitleGenerator:
    """Generate engaging video titles using AI"""

    def __init__(self):
        """Initialize title generator"""
        self.api_manager = APIKeyManager()
        self.frame_analyzer = FrameAnalyzer()
        self.groq_client = None
        self._init_groq()

    def _init_groq(self):
        """Initialize Groq client"""
        try:
            from groq import Groq

            api_key = self.api_manager.get_api_key()
            if api_key:
                self.groq_client = Groq(api_key=api_key)
                logger.info("Groq client initialized")
            else:
                logger.warning("No API key found")

        except ImportError:
            logger.error("Groq library not installed. Install with: pip install groq")
        except Exception as e:
            logger.error(f"Failed to initialize Groq client: {e}")

    def generate_title(self, video_info: Dict) -> str:
        """
        Generate engaging title for video

        Args:
            video_info: Video metadata dict with 'filename', 'duration', 'folder', etc.

        Returns:
            Generated title string (sanitized for filename)
        """
        if not self.groq_client:
            logger.error("Groq client not initialized")
            return self._extract_title_from_filename(video_info['filename'])

        try:
            # Analyze video frames and extract content
            logger.info(f"Analyzing video: {video_info['filename']}")
            frame_analysis = self.frame_analyzer.analyze_video(video_info['path'])

            # Get video metadata
            metadata = self.frame_analyzer.get_video_metadata(video_info['path'])

            # Merge analysis results into video_info
            video_info['frame_analysis'] = frame_analysis
            video_info['metadata'] = metadata

            # Build intelligent prompt
            prompt = self._build_prompt(video_info)

            # Call Groq API
            logger.info(f"Generating title for: {video_info['filename']}")
            response = self.groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=100,
                timeout=30
            )

            # Extract title from response
            title = response.choices[0].message.content.strip()

            # Clean and validate title
            title = self._clean_title(title)

            logger.info(f"Generated title: {title}")
            return title

        except Exception as e:
            logger.error(f"Title generation failed: {e}")
            # Fallback to intelligent extraction from filename
            return self._extract_title_from_filename(video_info['filename'])

    def _build_prompt(self, video_info: Dict) -> str:
        """
        Build intelligent prompt for Groq API based on video content analysis

        Args:
            video_info: Video metadata with frame analysis

        Returns:
            Prompt string
        """
        # Get frame analysis results
        frame_analysis = video_info.get('frame_analysis', {})
        text_from_frames = frame_analysis.get('text_found', [])
        has_text = frame_analysis.get('has_text', False)

        # Get video metadata
        metadata = video_info.get('metadata', {})
        duration = metadata.get('duration', video_info.get('duration', 0))
        width = metadata.get('width', 0)
        height = metadata.get('height', 0)
        has_audio = metadata.get('has_audio', False)

        # Format duration
        duration_text = ""
        if duration > 0:
            minutes = int(duration // 60)
            seconds = int(duration % 60)
            if minutes > 0:
                duration_text = f"{minutes}:{seconds:02d}"
            else:
                duration_text = f"{seconds} seconds"

        # Format resolution
        resolution_text = ""
        if width > 0 and height > 0:
            if height >= 2160:
                resolution_text = "4K"
            elif height >= 1080:
                resolution_text = "1080p HD"
            elif height >= 720:
                resolution_text = "720p HD"
            else:
                resolution_text = f"{width}x{height}"

        # Build content-based prompt
        prompt = f"""Generate an engaging, SEO-optimized YouTube video title based on video content analysis:

Video Content Analysis:"""

        # Add extracted text from frames
        if has_text and text_from_frames:
            # Limit to most relevant text (first 5 unique items)
            unique_text = list(dict.fromkeys(text_from_frames))[:5]
            prompt += f"\n- Text Found in Video: {', '.join(unique_text)}"
        else:
            prompt += "\n- No readable text detected in video frames"

        # Add metadata
        if duration_text:
            prompt += f"\n- Duration: {duration_text}"
        if resolution_text:
            prompt += f"\n- Quality: {resolution_text}"
        if has_audio:
            prompt += "\n- Has Audio: Yes"

        # Add requirements
        prompt += """

Requirements:
1. Length: 50-60 characters (STRICT)
2. Style: Engaging, clickable, informative
3. Based on video CONTENT (text detected, visual analysis)
4. Use title case (capitalize major words)
5. Make it SEO-friendly and attention-grabbing
6. NO emojis or special file characters (/ \\ : * ? " < > |)
7. Return ONLY the title, nothing else

Examples of good titles:
- "How to Cook Perfect Pasta in 10 Minutes"
- "Top 5 Travel Destinations for 2025"
- "Ultimate Guide to Python Programming"
- "Amazing Street Food Tour in Tokyo"

Generate ONE title only:"""

        return prompt

    def _extract_keywords(self, filename: str) -> list:
        """
        Extract meaningful keywords from filename

        Args:
            filename: Video filename without extension

        Returns:
            List of keywords
        """
        # Remove common separators and clean
        cleaned = filename.replace('_', ' ').replace('-', ' ').replace('.', ' ')

        # Remove numbers at end (like _v2, _final, etc.)
        cleaned = re.sub(r'_?(v\d+|final|edit|new|old|\d+)$', '', cleaned, flags=re.IGNORECASE)

        # Split into words
        words = cleaned.split()

        # Filter out common noise words
        noise_words = {
            'video', 'clip', 'movie', 'final', 'edit', 'new', 'old',
            'copy', 'version', 'v1', 'v2', 'v3', 'hd', '4k', '1080p'
        }

        keywords = [
            word for word in words
            if len(word) > 2 and word.lower() not in noise_words
        ]

        return keywords[:10]  # Max 10 keywords

    def _clean_title(self, title: str) -> str:
        """
        Clean and sanitize title for use as filename

        Args:
            title: Raw title from AI

        Returns:
            Cleaned title string
        """
        # Remove quotes if present
        title = title.strip('"\'')

        # Remove any leading/trailing whitespace
        title = title.strip()

        # Remove invalid filename characters
        invalid_chars = r'[<>:"/\\|?*]'
        title = re.sub(invalid_chars, '', title)

        # Replace multiple spaces with single space
        title = re.sub(r'\s+', ' ', title)

        # Limit length (50-60 chars ideal, max 100)
        if len(title) > 100:
            title = title[:97] + '...'

        return title

    def _extract_title_from_filename(self, filename: str) -> str:
        """
        Fallback: Extract decent title from filename

        Args:
            filename: Original filename

        Returns:
            Title extracted from filename
        """
        # Remove extension
        name = filename.rsplit('.', 1)[0]

        # Replace separators with spaces
        name = name.replace('_', ' ').replace('-', ' ').replace('.', ' ')

        # Remove version numbers and common suffixes
        name = re.sub(r'_?(v\d+|final|edit|new|old|\d+)$', '', name, flags=re.IGNORECASE)

        # Title case
        name = name.title()

        # Clean
        name = self._clean_title(name)

        logger.info(f"Fallback title: {name}")
        return name
