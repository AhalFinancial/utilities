from typing import Optional

from transcribe.formatter import format_notes, format_transcript
from transcribe.models.transcript import TranscriptArtifact


class _Info:
    def __init__(self, language: Optional[str], duration: Optional[float], language_probability: Optional[float]):
        self.language = language or "unknown"
        self.duration = duration or 0.0
        self.language_probability = language_probability or 0.0


def export_transcript_markdown(
    artifact: TranscriptArtifact,
    source_name: str,
    confidence_pct: Optional[float] = None,
    model_name: Optional[str] = None,
) -> str:
    info = _Info(artifact.language, artifact.duration, artifact.language_probability)
    return format_transcript(
        artifact.segments,
        info,
        source_name,
        confidence_pct=confidence_pct or artifact.confidence_pct,
        model_name=model_name or (artifact.model_name or "unknown"),
    )


def export_notes_markdown(
    artifact: TranscriptArtifact,
    summary_text: str,
    source_name: str,
    confidence_pct: Optional[float] = None,
    model_name: Optional[str] = None,
    style: str = "executive",
    cost_usd: Optional[float] = None,
) -> str:
    info = _Info(artifact.language, artifact.duration, artifact.language_probability)
    return format_notes(
        summary_text=summary_text,
        segments=artifact.segments,
        info=info,
        video_filename=source_name,
        confidence_pct=confidence_pct or artifact.confidence_pct,
        model_name=model_name or (artifact.model_name or "unknown"),
        style=style,
        cost_usd=cost_usd,
    )
