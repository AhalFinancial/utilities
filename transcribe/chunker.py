"""Audio chunking for long-form transcription.

Splits long audio files at natural silence boundaries for parallel processing,
with overlap between chunks and text deduplication.
"""

import logging
import shutil
import tempfile
from difflib import SequenceMatcher
from pathlib import Path
from typing import List, Tuple

from pydub import AudioSegment
from pydub.silence import split_on_silence

logger = logging.getLogger(__name__)


def chunk_audio(
    audio_path: Path,
    min_duration_for_chunking: int = 600
) -> List[Tuple[int, Path, float, float]]:
    """
    Split audio into chunks at silence boundaries for parallel processing.

    For audio shorter than min_duration_for_chunking, returns single chunk.
    For longer audio, splits at silence points into ~20-25s chunks with 3s overlap.

    Args:
        audio_path: Path to WAV file to chunk
        min_duration_for_chunking: Minimum duration (seconds) to trigger chunking.
            Default 600 (10 minutes).

    Returns:
        List of tuples: (chunk_id, chunk_path, start_time_offset, duration)
        - chunk_id: Sequential chunk number (0-indexed)
        - chunk_path: Path to temporary WAV file for this chunk
        - start_time_offset: Starting time in original audio (seconds)
        - duration: Duration of this chunk (seconds)

    Examples:
        >>> chunks = chunk_audio(Path("audio.wav"), min_duration_for_chunking=600)
        >>> for chunk_id, path, offset, duration in chunks:
        ...     print(f"Chunk {chunk_id}: {duration:.1f}s at offset {offset:.1f}s")
    """
    # Load audio and get duration
    audio = AudioSegment.from_wav(str(audio_path))
    duration_seconds = len(audio) / 1000.0

    logger.info(f"Audio duration: {duration_seconds:.1f}s")

    # Short audio: return as single chunk
    if duration_seconds < min_duration_for_chunking:
        logger.info("Audio under threshold - no chunking needed")
        return [(0, audio_path, 0.0, duration_seconds)]

    # Long audio: split at silence boundaries
    logger.info("Splitting audio at silence boundaries...")

    try:
        # Split on silence: 500ms silence at -40dB, keep 100ms of silence
        chunks = split_on_silence(
            audio,
            min_silence_len=500,
            silence_thresh=-40,
            keep_silence=100
        )
    except Exception as e:
        # Edge case: no silence points or split failed
        logger.warning(f"Silence detection failed: {e}. Treating as single chunk.")
        return [(0, audio_path, 0.0, duration_seconds)]

    if not chunks:
        # Edge case: no chunks returned
        logger.warning("No chunks after silence split. Using original audio.")
        return [(0, audio_path, 0.0, duration_seconds)]

    logger.info(f"Initial split created {len(chunks)} segments")

    # Merge small chunks to target 20-25 seconds
    target_duration_ms = 20000  # 20 seconds minimum
    overlap_ms = 3000  # 3 second overlap

    merged_chunks = []
    current_chunk = AudioSegment.empty()

    for segment in chunks:
        current_chunk += segment

        # If we've accumulated enough, save it
        if len(current_chunk) >= target_duration_ms:
            merged_chunks.append(current_chunk)
            current_chunk = AudioSegment.empty()

    # Add any remaining audio as final chunk
    if len(current_chunk) > 0:
        # Merge with previous if very short (< 5 seconds)
        if len(current_chunk) < 5000 and merged_chunks:
            merged_chunks[-1] += current_chunk
        else:
            merged_chunks.append(current_chunk)

    logger.info(f"Merged to {len(merged_chunks)} chunks targeting 20-25s each")

    # Create temp directory for chunks
    chunk_dir = Path(tempfile.mkdtemp(prefix="transcribe_chunks_"))
    logger.info(f"Created chunk directory: {chunk_dir}")

    # Export chunks with overlap
    result = []
    cumulative_time_ms = 0

    for i, chunk in enumerate(merged_chunks):
        # Add overlap from previous chunk (except first)
        if i > 0:
            # Take last 3 seconds of previous chunk
            prev_chunk = merged_chunks[i - 1]
            overlap_segment = prev_chunk[-overlap_ms:] if len(prev_chunk) >= overlap_ms else prev_chunk
            chunk_with_overlap = overlap_segment + chunk
        else:
            chunk_with_overlap = chunk

        # Export to temp WAV file
        chunk_path = chunk_dir / f"chunk_{i:03d}.wav"
        chunk_with_overlap.export(str(chunk_path), format="wav")

        # Calculate start time offset (cumulative time minus overlap)
        start_offset_seconds = cumulative_time_ms / 1000.0
        chunk_duration_seconds = len(chunk_with_overlap) / 1000.0

        result.append((i, chunk_path, start_offset_seconds, chunk_duration_seconds))

        logger.info(
            f"Chunk {i}: {chunk_duration_seconds:.1f}s at offset {start_offset_seconds:.1f}s"
        )

        # Update cumulative time (don't count overlap)
        cumulative_time_ms += len(chunk)

    return result


