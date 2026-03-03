"""Transcript formatting to markdown with metadata."""

import re
from datetime import datetime


# Legacy: Phase 1 format
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


def format_timestamp_adaptive(seconds: float, total_duration: float) -> str:
    """
    Convert seconds to adaptive timestamp format based on total duration.

    For videos under 1 hour: MM:SS format (no leading zero on minutes)
    For videos 1 hour or longer: H:MM:SS format (no leading zero on hours)

    Args:
        seconds: Time in seconds (can be float)
        total_duration: Total duration of video in seconds

    Returns:
        Formatted timestamp string in adaptive format

    Examples:
        >>> format_timestamp_adaptive(125, 3000)  # 5 min video
        '2:05'
        >>> format_timestamp_adaptive(125, 7200)  # 2 hour video
        '0:02:05'
        >>> format_timestamp_adaptive(3665, 7200)  # 2 hour video
        '1:01:05'
    """
    if total_duration >= 3600:  # 1 hour or longer
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours}:{minutes:02d}:{secs:02d}"
    else:  # Under 1 hour
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}:{secs:02d}"


def merge_segments_to_paragraphs(segments, gap_threshold=2.0):
    """
    Merge segments into flowing paragraphs at natural pauses.

    Segments separated by less than gap_threshold seconds are merged
    into a single paragraph under one timestamp. This creates more
    readable transcripts with fewer timestamp interruptions.

    Args:
        segments: List of transcription segments
        gap_threshold: Gap in seconds to trigger new paragraph (default 2.0)

    Returns:
        List of tuples: (start_timestamp, merged_text)

    Examples:
        >>> paragraphs = merge_segments_to_paragraphs(segments, gap_threshold=2.0)
        >>> for start, text in paragraphs:
        ...     print(f"[{start}] {text}")
    """
    if not segments:
        return []

    paragraphs = []
    current_paragraph_start = segments[0].start
    current_texts = []

    for i, segment in enumerate(segments):
        # Add current segment text
        current_texts.append(segment.text.strip())

        # Check if we should start a new paragraph
        is_last_segment = (i == len(segments) - 1)
        has_large_gap = False

        if not is_last_segment:
            next_segment = segments[i + 1]
            gap = next_segment.start - segment.end
            has_large_gap = gap > gap_threshold

        # Emit paragraph at natural pause or end
        if has_large_gap or is_last_segment:
            merged_text = " ".join(current_texts)
            paragraphs.append((current_paragraph_start, merged_text))

            # Reset for next paragraph
            if not is_last_segment:
                current_paragraph_start = segments[i + 1].start
                current_texts = []

    return paragraphs


