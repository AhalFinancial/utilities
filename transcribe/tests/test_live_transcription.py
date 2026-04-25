import json
import shutil
import uuid
from pathlib import Path
from types import SimpleNamespace

from transcribe.pipeline.live_stream import LiveTranscriptionManager


class DummyTranscriber:
    def transcribe_with_quality(self, path, word_timestamps=True):
        text = f"transcript for {path.name}"
        segment = SimpleNamespace(text=text, avg_logprob=-0.5)
        info = SimpleNamespace(language="en", duration=1.0, language_probability=0.95)
        return ([segment], info, 95.0)


def test_live_manager_writes_transcript_files():
    temp_dir = Path(".planning") / f"tmp-live-{uuid.uuid4().hex[:8]}"
    try:
        temp_dir.mkdir(parents=True, exist_ok=True)
        manager = LiveTranscriptionManager(temp_dir, transcriber=DummyTranscriber(), executor_workers=1)
        manager.queue_chunk(0, temp_dir / "mic_0000.wav", temp_dir / "desktop_0000.wav", 0.0, 2.0)
        manager.queue_chunk(1, temp_dir / "mic_0001.wav", temp_dir / "desktop_0001.wav", 2.0, 2.0)
        manager.shutdown()

        json_path = temp_dir / "live_transcript.json"
        md_path = temp_dir / "live_transcript.md"

        assert json_path.exists()
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert data["entries"][0]["chunk_idx"] == 0
        assert data["entries"][1]["chunk_idx"] == 1

        assert md_path.exists()
        assert "Chunk 0" in md_path.read_text()
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
