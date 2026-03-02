"""Audio extraction from video files using FFmpeg."""

import ffmpeg
from pathlib import Path


def extract_audio(video_path: Path, output_path: Path) -> None:
    """
    Extract audio from video file to WAV format.

    Extracts audio track to 16kHz mono WAV (PCM signed 16-bit little-endian)
    format optimized for Whisper transcription.

    Args:
        video_path: Path to input video file (MP4, MKV, WebM, or AVI)
        output_path: Path for output WAV file

    Raises:
        RuntimeError: If video file is corrupted, has no audio track, or FFmpeg fails

    Examples:
        >>> extract_audio(Path("video.mp4"), Path("audio.wav"))
    """
    try:
        (
            ffmpeg
            .input(str(video_path))
            .output(str(output_path), acodec='pcm_s16le', ac=1, ar='16000')
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
    except ffmpeg.Error as e:
        stderr = e.stderr.decode('utf8')

        # Parse common error patterns and provide user-friendly messages
        if 'Invalid data found' in stderr or 'could not find codec' in stderr:
            raise RuntimeError(
                f"Could not read {video_path.name} — file may be corrupted"
            ) from e
        elif 'Output file is empty' in stderr or 'does not contain any stream' in stderr:
            raise RuntimeError(
                f"No audio track found in {video_path.name}"
            ) from e
        else:
            # Unknown FFmpeg error
            raise RuntimeError(
                f"FFmpeg error processing {video_path.name}"
            ) from e
