"""CLI interface for video transcription tool.

Command: transcribe VIDEO_FILE [-q] [--force] [--style STYLE] [--no-summary]

Integrates validation, audio extraction, Whisper transcription, summarization,
and markdown formatting into a single user-friendly command.
"""

import click
import sys
import tempfile
from pathlib import Path

from transcribe.validators import validate_environment, validate_video_file
from transcribe.extractor import extract_audio
from transcribe.transcriber import Transcriber
from transcribe.formatter import format_transcript, format_notes
from transcribe.chunker import chunk_audio, cleanup_chunks
from transcribe.parallel import transcribe_chunks_parallel
from transcribe.progress import ProgressDisplay
from transcribe.summarizer import check_api_key, summarize_with_quality_gate
from transcribe.prompts import detect_summary_style


@click.command()
@click.argument('video_file', type=click.Path(exists=True))
@click.option('-q', '--quiet', is_flag=True, help='Suppress progress output')
@click.option('--force', is_flag=True, help='Overwrite existing output without asking')
@click.option('--no-summary', is_flag=True, help='Skip summarization, produce transcript only')
@click.option('--style', type=click.Choice(['executive', 'action-items', 'detailed'], case_sensitive=False), default=None, help='Summary style (default: auto-detect)')
def main(video_file, quiet, force, no_summary, style):
    """
    Transcribe and summarize a video file.

    Extracts audio from VIDEO_FILE, transcribes it using faster-whisper,
    generates AI summary, and saves as markdown notes in the same directory.

    Output file naming:
    - With summary: video.mp4 -> video_notes.md
    - Without summary: video.mp4 -> video_transcript.md

    Examples:

        transcribe meeting.mp4                          # Transcribe + summarize

        transcribe meeting.mp4 --style action-items     # Force action-items style

        transcribe meeting.mp4 --no-summary             # Transcript only

        transcribe meeting.mp4 -q                       # Quiet mode
    """
    try:
        # Convert to Path object
        video_path = Path(video_file)

        # Early validation (fail fast pattern)
        try:
            validate_environment()
        except RuntimeError as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)

        try:
            validate_video_file(video_path)
        except (FileNotFoundError, ValueError) as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)

        # Check API key if summarization enabled (fail fast before transcription)
        if not no_summary:
            try:
                check_api_key()
            except RuntimeError as e:
                click.echo(f"Error: {e}", err=True)
                sys.exit(1)

        # Construct output path based on whether summary will be included
        if no_summary:
            output_path = video_path.parent / f"{video_path.stem}_transcript.md"
        else:
            output_path = video_path.parent / f"{video_path.stem}_notes.md"

        # Check if output file exists
        if output_path.exists() and not force:
            if not click.confirm(f"{output_path.name} exists. Overwrite?"):
                click.echo("Cancelled.")
                return

        # Process video using complete Phase 2 pipeline with cleanup
        temp_audio = None
        chunk_temp_dir = None
        try:
            # Create temp audio file
            temp_file_handle = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
            temp_audio = Path(temp_file_handle.name)
            temp_file_handle.close()

            # Create progress display
            progress = ProgressDisplay(quiet=quiet)

            # Stage 1: Extract audio with progress
            progress.start_extraction()
            extract_audio(video_path, temp_audio)
            progress.finish_extraction()

            # Stage 2: Language detection
            transcriber = Transcriber(model_size="small")
            language, lang_prob = transcriber.detect_language(temp_audio)
            if not quiet and language:
                click.echo(f"Detected language: {language} ({lang_prob:.0%})")

            # Stage 3: Chunking decision
            chunks = chunk_audio(temp_audio)

            # Extract chunk directory for cleanup (if chunks were created)
            if len(chunks) > 1:
                chunk_temp_dir = chunks[0][1].parent

            # Stage 4: Transcription
            confidence_pct = None

            if len(chunks) == 1:
                # Stage 4a: Simple path for short videos (single chunk)
                progress.start_transcription(total_chunks=1)
                segments, info, confidence_pct = transcriber.transcribe_with_quality(
                    temp_audio,
                    language=language
                )
                progress.finish_transcription()

            else:
                # Stage 4b: Parallel path for long videos (multiple chunks)
                progress.start_transcription(total_chunks=len(chunks))
                segments, info_dict, all_segment_data = transcribe_chunks_parallel(
                    chunks,
                    model_size="small",
                    language=language,
                    on_chunk_complete=lambda cid: progress.update_transcription(cid)
                )
                progress.finish_transcription()

                # Validate quality on merged segments
                is_acceptable, confidence_pct, avg_logprob = transcriber.validate_quality(segments)

                # If low confidence, warn and re-run with medium model
                if not is_acceptable:
                    if not quiet:
                        click.echo(f"Low confidence ({confidence_pct:.0f}%), retrying with medium model...")

                    progress.start_transcription(total_chunks=len(chunks))
                    segments, info_dict, all_segment_data = transcribe_chunks_parallel(
                        chunks,
                        model_size="medium",
                        language=language,
                        on_chunk_complete=lambda cid: progress.update_transcription(cid)
                    )
                    progress.finish_transcription()

                    # Re-validate
                    is_acceptable, confidence_pct, avg_logprob = transcriber.validate_quality(segments)

                # Convert info_dict to info-like object for formatter compatibility
                class InfoObject:
                    def __init__(self, d):
                        self.language = d['language']
                        self.duration = d['duration']
                        self.language_probability = d['language_probability']

                info = InfoObject(info_dict)

            # Build transcript text for word count and summarization
            all_text = " ".join(seg.text for seg in segments)

            # Stage 5: Summarize (unless --no-summary)
            if not no_summary:
                # Detect language from info object
                summary_language = getattr(info, 'language', 'en') or 'en'

                # Auto-detect or use specified style
                if style is None:
                    detected_style = detect_summary_style(all_text)
                    if not quiet:
                        click.echo(f"Auto-selected summary style: {detected_style}")
                    style = detected_style

                if not quiet:
                    click.echo("Generating summary...")

                try:
                    # Summarize with quality gate
                    summary_text, cost_usd, attempted = summarize_with_quality_gate(
                        transcript_text=all_text,
                        confidence_pct=confidence_pct or 100.0,
                        style=style,
                        language=summary_language,
                        quiet=quiet
                    )

                    if attempted and summary_text:
                        # Format as notes (summary + transcript)
                        output_text = format_notes(
                            summary_text=summary_text,
                            segments=segments,
                            info=info,
                            video_filename=video_path.name,
                            confidence_pct=confidence_pct,
                            model_name=transcriber.model_size,
                            style=style,
                            cost_usd=cost_usd
                        )
                        output_path.write_text(output_text, encoding='utf-8')

                        if not quiet:
                            click.echo(f"Summary cost: ~${cost_usd:.2f}")
                    else:
                        # Summarization skipped or failed — save transcript only
                        # Change output path back to _transcript.md
                        output_path = video_path.parent / f"{video_path.stem}_transcript.md"
                        transcript_text = format_transcript(
                            segments, info, video_path.name,
                            confidence_pct=confidence_pct,
                            model_name=transcriber.model_size
                        )
                        output_path.write_text(transcript_text, encoding='utf-8')

                except Exception as e:
                    click.echo(f"Summarization failed: {e}", err=True)
                    click.echo("Saving transcript without summary.", err=True)
                    # Fall back to transcript-only output
                    output_path = video_path.parent / f"{video_path.stem}_transcript.md"
                    transcript_text = format_transcript(
                        segments, info, video_path.name,
                        confidence_pct=confidence_pct,
                        model_name=transcriber.model_size
                    )
                    output_path.write_text(transcript_text, encoding='utf-8')

            else:
                # --no-summary: save transcript only
                transcript_text = format_transcript(
                    segments, info, video_path.name,
                    confidence_pct=confidence_pct,
                    model_name=transcriber.model_size
                )
                output_path.write_text(transcript_text, encoding='utf-8')

            # Warn if low confidence
            if confidence_pct and confidence_pct < 50:
                progress.warn(f"Low confidence detected ({confidence_pct:.0f}%)")

            # Success message
            if not quiet:
                # Determine if summary was included in output
                has_summary = not no_summary and output_path.name.endswith('_notes.md')
                if has_summary:
                    click.echo(f"Notes saved to: {output_path}")
                else:
                    click.echo(f"Transcript saved to: {output_path}")

        finally:
            # Cleanup temp audio file
            if temp_audio and temp_audio.exists():
                temp_audio.unlink()

            # Cleanup chunk directory
            if chunk_temp_dir:
                cleanup_chunks(chunk_temp_dir)

    except RuntimeError as e:
        # Known runtime errors (FFmpeg failures, no audio, etc.)
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except ValueError as e:
        # Known value errors (no speech detected, invalid input)
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except FileNotFoundError as e:
        # File not found during processing
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        # Unexpected errors
        click.echo(
            f"Unexpected error: {e}\n"
            "Please check that FFmpeg is installed and the video file is valid.",
            err=True
        )
        sys.exit(1)


if __name__ == '__main__':
    main()
