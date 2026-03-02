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

        # Process video using two-stage pipeline with cleanup
        temp_audio = None
        try:
            # Create temp audio file
            temp_file_handle = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
            temp_audio = Path(temp_file_handle.name)
            temp_file_handle.close()

            # Stage 1: Extract audio
            if not quiet:
                click.echo("Extracting audio...")
            extract_audio(video_path, temp_audio)

            # Stage 2: Transcribe
            if not quiet:
                click.echo("Transcribing...")
            transcriber = Transcriber()
            segments, info = transcriber.transcribe(temp_audio)

            # Format transcript
            transcript_text = format_transcript(segments, info, video_path.name)

            # Write output
            output_path.write_text(transcript_text, encoding='utf-8')

            # Success message
            click.echo(f"Transcript saved to: {output_path}")

        finally:
            # Cleanup temp audio file
            if temp_audio and temp_audio.exists():
                temp_audio.unlink()

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
