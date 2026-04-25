from pathlib import Path
from uuid import uuid4

from transcribe.models.transcript import TranscriptSegment, WordTimestamp
from transcribe.pipeline.run import run_transcription


def _temp_root() -> Path:
    root = Path("tmp_test") / uuid4().hex
    root.mkdir(parents=True, exist_ok=True)
    return root


def test_run_transcription_creates_artifacts() -> None:
    tmp_root = _temp_root()
    source = tmp_root / "audio.wav"
    source.write_text("dummy", encoding="utf-8")

    def fake_transcribe(_path: Path):
        segments = [
            TranscriptSegment(
                start=0.0,
                end=1.0,
                text="hello",
                avg_logprob=-0.1,
                words=[WordTimestamp(word="hello", start=0.0, end=1.0)],
            )
        ]
        info = {
            "language": "en",
            "language_probability": 0.9,
            "duration": 1.0,
            "model_name": "small",
            "confidence_pct": 95.0,
            "quality_gate": {"threshold": 40, "passed": True, "avg_logprob": -0.1},
            "tool_version": "0.1.0",
            "cost_usd": 0.0,
        }
        return segments, info

    session, artifact, sdir = run_transcription(source, transcribe_fn=fake_transcribe, base_dir=tmp_root)
    assert (sdir / "session.json").exists()
    assert (sdir / "transcript.json").exists()
    assert (sdir / "run.json").exists()
    assert artifact.language == "en"
    assert artifact.segments[0].words[0].word == "hello"
