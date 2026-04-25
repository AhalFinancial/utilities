from transcribe.models.transcript import TranscriptArtifact, TranscriptSegment
from transcribe.exporters.markdown import export_transcript_markdown


def test_export_transcript_markdown_basic():
    artifact = TranscriptArtifact(
        session_id="abc",
        source_path="C:/meeting.mp4",
        language="en",
        language_probability=0.9,
        duration=10.0,
        model_name="small",
        confidence_pct=90.0,
        quality_gate=None,
        segments=[
            TranscriptSegment(start=0.0, end=1.0, text="hello"),
            TranscriptSegment(start=1.0, end=2.0, text="world"),
        ],
    )
    md = export_transcript_markdown(artifact, "meeting.mp4")
    assert "# Transcript" in md
    assert "meeting.mp4" in md
