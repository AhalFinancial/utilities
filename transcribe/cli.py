"""CLI interface for transcription tool with session-based output."""

import sys
import shutil
import tempfile
import json
from pathlib import Path

import click

from transcribe.validators import validate_environment, validate_media_file
from transcribe.audio_ingest import ingest_audio
from transcribe.transcriber import Transcriber
from transcribe.chunker import chunk_audio, cleanup_chunks
from transcribe.parallel import transcribe_chunks_parallel
from transcribe.progress import ProgressDisplay
from transcribe.summarizer import check_api_key, summarize_with_quality_gate
from transcribe.prompts import detect_summary_style
from transcribe.errors import TranscriptionError, APIKeyMissingError
from transcribe.checkpoint import (
    get_checkpoint_path,
    load_checkpoint,
    can_resume_from_checkpoint,
    delete_checkpoint,
)
from transcribe.models.transcript import TranscriptSegment, WordTimestamp
from transcribe.pipeline import run_transcription
from transcribe.pipeline.live import run_live_recording
from transcribe.recorder import prompt_for_devices, select_default_devices
from transcribe.exporters import export_transcript_markdown, export_notes_markdown, export_markdown_pdf
from transcribe.summaries import build_process_mapping_json, render_process_mapping_markdown
from transcribe.context import load_context, build_strategies
from transcribe.storage import json_store
from transcribe.storage.paths import sessions_root


def _segments_to_models(segments):
    converted = []
    for seg in segments:
        words = []
        if hasattr(seg, "words") and seg.words:
            for w in seg.words:
                if hasattr(w, "word"):
                    words.append(
                        WordTimestamp(
                            word=w.word,
                            start=w.start,
                            end=w.end,
                            probability=getattr(w, "probability", None),
                        )
                    )
                elif isinstance(w, dict):
                    words.append(
                        WordTimestamp(
                            word=w.get("word", ""),
                            start=w.get("start", 0.0),
                            end=w.get("end", 0.0),
                            probability=w.get("probability"),
                        )
                    )
        converted.append(
            TranscriptSegment(
                start=seg.start,
                end=seg.end,
                text=seg.text,
                avg_logprob=getattr(seg, "avg_logprob", None),
                words=words or None,
            )
        )
    return converted


