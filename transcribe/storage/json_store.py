import json
from pathlib import Path
from typing import Optional

from transcribe.models.session import Session, RunMetadata
from transcribe.models.transcript import TranscriptArtifact
from transcribe.storage.paths import sessions_root


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _read_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_session(session: Session, session_dir: Path) -> Path:
    path = session_dir / "session.json"
    _write_json(path, session.to_dict())
    return path


def load_session(session_dir: Path) -> Session:
    return Session.from_dict(_read_json(session_dir / "session.json"))


def save_transcript(artifact: TranscriptArtifact, session_dir: Path) -> Path:
    path = session_dir / "transcript.json"
    _write_json(path, artifact.to_dict())
    return path


def load_transcript(session_dir: Path) -> TranscriptArtifact:
    return TranscriptArtifact.from_dict(_read_json(session_dir / "transcript.json"))


def save_run_metadata(metadata: RunMetadata, session_dir: Path) -> Path:
    path = session_dir / "run.json"
    _write_json(path, metadata.to_dict())
    return path


def load_run_metadata(session_dir: Path) -> RunMetadata:
    return RunMetadata.from_dict(_read_json(session_dir / "run.json"))


def update_run_metadata(session_dir: Path, summary_paths: dict) -> Path:
    metadata = load_run_metadata(session_dir)
    current = metadata.summary_paths or {}
    current.update(summary_paths)
    metadata.summary_paths = current
    return save_run_metadata(metadata, session_dir)


def save_recording_metadata(metadata: dict, session_dir: Path) -> Path:
    path = session_dir / "recording.json"
    _write_json(path, metadata)
    return path


def load_recording_metadata(session_dir: Path) -> dict:
    return _read_json(session_dir / "recording.json")


def append_live_transcript_entry(session_dir: Path, entry: dict) -> Path:
    path = session_dir / "live_transcript.json"
    data = {"entries": []}
    if path.exists():
        data = _read_json(path)
    entries = data.get("entries", [])
    entries.append(entry)
    data["entries"] = entries
    data["last_chunk"] = entry["chunk_idx"]
    _write_json(path, data)
    return path


def append_live_transcript_md(session_dir: Path, entry: dict) -> Path:
    path = session_dir / "live_transcript.md"
    header = f"### Chunk {entry['chunk_idx']} — {entry['start_seconds']:.1f}s (+{entry['duration_seconds']:.1f}s)"
    snippet = entry.get("transcript", "").strip() or "[no speech detected]"
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"{header}\n")
        f.write(f"{snippet}\n\n")
    return path


def find_session_dir(session_id: str, base_dir: Optional[Path] = None) -> Optional[Path]:
    root = sessions_root(base_dir)
    if not root.exists():
        return None
    for session_file in root.glob("*/*/session.json"):
        try:
            data = _read_json(session_file)
            if data.get("session_id") == session_id:
                return session_file.parent
        except Exception:
            continue
    return None
