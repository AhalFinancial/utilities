"""Progress display for two-stage transcription pipeline.

Provides user feedback during audio extraction and transcription stages,
with support for quiet mode and non-TTY environments.
"""

import sys
import click
from typing import Optional
from tqdm import tqdm


class ProgressDisplay:
    """
    Two-stage progress display for transcription pipeline.

    Handles:
    - Stage 1: Audio extraction with simple done indicator
    - Stage 2: Transcription progress bar with chunk count, elapsed time, ETA
    - Quiet mode: minimal output
    - Non-TTY: graceful fallback

    Examples:
        >>> progress = ProgressDisplay(quiet=False)
        >>> progress.start_extraction()
        >>> # ... extract audio ...
        >>> progress.finish_extraction()
        >>> progress.start_transcription(total_chunks=5)
        >>> for chunk in chunks:
        ...     progress.update_transcription(chunk.id)
        >>> progress.finish_transcription()
    """

    def __init__(self, quiet: bool = False):
        """
        Initialize progress display.

        Args:
            quiet: If True, suppress all progress output except warnings
        """
        self.quiet = quiet
        self.pbar: Optional[tqdm] = None
        self.single_chunk_mode: bool = False

    def start_extraction(self):
        """
        Start audio extraction stage.

        Prints "Extracting audio... " without newline (if not quiet).
        """
        if not self.quiet:
            click.echo("Extracting audio... ", nl=False)

    def finish_extraction(self):
        """
        Finish audio extraction stage.

        Prints "[done]" to complete the extraction line (if not quiet).
        """
        if not self.quiet:
            click.echo("[done]")

    def start_transcription(self, total_chunks: int):
        """
        Start transcription stage with progress bar.

        For single chunk: prints "Transcribing..." (no progress bar)
        For multiple chunks: creates tqdm progress bar
        For quiet mode: no output
        For non-TTY: disables tqdm

        Args:
            total_chunks: Total number of chunks to process
        """
        if self.quiet:
            return

        if total_chunks == 1:
            # Single chunk: simple message, no progress bar
            click.echo("Transcribing...")
            self.single_chunk_mode = True
        else:
            # Multiple chunks: create progress bar
            self.single_chunk_mode = False

            # Check if we're in a TTY environment
            disable_tqdm = not sys.stdout.isatty()

            self.pbar = tqdm(
                total=total_chunks,
                desc="Transcribing",
                unit="chunk",
                bar_format='{desc}: {bar}| {n_fmt}/{total_fmt} chunks [{elapsed}<{remaining}]',
                disable=disable_tqdm
            )

    def update_transcription(self, chunk_id: Optional[int] = None):
        """
        Update transcription progress by one chunk.

        Args:
            chunk_id: Optional chunk identifier (for logging/debugging)
        """
        if self.pbar is not None:
            self.pbar.update(1)

    def finish_transcription(self):
        """
        Finish transcription stage.

        Closes progress bar if it exists, or prints "Done." for single chunk mode.
        """
        if self.pbar is not None:
            self.pbar.close()
            self.pbar = None
        elif self.single_chunk_mode and not self.quiet:
            click.echo("Done.")

    def warn(self, message: str):
        """
        Display warning message to stderr.

        Warnings are always shown, even in quiet mode (per user decision
        to "always save but warn" for quality issues).

        Args:
            message: Warning message to display
        """
        click.echo(f"Warning: {message}", err=True)