def _transcribe_media(
    media_path: Path,
    quiet: bool,
    no_summary: bool,
    style: str,
    no_resume: bool,
    checkpoint_path: Path,
):
    validate_environment()
    validate_media_file(media_path)

    if not no_summary:
        check_api_key()

    resume_checkpoint = None
    if not no_resume and checkpoint_path.exists():
        loaded_checkpoint = load_checkpoint(checkpoint_path)
        if loaded_checkpoint and can_resume_from_checkpoint(loaded_checkpoint, media_path):
            if quiet or click.confirm("Resume from checkpoint?", default=True):
                resume_checkpoint = loaded_checkpoint
                if not quiet:
                    click.echo("Resuming from checkpoint...")
        elif loaded_checkpoint:
            click.echo(
                click.style(
                    "Warning: Checkpoint found but media file has changed. Starting fresh.",
                    fg="yellow",
                ),
                err=True,
            )
            delete_checkpoint(checkpoint_path)

    chunk_temp_dir = None
    ingestion_metadata = None
    temp_dir = None
    progress = ProgressDisplay(quiet=quiet)

    try:
        temp_dir = Path(tempfile.mkdtemp())

        progress.start_extraction()
        ingestion_metadata = ingest_audio(media_path, temp_dir)
        progress.finish_extraction()

        temp_audio = Path(ingestion_metadata["ingest_path"])

        transcriber = Transcriber(model_size="small")
        language, lang_prob = transcriber.detect_language(temp_audio)
        if not quiet and language:
            click.echo(f"Detected language: {language} ({lang_prob:.0%})")

        chunks = chunk_audio(temp_audio)
        if len(chunks) > 1:
            chunk_temp_dir = chunks[0][1].parent

        confidence_pct = None
        avg_logprob = None
        if len(chunks) == 1:
            progress.start_transcription(total_chunks=1)
            segments, info, confidence_pct = transcriber.transcribe_with_quality(
                temp_audio, language=language, word_timestamps=True
            )
            progress.finish_transcription()
            _ok, _pct, avg_logprob = transcriber.validate_quality(segments)
        else:
            completed_chunk_transcripts = None
            if resume_checkpoint:
                completed_chunk_transcripts = resume_checkpoint.chunk_transcripts

            progress.start_transcription(total_chunks=len(chunks))
            segments, info_dict, _all_segment_data = transcribe_chunks_parallel(
                chunks,
                model_size="small",
                language=language,
                on_chunk_complete=lambda cid: progress.update_transcription(cid),
                checkpoint_path=checkpoint_path,
                video_path=media_path,
                completed_chunks=completed_chunk_transcripts,
            )
            progress.finish_transcription()

            is_acceptable, confidence_pct, avg_logprob = transcriber.validate_quality(segments)
            if not is_acceptable:
                if not quiet:
                    click.echo(f"Low confidence ({confidence_pct:.0f}%), retrying with medium model...")
                delete_checkpoint(checkpoint_path)
                progress.start_transcription(total_chunks=len(chunks))
                segments, info_dict, _all_segment_data = transcribe_chunks_parallel(
                    chunks,
                    model_size="medium",
                    language=language,
                    on_chunk_complete=lambda cid: progress.update_transcription(cid),
                    checkpoint_path=checkpoint_path,
                    video_path=media_path,
                    completed_chunks=None,
                )
                progress.finish_transcription()
                is_acceptable, confidence_pct, avg_logprob = transcriber.validate_quality(segments)

            class InfoObject:
                def __init__(self, d):
                    self.language = d["language"]
                    self.duration = d["duration"]
                    self.language_probability = d["language_probability"]

            info = InfoObject(info_dict)

        all_text = " ".join(seg.text for seg in segments)
        summary_text = None
        cost_usd = None
        used_style = style

        if not no_summary and (style or "").lower() != "process-mapping":
            summary_language = getattr(info, "language", "en") or "en"
            if used_style is None:
                detected_style = detect_summary_style(all_text)
                if not quiet:
                    click.echo(f"Auto-selected summary style: {detected_style}")
                used_style = detected_style
            if not quiet:
                click.echo("Generating summary...")
            summary_text, cost_usd, _attempted = summarize_with_quality_gate(
                transcript_text=all_text,
                confidence_pct=confidence_pct or 100.0,
                style=used_style,
                language=summary_language,
                quiet=quiet,
            )

        if confidence_pct and confidence_pct < 50:
            progress.warn(f"Low confidence detected ({confidence_pct:.0f}%)")

        delete_checkpoint(checkpoint_path)

        info_dict = {
            "language": getattr(info, "language", None),
            "language_probability": getattr(info, "language_probability", None),
            "duration": getattr(info, "duration", None),
            "model_name": transcriber.model_size,
            "confidence_pct": confidence_pct,
            "quality_gate": {
                "threshold": 40,
                "passed": bool(confidence_pct is None or confidence_pct >= 40),
                "avg_logprob": avg_logprob,
            },
            "tool_version": "0.1.0",
            "cost_usd": cost_usd,
        }

        if ingestion_metadata is not None:
            info_dict["ingest_metadata"] = ingestion_metadata

        return segments, info_dict, summary_text, cost_usd, used_style

    finally:
        if chunk_temp_dir:
            cleanup_chunks(chunk_temp_dir)
        if temp_dir and temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)


