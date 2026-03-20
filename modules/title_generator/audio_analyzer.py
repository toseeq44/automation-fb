"""
Audio Analyzer for Title Generator
Extracts audio content and detects language using Whisper AI
Supports: English, Portuguese, French, Spanish, Urdu, Hindi, Arabic, and more
"""

import os
import tempfile
from typing import Dict, List, Optional
from collections import Counter
from modules.logging.logger import get_logger

logger = get_logger(__name__)


class AudioAnalyzer:
    """Extract audio content and detect language using Whisper AI"""

    # Supported languages with full names
    SUPPORTED_LANGUAGES = {
        'en': 'English',
        'pt': 'Portuguese',
        'fr': 'French',
        'es': 'Spanish',
        'ur': 'Urdu',
        'hi': 'Hindi',
        'ar': 'Arabic',
        'de': 'German',
        'it': 'Italian',
        'ru': 'Russian',
        'ja': 'Japanese',
        'ko': 'Korean',
        'zh': 'Chinese',
        'tr': 'Turkish',
        'nl': 'Dutch',
        'pl': 'Polish',
        'sv': 'Swedish',
        'id': 'Indonesian',
        'th': 'Thai',
        'vi': 'Vietnamese'
    }

    # Language-specific stopwords for keyword extraction
    STOPWORDS = {
        'en': {'the', 'is', 'at', 'which', 'on', 'a', 'an', 'and', 'or', 'but',
               'in', 'with', 'to', 'for', 'of', 'as', 'by', 'this', 'that', 'it',
               'from', 'be', 'are', 'was', 'were', 'been', 'have', 'has', 'had'},

        'pt': {'o', 'a', 'os', 'as', 'um', 'uma', 'de', 'do', 'da', 'dos', 'das',
               'em', 'no', 'na', 'nos', 'nas', 'por', 'para', 'com', 'sem', 'sob',
               'é', 'são', 'foi', 'eram', 'ser', 'estar', 'ter', 'e', 'ou', 'mas'},

        'fr': {'le', 'la', 'les', 'un', 'une', 'des', 'de', 'du', 'au', 'aux',
               'dans', 'sur', 'avec', 'sans', 'pour', 'par', 'et', 'ou', 'mais',
               'est', 'sont', 'était', 'être', 'avoir', 'ce', 'cette', 'ces'},

        'es': {'el', 'la', 'los', 'las', 'un', 'una', 'de', 'del', 'al', 'en',
               'con', 'sin', 'por', 'para', 'y', 'o', 'pero', 'es', 'son', 'era',
               'ser', 'estar', 'tener', 'este', 'esta', 'estos', 'estas'},

        'ur': {'کا', 'کی', 'کے', 'میں', 'سے', 'نے', 'کو', 'پر', 'یہ', 'وہ',
               'ہے', 'ہیں', 'تھا', 'تھے', 'اور', 'یا', 'لیکن', 'کہ'},

        'hi': {'का', 'की', 'के', 'में', 'से', 'ने', 'को', 'पर', 'है', 'हैं',
               'था', 'थे', 'और', 'या', 'लेकिन', 'यह', 'वह', 'इस', 'उस'},

        'ar': {'في', 'من', 'إلى', 'على', 'عن', 'مع', 'هذا', 'ذلك', 'التي',
               'الذي', 'هو', 'هي', 'كان', 'كانت', 'و', 'أو', 'لكن'}
    }

    def __init__(self, model_size: str = 'base'):
        """
        Initialize Whisper model

        Args:
            model_size: Model size (tiny, base, small, medium, large)
                       'base' - Good balance of speed and accuracy (recommended)
                       'small' - Better accuracy, slower
                       'tiny' - Fastest, less accurate
        """
        self.model = None
        self.model_size = model_size
        self.whisper_available = False

        try:
            import whisper
            logger.info(f"Loading Whisper {model_size} model...")
            self.model = whisper.load_model(model_size)
            self.whisper_available = True
            logger.info("✅ Whisper model loaded successfully")
        except ImportError:
            logger.warning("⚠️ Whisper not installed. Run: pip install openai-whisper")
        except Exception as e:
            logger.error(f"❌ Failed to load Whisper model: {e}")

    def analyze_audio(self, video_path: str, sample_duration: int = 60) -> Dict:
        """
        Transcribe audio and detect language

        Args:
            video_path: Path to video file
            sample_duration: Duration to analyze (default: 60 seconds for speed)
                           Set to None for full video

        Returns:
            {
                'transcription': str,          # Full transcription
                'language': str,               # ISO code ('en', 'pt', 'fr', etc.)
                'language_name': str,          # Full name ('English', 'Portuguese')
                'confidence': float,           # 0-1 confidence score
                'keywords': List[str],         # Top keywords from speech
                'has_speech': bool,            # Whether speech was detected
                'duration_analyzed': float     # Seconds analyzed
            }
        """
        if not self.whisper_available:
            logger.warning("Whisper not available, skipping audio analysis")
            return self._empty_result()

        try:
            logger.info(f"🎙️ Analyzing audio from: {os.path.basename(video_path)}")

            # Extract audio to temp file for processing
            audio_path = self._extract_audio_temp(video_path, sample_duration)

            if not audio_path:
                logger.warning("Failed to extract audio")
                return self._empty_result()

            # Transcribe with Whisper
            logger.info("Transcribing audio (this may take a moment)...")
            result = self.model.transcribe(
                audio_path,
                task='transcribe',  # Don't translate, keep original language
                language=None,      # Auto-detect language
                fp16=False,         # CPU compatibility
                verbose=False       # Suppress Whisper logs
            )

            # Clean up temp audio file
            try:
                os.remove(audio_path)
            except:
                pass

            transcription = result['text'].strip()
            detected_language = result.get('language', 'en')

            if not transcription:
                logger.warning("No speech detected in audio")
                return self._empty_result()

            # Extract keywords from transcription
            keywords = self._extract_keywords_from_speech(
                transcription,
                detected_language
            )

            # Get language confidence (Whisper internal metric)
            # Note: This is an approximation, Whisper doesn't directly expose this
            confidence = self._estimate_language_confidence(result)

            analysis = {
                'transcription': transcription,
                'language': detected_language,
                'language_name': self.SUPPORTED_LANGUAGES.get(
                    detected_language,
                    detected_language.upper()
                ),
                'confidence': confidence,
                'keywords': keywords,
                'has_speech': True,
                'duration_analyzed': sample_duration or result.get('duration', 0)
            }

            logger.info(f"✅ Audio analysis complete: {analysis['language_name']} "
                       f"(confidence: {confidence:.1%})")
            logger.info(f"📝 Transcription: {transcription[:100]}{'...' if len(transcription) > 100 else ''}")
            logger.info(f"🔑 Keywords: {', '.join(keywords[:10])}")

            return analysis

        except Exception as e:
            logger.error(f"❌ Audio analysis failed: {e}")
            return self._empty_result()

    def _extract_audio_temp(self, video_path: str, duration: Optional[int] = None) -> Optional[str]:
        """
        Extract audio from video to temporary WAV file

        Args:
            video_path: Path to video
            duration: Max duration to extract (None = full)

        Returns:
            Path to temporary audio file
        """
        try:
            from moviepy import VideoFileClip

            # Create temp file
            temp_audio = os.path.join(
                tempfile.gettempdir(),
                f"audio_{os.getpid()}.wav"
            )

            # Load video and extract audio
            clip = VideoFileClip(video_path)

            if clip.audio is None:
                logger.warning("Video has no audio track")
                clip.close()
                return None

            # Trim to duration if specified
            if duration and clip.duration > duration:
                clip = clip.subclipped(0, duration)

            # Write audio to temp file
            clip.audio.write_audiofile(
                temp_audio,
                fps=16000,  # Whisper works best at 16kHz
                nbytes=2,
                codec='pcm_s16le',
                verbose=False,
                logger=None
            )

            clip.close()

            return temp_audio

        except Exception as e:
            logger.error(f"Failed to extract audio: {e}")
            return None

    def _extract_keywords_from_speech(
        self,
        transcription: str,
        language: str
    ) -> List[str]:
        """
        Extract important keywords from transcription
        Language-aware stopword removal

        Args:
            transcription: Transcribed text
            language: ISO language code

        Returns:
            List of top keywords
        """
        # Get stopwords for language (default to English)
        stopwords = self.STOPWORDS.get(language, self.STOPWORDS['en'])

        # Split into words
        words = transcription.split()

        # Clean and filter words
        cleaned_words = []
        for word in words:
            # Remove punctuation
            cleaned = word.strip('.,!?;:()"\'¿¡…')

            # Filter: must be 3+ chars and not a stopword
            if len(cleaned) >= 3 and cleaned.lower() not in stopwords:
                cleaned_words.append(cleaned)

        # Count frequency
        word_freq = Counter(cleaned_words)

        # Return top 20 most frequent keywords
        top_keywords = [word for word, count in word_freq.most_common(20)]

        return top_keywords

    def _estimate_language_confidence(self, result: Dict) -> float:
        """
        Estimate language detection confidence
        Based on Whisper output analysis

        Args:
            result: Whisper result dict

        Returns:
            Confidence score (0-1)
        """
        # Whisper doesn't expose confidence directly in all versions
        # We estimate based on:
        # 1. Presence of transcription
        # 2. Length of transcription
        # 3. Language detection consistency

        transcription = result.get('text', '')

        if not transcription:
            return 0.0

        # Longer transcriptions = higher confidence
        length_score = min(len(transcription) / 100, 1.0)

        # If language detection is consistent across segments
        segments = result.get('segments', [])
        if segments:
            detected_lang = result.get('language')
            segment_langs = [s.get('language', detected_lang) for s in segments]
            consistency = segment_langs.count(detected_lang) / len(segment_langs)
        else:
            consistency = 1.0

        # Combined confidence
        confidence = (length_score * 0.5) + (consistency * 0.5)

        return min(max(confidence, 0.3), 1.0)  # Clamp between 0.3 and 1.0

    def detect_language_only(self, video_path: str) -> str:
        """
        Quick language detection without full transcription
        Faster for just identifying language

        Args:
            video_path: Path to video

        Returns:
            ISO language code ('en', 'pt', 'fr', etc.)
        """
        if not self.whisper_available:
            return 'en'

        try:
            import whisper

            # Load first 30 seconds of audio only
            audio = whisper.load_audio(video_path, sr=16000)
            audio = audio[:30 * 16000]  # 30 seconds

            # Detect language
            audio_padded = whisper.pad_or_trim(audio)
            mel = whisper.log_mel_spectrogram(audio_padded).to(self.model.device)

            _, probs = self.model.detect_language(mel)

            # Get most probable language
            detected_lang = max(probs, key=probs.get)

            logger.info(f"Quick language detection: {detected_lang} "
                       f"({self.SUPPORTED_LANGUAGES.get(detected_lang, 'Unknown')}) "
                       f"- confidence: {probs[detected_lang]:.1%}")

            return detected_lang

        except Exception as e:
            logger.error(f"Language detection failed: {e}")
            return 'en'  # Default to English

    def _empty_result(self) -> Dict:
        """Return empty result when audio analysis fails"""
        return {
            'transcription': '',
            'language': 'en',
            'language_name': 'English',
            'confidence': 0.0,
            'keywords': [],
            'has_speech': False,
            'duration_analyzed': 0.0
        }
