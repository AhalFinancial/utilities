"""Speech-to-text transcription using faster-whisper."""

from faster_whisper import WhisperModel
from pathlib import Path


class Transcriber:
    """
    Whisper-based transcriber with lazy model loading.

    Uses the 'small' model by default (461MB, 244M params) which provides
    a good balance of accuracy and speed for 5-10 minute videos.

    The model is loaded lazily on first transcription to avoid startup delays.

    Examples:
        >>> transcriber = Transcriber()
        >>> segments, info = transcriber.transcribe(Path("audio.wav"))
        >>> print(f"Language: {info.language}")
    """

    def __init__(self, model_size: str = "small"):
        """
        Initialize transcriber with specified model size.

        Args:
            model_size: Whisper model size (tiny, base, small, medium, large).
                       Default: small (461MB, good accuracy/speed balance)
        """
        self.model_size = model_size
        self._model = None

    @property
    def model(self) -> WhisperModel:
        """
        Lazy-load Whisper model on first access.

        Uses CPU with int8 quantization for Phase 1 (simplest, works everywhere).
        Model is downloaded on first use if not cached.

        Returns:
            WhisperModel instance ready for transcription
        """
        if self._model is None:
            self._model = WhisperModel(
                self.model_size,
                device="cpu",
                compute_type="int8"
            )
        return self._model

    def transcribe(self, audio_path: Path, language=None, vad_filter=True, word_timestamps=False):
        """
        Transcribe audio file to text with timestamps.

        Args:
            audio_path: Path to audio file (WAV format recommended)
            language: Optional language code (e.g., "en", "es"). None = auto-detect
            vad_filter: Enable Voice Activity Detection to reduce hallucinations

        Returns:
            Tuple of (segments_list, info) where:
            - segments_list: List of transcribed segments with text and timestamps
            - info: TranscriptionInfo with language, duration, etc.

        Raises:
            ValueError: If no speech detected in audio

        Examples:
            >>> segments, info = transcriber.transcribe(Path("audio.wav"))
            >>> for segment in segments:
            ...     print(f"[{segment.start}] {segment.text}")
        """
        # Transcribe with beam_size=5 for better accuracy
        segments, info = self.model.transcribe(
            str(audio_path),
            beam_size=5,
            word_timestamps=word_timestamps,
            language=language,
            vad_filter=vad_filter,
            vad_parameters=dict(min_silence_duration_ms=500)
        )

        # Convert generator to list immediately to trigger transcription
        # and allow multiple iterations
        segments_list = list(segments)

        # Check for no-speech audio (empty segments)
        if not segments_list:
            raise ValueError("No speech detected in audio")

        return segments_list, info

    def detect_language(self, audio_path: Path):
        """
        Detect language from first 30 seconds of audio.

        Args:
            audio_path: Path to audio file

        Returns:
            Tuple of (language_code, language_probability)
            Returns (None, probability) if confidence is too low (< 0.5)

        Examples:
            >>> lang, prob = transcriber.detect_language(Path("audio.wav"))
            >>> if lang:
            ...     print(f"Detected {lang} with {prob:.2%} confidence")
        """
        # Transcribe first 30 seconds for language detection
        segments, info = self.model.transcribe(
            str(audio_path),
            beam_size=5,
            language=None,  # Force auto-detection
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
            condition_on_previous_text=False
        )

        # Consume generator to get info
        _ = list(segments)

        # Return language code only if confidence is acceptable
        language_code = info.language if info.language_probability >= 0.5 else None
        return (language_code, info.language_probability)

    def validate_quality(self, segments):
        """
        Validate transcription quality using avg_logprob metric.

        Args:
            segments: List of transcription segments

        Returns:
            Tuple of (is_acceptable, confidence_pct, avg_logprob) where:
            - is_acceptable: True if avg_logprob >= -1.0
            - confidence_pct: Quality score as percentage (0-100)
            - avg_logprob: Raw average log probability

        Examples:
            >>> ok, pct, logprob = transcriber.validate_quality(segments)
            >>> print(f"Quality: {pct:.0f}% (acceptable: {ok})")
        """
        if not segments:
            return (False, 0.0, -999.0)

        # Calculate average log probability across all segments
        total_logprob = sum(seg.avg_logprob for seg in segments)
        avg_logprob = total_logprob / len(segments)

        # Convert to 0-100% confidence score
        # -1.0 → 0%, 0.0 → 100%, -0.5 → 50%
        confidence_pct = max(0, min(100, (1 + avg_logprob) * 100))

        # Quality is acceptable if avg_logprob >= -1.0
        is_acceptable = avg_logprob >= -1.0

        return (is_acceptable, confidence_pct, avg_logprob)

    def transcribe_with_quality(self, audio_path: Path, language=None, word_timestamps=False):
        """
        Transcribe with quality validation and auto-upgrade to better model.

        This is the recommended entry point for production transcription.
        It validates quality and auto-upgrades from small to medium model
        if quality is unacceptable.

        Args:
            audio_path: Path to audio file
            language: Optional language code (None = auto-detect)

        Returns:
            Tuple of (segments, info, confidence_pct) where:
            - segments: List of transcription segments (with non-speech marked)
            - info: TranscriptionInfo
            - confidence_pct: Quality score as percentage

        Examples:
            >>> segments, info, confidence = transcriber.transcribe_with_quality(
            ...     Path("audio.wav"), language="en"
            ... )
            >>> print(f"Transcription quality: {confidence:.0f}%")
        """
        # Initial transcription
        segments, info = self.transcribe(audio_path, language=language, word_timestamps=word_timestamps)

        # Validate quality
        is_acceptable, confidence_pct, avg_logprob = self.validate_quality(segments)

        # Auto-upgrade to medium model if quality is poor and using small model
        if not is_acceptable and self.model_size == "small":
            print(f"Low confidence ({confidence_pct:.0f}%), retrying with medium model...")

            # Create new model with medium size
            original_model = self._model
            self._model = WhisperModel(
                "medium",
                device="cpu",
                compute_type="int8"
            )
            self.model_size = "medium"  # Update size for tracking

            # Re-transcribe
            segments, info = self.transcribe(audio_path, language=language, word_timestamps=word_timestamps)

            # Re-validate
            is_acceptable, confidence_pct, avg_logprob = self.validate_quality(segments)

        # Mark non-speech segments
        for segment in segments:
            # Mark segments with very low log probability as background noise
            if segment.avg_logprob < -1.5:
                segment.text = "[background noise]"
            # Also mark high no-speech probability if available
            elif hasattr(segment, 'no_speech_prob') and segment.no_speech_prob > 0.9:
                segment.text = "[background noise]"

        return (segments, info, confidence_pct)
