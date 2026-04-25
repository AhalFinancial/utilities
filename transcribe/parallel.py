"""Parallel chunk transcription for long-form audio.

Processes multiple audio chunks in parallel using ProcessPoolExecutor,
with timestamp adjustment and overlap deduplication.
"""

import logging
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Callable, Optional, Dict

from transcribe.transcriber import Transcriber
from transcribe.chunker import deduplicate_overlap
from transcribe.checkpoint import (
    save_checkpoint as save_checkpoint_to_disk,
    TranscriptionCheckpoint,
    get_checkpoint_path,
    calculate_file_hash
)

logger = logging.getLogger(__name__)


@dataclass
class MergedSegment:
    """
    Reassembled segment with adjusted timestamps.

    Used to represent segments after parallel transcription and timestamp
    adjustment, since original Whisper segment objects are not easily modified.
    """
    start: float
    end: float
    text: str
    avg_logprob: float
    words: Optional[List[dict]] = None


def _transcribe_single_chunk(chunk_path: str, model_size: str, language: Optional[str]) -> Tuple[List, dict]:
    """
    Transcribe a single chunk in a worker process.

    MODULE-LEVEL function (required for pickle/ProcessPoolExecutor compatibility).
    Creates a fresh Transcriber instance in the worker process and transcribes
    the chunk with VAD enabled.

    Args:
        chunk_path: Path to chunk WAV file
        model_size: Whisper model size (e.g., "small", "medium")
        language: Optional language code (None = auto-detect)

    Returns:
        Tuple of (segments_list, info_dict) where info_dict contains:
        - language: detected/specified language
        - duration: chunk duration in seconds
        - language_probability: language detection confidence
    """
    # Create fresh transcriber in worker process
    transcriber = Transcriber(model_size=model_size)

    # Transcribe with VAD
    segments, info = transcriber.transcribe(
        Path(chunk_path),
        language=language,
        vad_filter=True,
        word_timestamps=True
    )

    # Convert info to dict for serialization
    info_dict = {
        'language': info.language,
        'duration': info.duration,
        'language_probability': info.language_probability
    }

    return (segments, info_dict)


def _adjust_timestamps(segments: List, offset: float) -> List[MergedSegment]:
    """
    Adjust segment timestamps by adding offset.

    Args:
        segments: List of transcription segments
        offset: Time offset in seconds to add to each timestamp

    Returns:
        List of MergedSegment objects with adjusted timestamps
    """
    adjusted = []

    for seg in segments:
        adjusted_words = None
        if hasattr(seg, "words") and seg.words:
            adjusted_words = []
            for w in seg.words:
                if hasattr(w, "word"):
                    adjusted_words.append({
                        "word": w.word,
                        "start": w.start + offset,
                        "end": w.end + offset,
                        "probability": getattr(w, "probability", None),
                    })
                elif isinstance(w, dict):
                    adjusted_words.append({
                        "word": w.get("word"),
                        "start": w.get("start", 0) + offset,
                        "end": w.get("end", 0) + offset,
                        "probability": w.get("probability"),
                    })
        adjusted_seg = MergedSegment(
            start=seg.start + offset,
            end=seg.end + offset,
            text=seg.text,
            avg_logprob=seg.avg_logprob,
            words=adjusted_words
        )
        adjusted.append(adjusted_seg)

    return adjusted


