"""CLI interface for video transcription tool.

Command: transcribe VIDEO_FILE [-q] [--force]

Integrates validation, audio extraction, Whisper transcription, and markdown
formatting into a single user-friendly command.
"""

import click
import sys
import tempfile
from pathlib import Path

from transcribe.validators import validate_environment, validate_video_file
from transcribe.extractor import extract_audio
from transcribe.transcriber import Transcriber
from transcribe.formatter import format_transcript
from transcribe.chunker import chunk_audio, cleanup_chunks
from transcribe.parallel import transcribe_chunks_parallel
from transcribe.progress import ProgressDisplay


@click.command()
@click.argument('video_file', type=click.Path(exists=True))
@click.option('-q', '--quiet', is_flag=True, help='Suppress progress output')
@click.option('--force', is_flag=True, help='Overwrite existing output without asking')
def main(video_file, quiet, force):
    """
    Transcribe a video file to markdown with timestamps.

    Extracts audio from VIDEO_FILE, transcribes it using faster-whisper,
    and saves the transcript as a markdown file in the same directory.

    Output file naming: video.mp4 -> video_transcript.md

    Examples:

        transcribe meeting.mp4

        transcribe presentation.mkv --quiet

        transcribe video.mp4 --force
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

        # Construct output path
        output_path = video_path.parent / f"{video_path.stem}_transcript.md"

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

            # Stage 5: Format and save
            transcript_text = format_transcript(
                segments,
                info,
                video_path.name,
                confidence_pct=confidence_pct,
                model_name=transcriber.model_size
            )

            # Write output
            output_path.write_text(transcript_text, encoding='utf-8')

            # Warn if low confidence
            if confidence_pct and confidence_pct < 50:
                progress.warn(f"Low confidence detected ({confidence_pct:.0f}%)")

            # Success message
            if not quiet:
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
