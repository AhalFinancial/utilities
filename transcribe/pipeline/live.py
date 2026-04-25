"""Live recording pipeline for capturing mic + desktop audio."""

from pathlib import Path
from typing import Callable, Dict, Optional, Tuple

from transcribe.models.session import RunMetadata, Session, now_iso
from transcribe.recorder.record import record_session
from transcribe.storage import json_store
from transcribe.storage.paths import now_timestamp, session_dir, session_id_for
from transcribe.pipeline.live_stream import LiveTranscriptionManager


def create_recording_session(source_label: str, base_dir: Optional[Path] = None) -> Tuple[Session, Path]:
    timestamp = now_timestamp()
    session_id = session_id_for(source_label, timestamp)
    sdir = session_dir(base_dir or Path.cwd(), timestamp, source_label)
    session = Session(
        session_id=session_id,
        source_path=source_label,
        source_name=source_label,
        created_at=now_iso(),
        session_dir=str(sdir.resolve()),
    )
    json_store.save_session(session, sdir)
    return session, sdir


def run_live_recording(
    mic_device: Dict,
    loopback_device: Dict,
    sample_rate: int = 48000,
    chunk_duration: float = 2.0,
    base_dir: Optional[Path] = None,
    max_seconds: Optional[float] = None,
    status_callback: Optional[Callable[[Dict], None]] = None,
) -> Tuple[Session, Path, dict]:
    session, sdir = create_recording_session("live-recording", base_dir=base_dir)
    started_at = now_iso()
    manager = LiveTranscriptionManager(sdir, status_callback=status_callback)
    try:
        result = record_session(
            sdir,
            mic_device=mic_device,
            loopback_device=loopback_device,
            sample_rate=sample_rate,
            chunk_duration=chunk_duration,
            max_seconds=max_seconds,
            chunk_callback=manager.queue_chunk,
        )
    finally:
        manager.shutdown()

    metadata = {
        "session_id": session.session_id,
        "started_at": started_at,
        "finished_at": now_iso(),
        "sample_rate": sample_rate,
        "chunk_duration": chunk_duration,
        "mic_device": {
            "index": mic_device.get("index"),
            "name": mic_device.get("name"),
            "hostapi": mic_device.get("hostapi"),
        },
        "loopback_device": {
            "index": loopback_device.get("index"),
            "name": loopback_device.get("name"),
            "hostapi": loopback_device.get("hostapi"),
        },
    }
    metadata.update(manager.metadata())
    metadata["chunk_paths"] = [str(p) for p in result.chunk_paths]
    metadata["duration_seconds"] = result.duration
    json_store.save_recording_metadata(metadata, sdir)

    run_metadata = RunMetadata(
        session_id=session.session_id,
        started_at=started_at,
        finished_at=now_iso(),
        tool_version="0.1.0",
        model_name=None,
        cost_usd=None,
    )
    json_store.save_run_metadata(run_metadata, sdir)

    return session, sdir, metadata
