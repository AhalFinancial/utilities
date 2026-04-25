"""Validation functions for environment and media file checks.

Call validate_environment() at startup to ensure FFmpeg is available.
Call validate_media_file() before processing each media file to verify format.
"""

import shutil
import ffmpeg
from pathlib import Path

from transcribe.errors import (
    FFmpegNotFoundError,
    NoAudioStreamError,
    CorruptedFileError,
    UnsupportedFormatError,
    FileValidationError,
)


from transcribe.audio_ingest import SUPPORTED_AUDIO_FORMATS


VIDEO_FORMATS = {".mp4", ".mkv", ".webm", ".avi"}
MEDIA_FORMATS = VIDEO_FORMATS | SUPPORTED_AUDIO_FORMATS


def validate_environment():
    """Check that FFmpeg is installed and available on system PATH.

    Raises:
        FFmpegNotFoundError: If FFmpeg is not found, with install instructions.
    """
    if shutil.which('ffmpeg') is None:
        raise FFmpegNotFoundError()


def validate_media_file(media_path: Path):
    """Validate that a video or audio file exists and has a supported format.

    Args:
        media_path: Path to the media file to validate.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the path is not a file.
        UnsupportedFormatError: If file format is not supported.
        NoAudioStreamError: If video has no audio track.
        CorruptedFileError: If file is corrupted or unreadable.
        FileValidationError: If FFmpeg probe fails for other reasons.

    Returns:
        dict: FFmpeg probe information for the file.
    """
    if not media_path.exists():
        raise FileNotFoundError(
            f"Media file not found: {media_path}\n"
            "Suggestion: Check the file path and ensure the file exists."
        )

    if not media_path.is_file():
        raise ValueError(f"Path is not a file: {media_path}")

    # Check extension against supported formats (case-insensitive) - cheap check first
    supported_formats = MEDIA_FORMATS
    file_extension = media_path.suffix.lower()

    if file_extension not in supported_formats:
        raise UnsupportedFormatError(file_extension, supported_formats)

    # Use FFmpeg probe to validate file integrity and check for audio stream
    try:
        probe_info = ffmpeg.probe(str(media_path))

        # Check for at least one audio stream
        has_audio = any(
            stream.get('codec_type') == 'audio'
            for stream in probe_info.get('streams', [])
        )

        if not has_audio:
            raise NoAudioStreamError(media_path.name)

        return probe_info

    except ffmpeg.Error as e:
        stderr = e.stderr.decode('utf8') if e.stderr else ""

        # Parse common error patterns
        if 'Invalid data' in stderr or 'End of file' in stderr:
            raise CorruptedFileError(media_path.name) from e
        else:
            # Generic FFmpeg validation error
            raise FileValidationError(media_path.name, stderr) from e


def validate_video_file(video_path: Path):
    """Legacy helper that forwards to validate_media_file (video + audio)."""
    return validate_media_file(video_path)
