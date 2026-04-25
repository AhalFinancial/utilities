from pathlib import Path
from uuid import uuid4

from transcribe.models.session import Session
from transcribe.storage import json_store
from transcribe.storage.paths import session_dir, session_id_for


def _temp_root() -> Path:
    root = Path("tmp_test") / uuid4().hex
    root.mkdir(parents=True, exist_ok=True)
    return root


def test_session_path_layout() -> None:
    tmp_root = _temp_root()
    source = Path("meeting.mp4")
    timestamp = "20260306-212300"
    sdir = session_dir(tmp_root, timestamp, source.stem)
    assert sdir.parts[-3] == "sessions"
    assert sdir.parts[-2] == "2026-03"
    assert sdir.parts[-1].startswith(timestamp)


def test_session_id_is_stable() -> None:
    sid1 = session_id_for("C:/file.mp4", "20260306-212300")
    sid2 = session_id_for("C:/file.mp4", "20260306-212300")
    assert sid1 == sid2


def test_session_json_roundtrip() -> None:
    tmp_root = _temp_root()
    sdir = tmp_root / "sessions" / "2026-03" / "20260306-212300-meeting"
    session = Session(
        session_id="abc123",
        source_path="C:/meeting.mp4",
        source_name="meeting.mp4",
        created_at="2026-03-06T21:23:00Z",
        session_dir=str(sdir),
    )
    json_store.save_session(session, sdir)
    loaded = json_store.load_session(sdir)
    assert loaded.session_id == "abc123"
    assert loaded.source_name == "meeting.mp4"
