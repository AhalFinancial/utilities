from transcribe.audio_ingest import ingest_audio
from transcribe.pipeline.run import run_transcription
from transcribe.storage import json_store


def test_ingest_converts_mp3(tmp_path, monkeypatch):
    source = tmp_path / "session.mp3"
    source.write_bytes(b"mp3-data")
    out_dir = tmp_path / "out"

    def fake_extract_audio(input_path, dest_path):
        dest_path.write_bytes(b"wav-data")

    monkeypatch.setattr("audio_ingest.extract_audio", fake_extract_audio)
    metadata = ingest_audio(source, out_dir)

    assert Path(metadata["ingest_path"]).exists()
    assert metadata["source_format"] == "mp3"
    assert metadata["ingest_format"] == "wav"
    assert metadata["ingest_steps"] == ["ffmpeg: extract_audio"]


def test_ingest_skips_conversion_for_normalized_wav(tmp_path, monkeypatch):
    source = tmp_path / "native.wav"
    source.write_bytes(b"wave-data")
    out_dir = tmp_path / "normalized"

    def fake_probe(path):
        assert path == str(source)
        return {
            "streams": [
                {
                    "codec_type": "audio",
                    "codec_name": "pcm_s16le",
                    "sample_rate": "16000",
                    "channels": 1,
                }
            ]
        }

    called = {"extract": False}

    def fake_extract_audio(*args, **kwargs):
        called["extract"] = True

    monkeypatch.setattr("audio_ingest.ffmpeg.probe", fake_probe)
    monkeypatch.setattr("audio_ingest.extract_audio", fake_extract_audio)
    metadata = ingest_audio(source, out_dir)

    assert metadata["ingest_steps"][0].startswith("copy:")
    assert not called["extract"]


def test_run_transcription_records_ingest_metadata(tmp_path):
    media = tmp_path / "input.wav"
    media.write_bytes(b"wav-data")
    base_dir = tmp_path / "workspace"

    def fake_transcribe(path, session_dir):
        return [], {"ingest_metadata": {"source_format": "wav"}, "tool_version": "0.1.0"}

    _, _, session_dir = run_transcription(media, transcribe_fn=fake_transcribe, base_dir=base_dir)
    run_meta = json_store.load_run_metadata(session_dir)

    assert run_meta.ingest_metadata == {"source_format": "wav"}
