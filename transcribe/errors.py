"""Custom exception classes for transcription tool.

All exceptions extend TranscriptionError base class and provide:
- Clear error message describing what went wrong
- Actionable suggestion for how to fix it
- display() method for user-friendly terminal output
"""

import click
from typing import Optional


class TranscriptionError(Exception):
    """Base exception for all transcription errors.

    All subclasses should set message and optionally suggestion in __init__.
    """

    def __init__(self, message: str, suggestion: Optional[str] = None):
        """Initialize error with message and optional suggestion.

        Args:
            message: Description of what went wrong
            suggestion: Actionable suggestion for how to fix it
        """
        self.message = message
        self.suggestion = suggestion
        super().__init__(message)

    def display(self) -> None:
        """Display error message and suggestion to stderr with color formatting."""
        # Red error message
        click.echo(click.style(f"Error: {self.message}", fg='red'), err=True)

        # Yellow suggestion if provided
        if self.suggestion:
            click.echo(click.style(f"Suggestion: {self.suggestion}", fg='yellow'), err=True)


class FileValidationError(TranscriptionError):
    """Error validating video file (generic validation failure)."""

    def __init__(self, filename: str, details: str):
        """Initialize with filename and error details.

        Args:
            filename: Name of the file that failed validation
            details: Specific error details from validation
        """
        message = f"File validation failed for {filename}: {details}"
        suggestion = "Check that the file is a valid video file and not corrupted."
        super().__init__(message, suggestion)


class NoAudioStreamError(TranscriptionError):
    """Error when video file has no audio track."""

    def __init__(self, filename: str):
        """Initialize with filename that has no audio.

        Args:
            filename: Name of the file missing audio track
        """
        message = f"No audio track found in {filename}"
        suggestion = "Check that the file has an audio track, or try a different file"
        super().__init__(message, suggestion)


class CorruptedFileError(TranscriptionError):
    """Error when video file is corrupted or unreadable."""

    def __init__(self, filename: str):
        """Initialize with corrupted filename.

        Args:
            filename: Name of the corrupted file
        """
        message = f"File {filename} appears to be corrupted or unreadable"
        suggestion = (
            "Try re-downloading the file, or convert it with: "
            "ffmpeg -i input.mp4 -c:v copy -c:a copy output.mp4"
        )
        super().__init__(message, suggestion)


class UnsupportedFormatError(TranscriptionError):
    """Error when video file format is not supported."""

    def __init__(self, extension: str, supported_formats: set):
        """Initialize with unsupported format details.

        Args:
            extension: File extension that is not supported
            supported_formats: Set of supported file extensions
        """
        message = f"Unsupported video format: {extension}"
        formats_list = ', '.join(sorted(supported_formats))
        suggestion = f"Supported formats: {formats_list}"
        super().__init__(message, suggestion)


class APIKeyMissingError(TranscriptionError):
    """Error when OPENAI_API_KEY environment variable is not set."""

    def __init__(self):
        """Initialize with API key setup instructions."""
        message = "OPENAI_API_KEY environment variable not set"
        suggestion = (
            "Get your API key from: https://platform.openai.com/api-keys\n"
            "       Set it with: export OPENAI_API_KEY='your-key-here'"
        )
        super().__init__(message, suggestion)


class APIRetryExhaustedError(TranscriptionError):
    """Error when API retry attempts are exhausted."""

    def __init__(self, attempts: int, last_error: str):
        """Initialize with retry details.

        Args:
            attempts: Number of retry attempts made
            last_error: Description of the last error encountered
        """
        message = f"API call failed after {attempts} retry attempts: {last_error}"
        suggestion = (
            "Wait a few minutes and try again, or check your OpenAI usage dashboard at: "
            "https://platform.openai.com/usage"
        )
        super().__init__(message, suggestion)


class FFmpegNotFoundError(TranscriptionError):
    """Error when FFmpeg is not installed or not found in PATH."""

    def __init__(self):
        """Initialize with FFmpeg installation instructions."""
        message = "FFmpeg is not installed or not found in PATH"
        suggestion = (
            "Install FFmpeg:\n"
            "       macOS:   brew install ffmpeg\n"
            "       Ubuntu:  sudo apt-get install ffmpeg\n"
            "       Windows: Download from https://ffmpeg.org/download.html and add to PATH\n"
            "       Verify installation: ffmpeg -version"
        )
        super().__init__(message, suggestion)