def transcribe_chunks_parallel(
    chunks: List[Tuple[int, Path, float, float]],
    model_size: str = "small",
    language: Optional[str] = None,
    max_workers: Optional[int] = None,
    on_chunk_complete: Optional[Callable[[int], None]] = None,
    checkpoint_path: Optional[Path] = None,
    video_path: Optional[Path] = None,
    completed_chunks: Optional[Dict[int, str]] = None
) -> Tuple[List[MergedSegment], dict, List[Tuple[int, List, dict]]]:
    """
    Transcribe multiple chunks in parallel with ProcessPoolExecutor.

    Processes chunks concurrently, adjusts timestamps by start_time_offset,
    deduplicates overlapping text between consecutive chunks, and returns
    merged segments in correct order.

    Supports resume from checkpoint: already-completed chunks are skipped,
    and checkpoint is saved after each chunk completion.

    Args:
        chunks: List of (chunk_id, chunk_path, start_time_offset, duration) tuples
        model_size: Whisper model size (default "small")
        language: Optional language code (None = auto-detect)
        max_workers: Number of worker processes (None = auto-calculate)
        on_chunk_complete: Optional callback(chunk_id) called when chunk finishes
        checkpoint_path: Optional path to save checkpoints (enables resume)
        video_path: Optional original video path (for checkpoint hash validation)
        completed_chunks: Optional dict of already-completed chunk transcripts (from resume)

    Returns:
        Tuple of (merged_segments, info, all_segment_data) where:
        - merged_segments: List of MergedSegment with adjusted timestamps
        - info: Dict with combined transcription info
        - all_segment_data: List of (chunk_id, segments, info) for debugging
    """
    if not chunks:
        return ([], {}, [])

    # Initialize tracking structures
    completed_chunks = completed_chunks or {}
    chunk_transcripts = dict(completed_chunks)  # Copy for tracking new completions

    # Calculate max_workers if not provided
    # Use min(cpu_count, estimated_safe_parallel_tasks)
    # Assume 2GB per worker, 8GB available by default
    if max_workers is None:
        cpu_count = os.cpu_count() or 2
        # Conservative: allow 4 workers max on typical 8GB machine
        max_workers = min(cpu_count, max(1, 4))

    logger.info(f"Starting parallel transcription with {max_workers} workers")
    if completed_chunks:
        logger.info(f"Resuming from checkpoint: {len(completed_chunks)} chunks already completed")

    # Submit all chunks to executor (skip already-completed ones)
    futures_to_chunk = {}
    all_chunk_results = []

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        # Submit tasks only for incomplete chunks
        for chunk_id, chunk_path, start_offset, duration in chunks:
            if chunk_id in completed_chunks:
                # Skip this chunk - already completed
                logger.info(f"Skipping chunk {chunk_id} (already completed)")
                continue

            future = executor.submit(
                _transcribe_single_chunk,
                str(chunk_path),
                model_size,
                language
            )
            futures_to_chunk[future] = (chunk_id, start_offset)

        # Process results as they complete
        for future in as_completed(futures_to_chunk):
            chunk_id, start_offset = futures_to_chunk[future]

            try:
                segments, info_dict = future.result()

                # Adjust timestamps
                adjusted_segments = _adjust_timestamps(segments, start_offset)

                # Store result
                all_chunk_results.append((chunk_id, adjusted_segments, info_dict))

                # Store transcript text for checkpoint
                chunk_text = " ".join(seg.text for seg in adjusted_segments)
                chunk_transcripts[chunk_id] = chunk_text

                # Save checkpoint after each chunk completion (if enabled)
                if checkpoint_path and video_path:
                    checkpoint = TranscriptionCheckpoint(
                        video_path=str(video_path.resolve()),
                        video_hash=calculate_file_hash(video_path),
                        total_chunks=len(chunks),
                        completed_chunks=sorted(chunk_transcripts.keys()),
                        chunk_transcripts=chunk_transcripts,
                        language=language,
                        model_size=model_size,
                        timestamp=time.time()
                    )
                    save_checkpoint_to_disk(checkpoint, checkpoint_path)
                    logger.info(f"Checkpoint saved: {len(chunk_transcripts)}/{len(chunks)} chunks")

                # Notify progress callback
                if on_chunk_complete:
                    on_chunk_complete(chunk_id)

                logger.info(
                    f"Chunk {chunk_id} complete: {len(segments)} segments, "
                    f"offset {start_offset:.1f}s"
                )

            except Exception as e:
                logger.error(f"Chunk {chunk_id} failed: {e}")
                raise

    # Add completed chunks back as results (reconstruct from saved transcripts)
    for chunk_id in completed_chunks.keys():
        if chunk_id not in [r[0] for r in all_chunk_results]:
            # Find chunk metadata from original chunks list
            for cid, cpath, start_offset, duration in chunks:
                if cid == chunk_id:
                    # Create placeholder segment from saved transcript
                    transcript_text = completed_chunks[chunk_id]
                    placeholder_segment = MergedSegment(
                        start=start_offset,
                        end=start_offset + duration,
                        text=transcript_text,
                        avg_logprob=-0.5  # Assume decent quality
                    )
                    # Add as a single-segment result
                    all_chunk_results.append((
                        chunk_id,
                        [placeholder_segment],
                        {'language': language, 'duration': duration, 'language_probability': 0.95}
                    ))
                    break

    # Sort results by chunk_id to maintain order
    all_chunk_results.sort(key=lambda x: x[0])

    # Merge segments with deduplication
    merged_segments = []
    combined_info = {
        'language': None,
        'duration': 0.0,
        'language_probability': 0.0
    }

    if all_chunk_results:
        # Use info from first chunk
        _, _, first_info = all_chunk_results[0]
        combined_info['language'] = first_info['language']
        combined_info['language_probability'] = first_info['language_probability']

        # Calculate total duration from last chunk
        last_chunk_id, last_segments, _ = all_chunk_results[-1]
        if last_segments:
            combined_info['duration'] = last_segments[-1].end

    # Merge segments with overlap deduplication
    for i, (chunk_id, segments, info_dict) in enumerate(all_chunk_results):
        if i == 0:
            # First chunk: add all segments
            merged_segments.extend(segments)
        else:
            # Subsequent chunks: deduplicate overlap with previous chunk
            if merged_segments and segments:
                # Get last text from previous chunk
                prev_text = merged_segments[-1].text

                # Build current chunk text for deduplication
                current_texts = [seg.text for seg in segments]
                current_text = " ".join(current_texts)

                # Deduplicate
                deduped_text = deduplicate_overlap(prev_text, current_text)

                # Split deduped text back into segments
                # Simple approach: if deduplication removed text, skip overlapping segments
                if len(deduped_text) < len(current_text):
                    # Find where overlap ends by comparing lengths
                    removed_chars = len(current_text) - len(deduped_text)
                    chars_accumulated = 0
                    skip_count = 0

                    for seg in segments:
                        chars_accumulated += len(seg.text)
                        if chars_accumulated <= removed_chars:
                            skip_count += 1
                        else:
                            break

                    # Add non-overlapping segments
                    merged_segments.extend(segments[skip_count:])
                else:
                    # No significant overlap found, add all
                    merged_segments.extend(segments)
            else:
                # No previous segments or no current segments
                merged_segments.extend(segments)

    logger.info(f"Merged {len(merged_segments)} total segments from {len(chunks)} chunks")

    return (merged_segments, combined_info, all_chunk_results)