@click.group(invoke_without_command=True, context_settings={"allow_extra_args": True})
@click.option("-q", "--quiet", is_flag=True, help="Suppress progress output")
@click.option("--force", is_flag=True, help="Overwrite existing output without asking")
@click.option("--no-summary", is_flag=True, help="Skip summarization, produce transcript only")
@click.option(
    "--style",
    type=click.Choice(["executive", "action-items", "detailed", "process-mapping"], case_sensitive=False),
    default=None,
    help="Summary style (default: auto-detect)",
)
@click.option(
    "--process-template",
    type=click.Choice(["standard", "compliance", "audit"], case_sensitive=False),
    default="standard",
    help="Process-mapping template variant",
)
@click.option("--context-file", type=click.Path(), default=None, help="External context file")
@click.option("--context-text", type=str, default=None, help="Inline context text")
@click.option("--context-dir", type=click.Path(), default=None, help="Directory of context files")
@click.option("--no-resume", is_flag=True, help="Start fresh even if checkpoint exists")
@click.option("--legacy", is_flag=True, help="Write legacy outputs next to source file")
@click.option("--pdf", "pdf", is_flag=True, help="Export PDF from markdown output")
@click.option("--pdf-output", type=click.Path(), default=None, help="PDF output path")
@click.pass_context
def main(
    ctx,
    quiet,
    force,
    no_summary,
    style,
    no_resume,
    legacy,
    process_template,
    context_file,
    context_text,
    context_dir,
    pdf,
    pdf_output,
):
    if ctx.invoked_subcommand is None:
        if not ctx.args:
            click.echo("Error: media file is required.", err=True)
            sys.exit(1)
        if len(ctx.args) > 1:
            click.echo("Error: too many arguments. Provide a single media file.", err=True)
            sys.exit(1)
        video_file = ctx.args[0]
        if not Path(video_file).exists():
            click.echo(f"Error: media file not found: {video_file}", err=True)
            sys.exit(1)
        ctx.invoke(
            file,
            video_file=video_file,
            quiet=quiet,
            force=force,
            no_summary=no_summary,
            style=style,
            no_resume=no_resume,
            legacy=legacy,
            process_template=process_template,
            context_file=context_file,
            context_text=context_text,
            context_dir=context_dir,
            pdf=pdf,
            pdf_output=pdf_output,
        )


