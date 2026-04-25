from pathlib import Path
import shutil

import ffmpeg

from transcribe.extractor import extract_audio


SUPPORTED_AUDIO_FORMATS = {".mp3", ".wav", ".flac", ".aac", ".m4a", ".ogg", ".opus"}
_TARGET_SAMPLE_RATE = 16000
_TARGET_CHANNELS = 1
_TARGET_CODEC = "pcm_s16le"


def _is_normalized_wav(source_path: Path) -> bool:
    if source_path.suffix.lower() != ".wav":
        return False

    try:
        probe_info = ffmpeg.probe(str(source_path))
    except ffmpeg.Error:
        return False

    for stream in probe_info.get("streams", []):
        if stream.get("codec_type") != "audio":
            continue
        codec = stream.get("codec_name", "").lower()
        sample_rate = stream.get("sample_rate")
        channels = stream.get("channels")
        try:
            sample_rate = int(float(sample_rate)) if sample_rate else None
        except (ValueError, TypeError):
            sample_rate = None

        if (
            codec == _TARGET_CODEC
            and sample_rate == _TARGET_SAMPLE_RATE
            and channels == _TARGET_CHANNELS
        ):
            return True
        return False
    return False


def ingest_audio(source_path: Path, output_dir: Path) -> dict:
    """
    Normalize any supported media file into 16kHz mono PCM WAV.

    Returns metadata describing the source and the converted path.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    target_path = output_dir / f"{source_path.stem}-ingested.wav"

    if _is_normalized_wav(source_path):
        shutil.copy2(source_path, target_path)
        ingest_steps = ["copy: already normalized WAV (16kHz mono PCM)"]
    else:
        extract_audio(source_path, target_path)
        ingest_steps = ["ffmpeg: extract_audio"]

    return {
        "source_path": str(source_path.resolve()),
        "source_format": source_path.suffix.lower().lstrip("."),
        "ingest_path": str(target_path.resolve()),
        "ingest_format": "wav",
        "ingest_sample_rate": _TARGET_SAMPLE_RATE,
        "ingest_channels": _TARGET_CHANNELS,
        "ingest_steps": ingest_steps,
    }
