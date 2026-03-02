"""Validation functions for environment and video file checks.

Call validate_environment() at startup to ensure FFmpeg is available.
Call validate_video_file() before processing each video to verify format.
"""

import shutil
from pathlib import Path


def validate_environment():
    """Check that FFmpeg is installed and available on system PATH.

    Raises:
        RuntimeError: If FFmpeg is not found, with install instructions.
    """
    if shutil.which('ffmpeg') is None:
        raise RuntimeError(
            "FFmpeg is not installed or not found in PATH.\n\n"
            "Install FFmpeg:\n"
            "  macOS:   brew install ffmpeg\n"
            "  Ubuntu:  sudo apt-get install ffmpeg\n"
            "  Windows: Download from https://ffmpeg.org/download.html and add to PATH\n\n"
            "Verify installation: ffmpeg -version"
        )


def validate_video_file(video_path: Path):
    """Validate that a video file exists and has a supported format.

    Args:
        video_path: Path to the video file to validate.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the path is not a file or has unsupported format.
    """
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    if not video_path.is_file():
        raise ValueError(f"Path is not a file: {video_path}")

    # Check extension against supported formats (case-insensitive)
    supported_formats = {'.mp4', '.mkv', '.webm', '.avi'}
    file_extension = video_path.suffix.lower()

    if file_extension not in supported_formats:
        raise ValueError(
            f"Unsupported video format: {file_extension}\n"
            f"Supported formats: {', '.join(sorted(supported_formats))}"
        )