@main.command()
@click.argument("video_file", type=click.Path(exists=True))
@click.option("-q", "--quiet", is_flag=True, help="Suppress progress output")
@click.option("--force", is_flag=True, help="Overwrite existing output without asking")
@click.option("--no-summary", is_flag=True, help="Skip summarization, produce transcript only")
@click.option(
    "--style",
    type=click.Choice(["executive", "action-items", "detailed", "process-mapping"], case_sensitive=False),
    default=None,
    help="Summary style (default: auto-detect)",
)
@click.option(
    "--process-template",
    type=click.Choice(["standard", "compliance", "audit"], case_sensitive=False),
    default="standard",
    help="Process-mapping template variant",
)
@click.option("--context-file", type=click.Path(), default=None, help="External context file")
@click.option("--context-text", type=str, default=None, help="Inline context text")
@click.option("--context-dir", type=click.Path(), default=None, help="Directory of context files")
@click.option("--no-resume", is_flag=True, help="Start fresh even if checkpoint exists")
@click.option("--legacy", is_flag=True, help="Write legacy outputs next to source file")
@click.option("--pdf", "pdf", is_flag=True, help="Export PDF from markdown output")
@click.option("--pdf-output", type=click.Path(), default=None, help="PDF output path")
def file(
    video_file,
    quiet,
    force,
    no_summary,
    style,
    process_template,
    context_file,
    context_text,
    context_dir,
    no_resume,
    legacy,
    pdf,
    pdf_output,
):
    """Transcribe a video or audio file into the session-based workflow."""
    try:
        video_path = Path(video_file)

        def transcribe_fn(path: Path, session_dir: Path):
            checkpoint_path = (
                session_dir / "checkpoint.json"
                if not legacy
                else get_checkpoint_path(video_path)
            )
            segments, info_dict, summary_text, cost_usd, used_style = _transcribe_media(
                path, quiet, no_summary, style, no_resume, checkpoint_path
            )
            transcribe_fn.summary_text = summary_text
            transcribe_fn.cost_usd = cost_usd
            transcribe_fn.used_style = used_style
            return _segments_to_models(segments), info_dict

        session, artifact, session_dir = run_transcription(video_path, transcribe_fn=transcribe_fn)

        transcript_md = export_transcript_markdown(
            artifact, video_path.name, model_name=artifact.model_name
        )
        transcript_path = Path(session_dir) / "transcript.md"

        if transcript_path.exists() and not force:
            if not click.confirm(f"{transcript_path.name} exists. Overwrite?"):
                click.echo("Cancelled.")
                return

        transcript_path.write_text(transcript_md, encoding="utf-8")

        process_mapping_json = None
        process_mapping_md = None
        if not no_summary and (style or "").lower() == "process-mapping":
            sections = load_context(
                Path(context_file) if context_file else None,
                context_text,
                Path(context_dir) if context_dir else None,
            )
            context_text_selected = None
            if sections:
                options = ["Full context", "Top-N relevant", "Hard cap"]
                strategies = build_strategies(
                    " ".join(seg.text for seg in artifact.segments),
                    sections,
                )
                click.echo("Context strategies with estimated cost:")
                for idx, opt in enumerate(options):
                    est = strategies[idx]
                    click.echo(f"{idx + 1}. {opt} (~${est.estimated_cost_usd:.4f})")
                selection = click.prompt("Select context strategy", type=click.Choice(["1", "2", "3"]), default="2")
                context_text_selected = strategies[int(selection) - 1].text

            process_mapping_json, _in_tokens, _out_tokens, pm_cost = build_process_mapping_json(
                transcript_text=" ".join(seg.text for seg in artifact.segments),
                context_text=context_text_selected,
                template=process_template,
                language=getattr(artifact, "language", "en") or "en",
            )
            process_mapping_md = render_process_mapping_markdown(process_mapping_json)
            summary_dir = Path(session_dir) / "summaries"
            summary_dir.mkdir(parents=True, exist_ok=True)
            json_path = summary_dir / "process-mapping.json"
            json_path.write_text(json.dumps(process_mapping_json, indent=2), encoding="utf-8")
            md_path = Path(session_dir) / "process-mapping.md"
            md_path.write_text(process_mapping_md, encoding="utf-8")
            json_store.update_run_metadata(
                session_dir,
                {
                    "process-mapping.json": str(json_path),
                    "process-mapping.md": str(md_path),
                },
            )
        elif not no_summary and transcribe_fn.summary_text:
            notes_md = export_notes_markdown(
                artifact,
                summary_text=transcribe_fn.summary_text,
                source_name=video_path.name,
                model_name=artifact.model_name,
                style=transcribe_fn.used_style or "executive",
                cost_usd=transcribe_fn.cost_usd,
            )
            notes_path = Path(session_dir) / "notes.md"
            notes_path.write_text(notes_md, encoding="utf-8")

        if pdf:
            if process_mapping_md:
                md_path = Path(session_dir) / "process-mapping.md"
            elif not no_summary and transcribe_fn.summary_text:
                md_path = Path(session_dir) / "notes.md"
            else:
                md_path = transcript_path

            pdf_path = Path(pdf_output) if pdf_output else md_path.with_suffix(".pdf")
            md_text = md_path.read_text(encoding="utf-8")
            export_markdown_pdf(md_text, pdf_path, title=md_path.stem.replace("_", " ").title())

        if legacy:
            if no_summary:
                legacy_path = video_path.parent / f"{video_path.stem}_transcript.md"
                legacy_path.write_text(transcript_md, encoding="utf-8")
            else:
                if process_mapping_md:
                    legacy_path = video_path.parent / f"{video_path.stem}_process_mapping.md"
                    legacy_path.write_text(process_mapping_md, encoding="utf-8")
                else:
                    legacy_notes = (
                        Path(session_dir) / "notes.md"
                        if transcribe_fn.summary_text
                        else None
                    )
                    if legacy_notes and legacy_notes.exists():
                        legacy_path = video_path.parent / f"{video_path.stem}_notes.md"
                        legacy_path.write_text(legacy_notes.read_text(encoding="utf-8"), encoding="utf-8")
                    else:
                        legacy_path = video_path.parent / f"{video_path.stem}_transcript.md"
                        legacy_path.write_text(transcript_md, encoding="utf-8")

        if not quiet:
            click.echo(f"Session saved to: {session_dir}")

    except TranscriptionError as e:
        e.display()
        sys.exit(1)
    except Exception as e:
        click.echo(click.style("Error: ", fg="red", bold=True) + str(e), err=True)
        click.echo(
            click.style("Suggestion: ", fg="yellow")
            + "Check that FFmpeg is installed and the media file is valid.",
            err=True,
        )
        sys.exit(1)