def format_notes(
    summary_text: str,
    segments,
    info,
    video_filename: str,
    confidence_pct=None,
    model_name="small",
    style="executive",
    cost_usd=None
) -> str:
    """
    Format combined summary+transcript as markdown notes.

    Creates a structured markdown document with:
    - Summary at top (with style and cost metadata)
    - Full transcript below with all metadata and timestamps

    Args:
        summary_text: AI-generated summary text
        segments: List of transcription segments (from Transcriber)
        info: TranscriptionInfo object with language, duration, etc.
        video_filename: Original video filename for metadata
        confidence_pct: Optional quality score as percentage (0-100)
        model_name: Model used for transcription (default "small")
        style: Summary style used (executive, action-items, detailed)
        cost_usd: Optional cost of summarization in USD

    Returns:
        Complete markdown notes as string

    Examples:
        >>> markdown = format_notes(
        ...     summary_text, segments, info, "meeting.mp4",
        ...     confidence_pct=85.5, model_name="small",
        ...     style="executive", cost_usd=0.05
        ... )
        >>> with open("meeting_notes.md", "w") as f:
        ...     f.write(markdown)
    """
    lines = []

    # Calculate duration from segments or use info.duration
    if segments:
        duration_seconds = segments[-1].end
    else:
        duration_seconds = getattr(info, 'duration', 0)

    duration_minutes = int(duration_seconds // 60)
    duration_secs = int(duration_seconds % 60)

    # Header: Meeting Notes
    lines.append("# Meeting Notes")
    lines.append("")
    lines.append(f"**Source:** {video_filename}")
    lines.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"**Duration:** {duration_minutes}m {duration_secs}s")
    lines.append(
        f"**Language:** {info.language} "
        f"(confidence: {info.language_probability:.2%})"
    )
    lines.append(f"**Summary style:** {style}")

    # Add cost if provided
    if cost_usd is not None:
        lines.append(f"**Summary cost:** ~${cost_usd:.2f}")

    lines.append("")
    lines.append("---")
    lines.append("")

    # Summary section
    lines.append("## Summary")
    lines.append("")
    lines.append(summary_text)
    lines.append("")
    lines.append("---")
    lines.append("")

    # Full Transcript section
    lines.append("## Full Transcript")
    lines.append("")

    # Calculate word count and reading time
    all_text = " ".join(seg.text for seg in segments)
    word_count = len(re.findall(r'\w+', all_text))
    reading_time_min = max(1, (word_count + 179) // 180)  # Round up

    lines.append(f"**Word count:** {word_count}")
    lines.append(f"**Reading time:** ~{reading_time_min} min")

    # Add confidence if provided
    if confidence_pct is not None:
        lines.append(f"**Confidence:** {confidence_pct:.0f}%")

    lines.append(f"**Model:** faster-whisper ({model_name})")
    lines.append("")

    # Merge segments into paragraphs at natural pauses
    paragraphs = merge_segments_to_paragraphs(segments, gap_threshold=2.0)

    # Format paragraphs with adaptive timestamps
    for start_time, paragraph_text in paragraphs:
        timestamp = format_timestamp_adaptive(start_time, duration_seconds)
        lines.append(f"[{timestamp}]")
        lines.append(paragraph_text)
        lines.append("")  # Blank line between paragraphs

    return "\n".join(lines)


def format_transcript(segments, info, video_filename: str, confidence_pct=None, model_name="small") -> str:
    """
    Format transcription segments as markdown with metadata header.

    Creates a structured markdown document with:
    - Enriched metadata header (word count, reading time, confidence, model)
    - Paragraphs merged at natural pauses (>2s gaps)
    - Adaptive timestamps (MM:SS for <1hr, HH:MM:SS for longer)

    Args:
        segments: List of transcription segments (from Transcriber)
        info: TranscriptionInfo object with language, duration, etc.
        video_filename: Original video filename for metadata
        confidence_pct: Optional quality score as percentage (0-100)
        model_name: Model used for transcription (default "small")

    Returns:
        Complete markdown transcript as string

    Examples:
        >>> markdown = format_transcript(
        ...     segments, info, "meeting.mp4",
        ...     confidence_pct=85.5, model_name="medium"
        ... )
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

    # Calculate word count and reading time
    all_text = " ".join(seg.text for seg in segments)
    word_count = len(re.findall(r'\w+', all_text))
    reading_time_min = max(1, (word_count + 179) // 180)  # Round up

    lines.append(f"**Word count:** {word_count}")
    lines.append(f"**Reading time:** ~{reading_time_min} min")

    # Add confidence if provided
    if confidence_pct is not None:
        lines.append(f"**Confidence:** {confidence_pct:.0f}%")

    lines.append(f"**Model:** faster-whisper ({model_name})")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Merge segments into paragraphs at natural pauses
    paragraphs = merge_segments_to_paragraphs(segments, gap_threshold=2.0)

    # Format paragraphs with adaptive timestamps
    for start_time, paragraph_text in paragraphs:
        timestamp = format_timestamp_adaptive(start_time, duration_seconds)
        lines.append(f"[{timestamp}]")
        lines.append(paragraph_text)
        lines.append("")  # Blank line between paragraphs

    return "\n".join(lines)
