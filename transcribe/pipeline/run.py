from pathlib import Path
from typing import Callable, Iterable, Optional, Tuple

from transcribe.models.session import Session, RunMetadata, now_iso
from transcribe.models.transcript import TranscriptArtifact, TranscriptSegment, WordTimestamp
from transcribe.storage import json_store
from transcribe.storage.paths import now_timestamp, session_dir, session_id_for


def create_session(source_path: Path, base_dir: Optional[Path] = None) -> Tuple[Session, Path]:
    timestamp = now_timestamp()
    session_id = session_id_for(str(source_path), timestamp)
    sdir = session_dir(base_dir or Path.cwd(), timestamp, source_path.stem)
    session = Session(
        session_id=session_id,
        source_path=str(source_path.resolve()),
        source_name=source_path.name,
        created_at=now_iso(),
        session_dir=str(sdir.resolve()),
    )
    json_store.save_session(session, sdir)
    return session, sdir


def build_transcript_artifact(
    session: Session,
    segments: Iterable[TranscriptSegment],
    language: Optional[str] = None,
    language_probability: Optional[float] = None,
    duration: Optional[float] = None,
    model_name: Optional[str] = None,
    confidence_pct: Optional[float] = None,
    quality_gate: Optional[dict] = None,
) -> TranscriptArtifact:
    return TranscriptArtifact(
        session_id=session.session_id,
        source_path=session.source_path,
        language=language,
        language_probability=language_probability,
        duration=duration,
        model_name=model_name,
        confidence_pct=confidence_pct,
        quality_gate=quality_gate,
        segments=list(segments),
    )


def run_transcription(
    source_path: Path,
    transcribe_fn: Optional[Callable[[Path], Tuple[Iterable[TranscriptSegment], dict]]] = None,
    base_dir: Optional[Path] = None,
) -> Tuple[Session, TranscriptArtifact, Path]:
    session, sdir = create_session(source_path, base_dir=base_dir)

    started_at = now_iso()
    if transcribe_fn is None:
        raise NotImplementedError("transcribe_fn is required for now")

    try:
        if transcribe_fn.__code__.co_argcount >= 2:
            segments, info = transcribe_fn(source_path, sdir)
        else:
            segments, info = transcribe_fn(source_path)
    except AttributeError:
        segments, info = transcribe_fn(source_path)
    artifact = build_transcript_artifact(
        session=session,
        segments=segments,
        language=info.get("language"),
        language_probability=info.get("language_probability"),
        duration=info.get("duration"),
        model_name=info.get("model_name"),
        confidence_pct=info.get("confidence_pct"),
        quality_gate=info.get("quality_gate"),
    )
    json_store.save_transcript(artifact, sdir)

    metadata = RunMetadata(
        session_id=session.session_id,
        started_at=started_at,
        finished_at=now_iso(),
        tool_version=info.get("tool_version", "0.1.0"),
        model_name=info.get("model_name"),
        cost_usd=info.get("cost_usd"),
        ingest_metadata=info.get("ingest_metadata"),
    )
    json_store.save_run_metadata(metadata, sdir)

    return session, artifact, sdir
