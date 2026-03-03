"""Validation functions for environment and video file checks.

Call validate_environment() at startup to ensure FFmpeg is available.
Call validate_video_file() before processing each video to verify format.
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


def validate_environment():
    """Check that FFmpeg is installed and available on system PATH.

    Raises:
        FFmpegNotFoundError: If FFmpeg is not found, with install instructions.
    """
    if shutil.which('ffmpeg') is None:
        raise FFmpegNotFoundError()


def validate_video_file(video_path: Path):
    """Validate that a video file exists and has a supported format.

    Args:
        video_path: Path to the video file to validate.

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
    if not video_path.exists():
        raise FileNotFoundError(
            f"Video file not found: {video_path}\n"
            "Suggestion: Check the file path and ensure the file exists."
        )

    if not video_path.is_file():
        raise ValueError(f"Path is not a file: {video_path}")

    # Check extension against supported formats (case-insensitive) - cheap check first
    supported_formats = {'.mp4', '.mkv', '.webm', '.avi'}
    file_extension = video_path.suffix.lower()

    if file_extension not in supported_formats:
        raise UnsupportedFormatError(file_extension, supported_formats)

    # Use FFmpeg probe to validate file integrity and check for audio stream
    try:
        probe_info = ffmpeg.probe(str(video_path))

        # Check for at least one audio stream
        has_audio = any(
            stream.get('codec_type') == 'audio'
            for stream in probe_info.get('streams', [])
        )

        if not has_audio:
            raise NoAudioStreamError(video_path.name)

        return probe_info

    except ffmpeg.Error as e:
        stderr = e.stderr.decode('utf8') if e.stderr else ""

        # Parse common error patterns
        if 'Invalid data' in stderr or 'End of file' in stderr:
            raise CorruptedFileError(video_path.name) from e
        else:
            # Generic FFmpeg validation error
            raise FileValidationError(video_path.name, stderr) from e
