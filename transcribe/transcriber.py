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

    def transcribe(self, audio_path: Path):
        """
        Transcribe audio file to text with timestamps.

        Args:
            audio_path: Path to audio file (WAV format recommended)

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
            word_timestamps=False  # Segment-level timestamps only for Phase 1
        )

        # Convert generator to list immediately to trigger transcription
        # and allow multiple iterations
        segments_list = list(segments)

        # Check for no-speech audio (empty segments)
        if not segments_list:
            raise ValueError("No speech detected in audio")

        return segments_list, info