def deduplicate_overlap(
    text_prev: str,
    text_next: str,
    overlap_words: int = 50,
    threshold: float = 0.85
) -> str:
    """
    Remove overlapping text between consecutive chunk transcriptions.

    Compares the end of text_prev with the beginning of text_next to find
    and remove duplicate content caused by chunk overlap.

    Args:
        text_prev: Text from previous chunk
        text_next: Text from next chunk
        overlap_words: Number of words to check for overlap (default 50)
        threshold: Similarity ratio to consider a match (default 0.85)

    Returns:
        Cleaned text_next with overlap removed

    Examples:
        >>> prev = "The quick brown fox jumps over the lazy dog"
        >>> next = "lazy dog and ran away"
        >>> deduplicate_overlap(prev, next, overlap_words=5)
        'and ran away'
    """
    if not text_prev or not text_next:
        return text_next

    # Split into words
    words_prev = text_prev.split()
    words_next = text_next.split()

    # Get comparison windows
    prev_tail = words_prev[-overlap_words:] if len(words_prev) > overlap_words else words_prev
    next_head = words_next[:overlap_words] if len(words_next) > overlap_words else words_next

    # Find longest common substring
    prev_tail_text = " ".join(prev_tail)
    next_head_text = " ".join(next_head)

    matcher = SequenceMatcher(None, prev_tail_text, next_head_text)
    match = matcher.find_longest_match(0, len(prev_tail_text), 0, len(next_head_text))

    # If match is significant, remove from next_head
    if match.size > 0:
        ratio = match.size / len(next_head_text) if len(next_head_text) > 0 else 0

        if ratio >= threshold:
            # Remove the overlapping portion from start of text_next
            # Convert character position back to word position
            matched_text = next_head_text[match.b:match.b + match.size]
            matched_words = matched_text.split()

            # Find where overlap ends in words_next
            overlap_word_count = 0
            for i, word in enumerate(words_next[:overlap_words]):
                if i < len(matched_words):
                    overlap_word_count = i + 1

            # Return text_next with overlap removed
            remaining_words = words_next[overlap_word_count:]
            result = " ".join(remaining_words)

            logger.info(
                f"Removed {overlap_word_count} overlapping words "
                f"(match ratio: {ratio:.2f})"
            )

            return result

    # No significant overlap found
    return text_next


def cleanup_chunks(chunk_dir: Path) -> None:
    """
    Remove temporary chunk directory and all files.

    Args:
        chunk_dir: Path to temporary chunk directory created by chunk_audio

    Examples:
        >>> chunks = chunk_audio(Path("audio.wav"))
        >>> # ... process chunks ...
        >>> cleanup_chunks(Path("/tmp/transcribe_chunks_xyz"))
    """
    if chunk_dir.exists() and chunk_dir.is_dir():
        shutil.rmtree(chunk_dir)
        logger.info(f"Cleaned up chunk directory: {chunk_dir}")
    else:
        logger.warning(f"Chunk directory not found: {chunk_dir}")
