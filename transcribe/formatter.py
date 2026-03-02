"""Transcript formatting to markdown with metadata."""

from datetime import datetime


def format_timestamp(seconds: float) -> str:
    """
    Convert seconds to HH:MM:SS timestamp format.

    Args:
        seconds: Time in seconds (can be float)

    Returns:
        Formatted timestamp string in HH:MM:SS format

    Examples:
        >>> format_timestamp(3665)
        '01:01:05'
        >>> format_timestamp(125.5)
        '00:02:05'
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def format_transcript(segments, info, video_filename: str) -> str:
    """
    Format transcription segments as markdown with metadata header.

    Creates a structured markdown document with:
    - Metadata header (source file, date, duration, language, model)
    - Timestamped transcript blocks

    Args:
        segments: List of transcription segments (from Transcriber)
        info: TranscriptionInfo object with language, duration, etc.
        video_filename: Original video filename for metadata

    Returns:
        Complete markdown transcript as string

    Examples:
        >>> markdown = format_transcript(segments, info, "meeting.mp4")
        >>> with open("meeting_transcript.md", "w") as f:
        ...     f.write(markdown)
    """
    lines = []

    # Metadata header
    lines.append("# Transcript")
    lines.append("")
    lines.append(f"**Source:** {video_filename}")
    lines.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Calculate duration from segments or use info.duration
    if segments:
        duration_seconds = segments[-1].end
    else:
        duration_seconds = getattr(info, 'duration', 0)

    duration_minutes = int(duration_seconds // 60)
    duration_secs = int(duration_seconds % 60)
    lines.append(f"**Duration:** {duration_minutes}m {duration_secs}s")

    lines.append(
        f"**Language:** {info.language} "
        f"(confidence: {info.language_probability:.2%})"
    )
    lines.append("**Model:** faster-whisper (small)")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Timestamped transcript blocks
    for segment in segments:
        timestamp = format_timestamp(segment.start)
        text = segment.text.strip()
        lines.append(f"[{timestamp}] {text}")

    return "\n".join(lines)
