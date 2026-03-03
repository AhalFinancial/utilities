"""Checkpoint management for resumable long-form transcription.

Provides atomic checkpoint save/load with file integrity validation.
Allows users to resume interrupted processing without starting over.
"""

import hashlib
import json
import os
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, List, Dict


@dataclass
class TranscriptionCheckpoint:
    """
    Checkpoint state for resumable transcription.

    Tracks progress through long-form video transcription so processing
    can resume from the last completed chunk after interruption.
    """
    video_path: str  # Absolute path to source video
    video_hash: str  # MD5 hash of first+last 64KB (quick change detection)
    total_chunks: int  # Expected number of chunks
    completed_chunks: List[int]  # Chunk IDs that finished
    chunk_transcripts: Dict[int, str]  # chunk_id -> transcript text for completed chunks
    language: Optional[str]  # Detected language (reuse on resume)
    model_size: str  # Whisper model used
    timestamp: float  # time.time() when saved


def calculate_file_hash(video_path: Path) -> str:
    """
    Calculate MD5 hash of first 64KB + last 64KB of file.

    Fast change detection without reading entire file. For files smaller
    than 128KB, hashes the entire file.

    Args:
        video_path: Path to video file

    Returns:
        MD5 hex digest string
    """
    file_size = video_path.stat().st_size
    hasher = hashlib.md5()

    with open(video_path, 'rb') as f:
        if file_size <= 128 * 1024:
            # Small file: hash the whole thing
            hasher.update(f.read())
        else:
            # Large file: hash first 64KB + last 64KB
            # Read first 64KB
            hasher.update(f.read(64 * 1024))

            # Seek to last 64KB
            f.seek(-64 * 1024, 2)
            hasher.update(f.read(64 * 1024))

    return hasher.hexdigest()


def get_checkpoint_path(video_path: Path) -> Path:
    """
    Get checkpoint file path for a given video.

    Checkpoint is saved in same directory as video with .checkpoint.json suffix.

    Args:
        video_path: Path to video file

    Returns:
        Path to checkpoint file
    """
    return video_path.parent / f"{video_path.stem}.checkpoint.json"


def save_checkpoint(checkpoint: TranscriptionCheckpoint, checkpoint_path: Path) -> None:
    """
    Atomically save checkpoint to disk.

    Writes to temporary file first, then uses os.replace() for atomic write.
    Ensures checkpoint is never partially written.

    Args:
        checkpoint: Checkpoint state to save
        checkpoint_path: Where to save checkpoint file
    """
    tmp_path = checkpoint_path.with_suffix('.tmp')

    try:
        # Write to temporary file
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(asdict(checkpoint), f, indent=2)

        # Atomic replace (on Windows, this requires removing the target first if it exists)
        if checkpoint_path.exists():
            checkpoint_path.unlink()
        os.replace(tmp_path, checkpoint_path)

    except Exception:
        # Clean up temp file on error
        if tmp_path.exists():
            tmp_path.unlink()
        raise


def load_checkpoint(checkpoint_path: Path) -> Optional[TranscriptionCheckpoint]:
    """
    Load checkpoint from disk.

    Returns None if file doesn't exist or can't be parsed (invalid/corrupted).

    Args:
        checkpoint_path: Path to checkpoint file

    Returns:
        TranscriptionCheckpoint if valid, None otherwise
    """
    if not checkpoint_path.exists():
        return None

    try:
        with open(checkpoint_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # JSON converts int dict keys to strings - convert back
        if 'chunk_transcripts' in data and data['chunk_transcripts']:
            data['chunk_transcripts'] = {int(k): v for k, v in data['chunk_transcripts'].items()}

        # Construct dataclass from dict
        return TranscriptionCheckpoint(**data)

    except (json.JSONDecodeError, TypeError, KeyError, ValueError):
        # Invalid checkpoint file
        return None


def can_resume_from_checkpoint(checkpoint: TranscriptionCheckpoint, video_path: Path) -> bool:
    """
    Validate checkpoint against current video file.

    Checks that:
    - Video file path matches checkpoint
    - Video file hash matches checkpoint (file hasn't changed)

    Args:
        checkpoint: Checkpoint to validate
        video_path: Current video file path

    Returns:
        True if checkpoint is valid for this video, False otherwise
    """
    # Verify path matches
    if str(video_path.resolve()) != checkpoint.video_path:
        return False

    # Verify hash matches (file hasn't changed)
    current_hash = calculate_file_hash(video_path)
    if current_hash != checkpoint.video_hash:
        return False

    return True


def delete_checkpoint(checkpoint_path: Path) -> None:
    """
    Delete checkpoint file if it exists.

    Silently ignores if file doesn't exist.

    Args:
        checkpoint_path: Path to checkpoint file to delete
    """
    if checkpoint_path.exists():
        checkpoint_path.unlink()