def _live_status(entry: dict) -> None:
    snippet = entry.get("snippet") or entry.get("transcript", "").strip()
    click.echo(
        click.style(
            f"[Live] chunk {entry['chunk_idx']} "
            f"@ {entry['start_seconds']:.1f}s: {snippet}",
            fg="cyan",
        )
    )


@main.command()
@click.option("--chunk-seconds", type=float, default=2.0, help="Chunk duration in seconds")
@click.option("--sample-rate", type=int, default=48000, help="Sample rate for recording")
@click.option("--max-seconds", type=float, default=None, help="Stop after N seconds (optional)")
@click.option("--auto-devices", is_flag=True, help="Auto-select default mic + loopback devices")
@click.option("--audio-file", type=click.Path(exists=True), help="Ingest an existing media file instead of live capture")
@click.pass_context
def record(ctx, chunk_seconds, sample_rate, max_seconds, auto_devices, audio_file):
    """Record live audio or ingest a media file through the transcription workflow."""
    try:
        if audio_file:
            click.echo("Ingesting media file instead of live recording...")
            ctx.invoke(file, video_file=audio_file)
            return

        if auto_devices:
            devices = select_default_devices()
            click.echo(
                f"Auto-selected mic: {devices['mic']['label']} | loopback: {devices['loopback']['label']}"
            )
        else:
            devices = prompt_for_devices(output_fn=click.echo)
        session, session_dir, metadata = run_live_recording(
            mic_device=devices["mic"],
            loopback_device=devices["loopback"],
            sample_rate=sample_rate,
            chunk_duration=chunk_seconds,
            max_seconds=max_seconds,
            status_callback=_live_status,
        )
        click.echo(f"Recording session saved to: {session_dir}")
        click.echo(f"Session ID: {session.session_id}")
        click.echo(f"Chunks captured: {len(metadata.get('chunk_paths', []))}")
        if metadata.get("live_transcript_md"):
            click.echo(f"Live transcript: {metadata['live_transcript_md']}")
    except Exception as e:
        click.echo(click.style("Error: ", fg="red", bold=True) + str(e), err=True)
        sys.exit(1)


@main.command()
@click.argument("session_id")
@click.option(
    "--export",
    "export_type",
    type=click.Choice(["transcript", "pdf"], case_sensitive=False),
    default="transcript",
)
@click.option("--output", type=click.Path(), default=None)
def session(session_id, export_type, output):
    sdir = json_store.find_session_dir(session_id)
    if not sdir:
        click.echo(f"Session not found: {session_id}", err=True)
        sys.exit(1)
    if export_type.lower() == "pdf":
        sdir_path = Path(sdir)
        md_path = sdir_path / "process-mapping.md"
        if not md_path.exists():
            md_path = sdir_path / "notes.md"
        if not md_path.exists():
            md_path = sdir_path / "transcript.md"
        if not md_path.exists():
            click.echo("No markdown output found for session.", err=True)
            sys.exit(1)
        out_path = Path(output) if output else md_path.with_suffix(".pdf")
        md_text = md_path.read_text(encoding="utf-8")
        export_markdown_pdf(md_text, out_path, title=md_path.stem.replace("_", " ").title())
        click.echo(f"Exported to: {out_path}")
        return

    artifact = json_store.load_transcript(sdir)
    out_path = Path(output) if output else (Path(sdir) / "transcript.md")
    md = export_transcript_markdown(artifact, Path(artifact.source_path).name)
    out_path.write_text(md, encoding="utf-8")
    click.echo(f"Exported to: {out_path}")


@main.command()
def check():
    """Check FFmpeg and OpenAI API key availability."""
    try:
        validate_environment()
        click.echo("FFmpeg: OK")
    except Exception as e:
        click.echo(click.style("FFmpeg: ", fg="red", bold=True) + str(e), err=True)
        raise SystemExit(1)

    try:
        check_api_key()
        click.echo("OPENAI_API_KEY: OK")
    except APIKeyMissingError:
        click.echo(
            click.style("OPENAI_API_KEY: ", fg="red", bold=True)
            + "Missing. Set environment variable or add to a .env file.",
            err=True,
        )
        raise SystemExit(1)


if __name__ == "__main__":
    main()
