# Phase 1: Foundation Pipeline - Research

**Researched:** 2026-03-02
**Domain:** Video-to-text transcription pipeline (audio extraction + speech-to-text)
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Output format:**
- Markdown (.md) output format
- Full metadata header: file name, date, duration, language detected, model used
- Output saved in same folder as source video (video.mp4 → video_transcript.md)
- If output file exists: warn and prompt user; --force flag to overwrite without asking

**CLI invocation:**
- Command name: `transcribe`
- Video file passed as positional argument: `transcribe video.mp4`
- Progress shown by default (extracting… transcribing… done); -q flag for quiet mode
- Check for FFmpeg on startup, fail early with clear install instructions if missing

**Video format handling:**
- Support all 4 formats: MP4, MKV, WebM, AVI
- No audio track: warn and skip (don't crash)
- Corrupted/unreadable file: clear error message ("Could not read video.mp4 — file may be corrupted")
- Validate FFmpeg availability before any processing

**Transcript style:**
- Timestamped blocks: [00:01:23] text... [00:02:45] next block...
- Timestamps at natural speech pauses (follow conversation flow)
- Polished output: proper punctuation and capitalization
- Output language matches audio language (Spanish audio → Spanish text, English → English)

### Claude's Discretion

- Installation/packaging approach (pip, pipx, uv, or local script)
- Exact progress message format and styling
- Whisper model size selection for Phase 1 (base/small/medium)
- Temp file management strategy
- Exact markdown template structure

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| AUDIO-01 | User can process MP4, MKV, WebM, and AVI video files | ffmpeg-python handles all formats; FFmpeg supports all 4 natively |
| AUDIO-02 | Tool automatically names output file based on source video (video.mp4 → video_transcript.md) | pathlib.Path provides .stem and .parent for path manipulation |
| TRANS-01 | User can transcribe speech from video to text using faster-whisper | faster-whisper 1.2.1 provides WhisperModel with segment-level transcription |
| CLI-01 | User runs a single command with a video file path to get transcript + summary | Click framework provides @click.command with positional arguments via @click.argument |

</phase_requirements>

## Summary

Phase 1 establishes the core video-to-text pipeline using **faster-whisper** (reimplementation of OpenAI Whisper using CTranslate2, up to 4x faster) for transcription and **ffmpeg-python** for audio extraction. The stack is mature and well-documented.

**faster-whisper 1.2.1** (released Oct 2025) bundles FFmpeg via PyAV, eliminating system FFmpeg dependency for transcription. However, **audio extraction still requires system FFmpeg installation** — this is a critical distinction. The tool must check for FFmpeg availability at startup using `shutil.which('ffmpeg')` before any processing.

**Click** is the recommended CLI framework (38.7% adoption in Python ecosystem as of 2025), providing decorator-based command definition, automatic help generation, and built-in progress bars via `click.progressbar()`. It's more maintainable than argparse for CLIs with future expansion potential.

**Primary recommendation:** Use faster-whisper with the **small** model for Phase 1 (balance of speed and accuracy, ~461MB download), ffmpeg-python for audio extraction to WAV format, Click for CLI, and pathlib for cross-platform file handling.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| faster-whisper | 1.2.1+ | Speech-to-text transcription | 4x faster than openai-whisper, same accuracy, lower memory. Industry standard for production Whisper usage. |
| ffmpeg-python | 0.2.0+ | Audio extraction from video | Pythonic wrapper for FFmpeg, cleaner than subprocess calls. Most popular FFmpeg binding (2.4k GitHub stars). |
| click | 8.1.0+ | CLI framework | 38.7% adoption in Python ecosystem. Decorator-based, extensible, built-in progress bars. Better than argparse for multi-command CLIs. |
| pathlib | stdlib | File path handling | Cross-platform path manipulation. Standard library, no dependencies. |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| tempfile | stdlib | Temporary audio file management | For extracted audio files before transcription. Use NamedTemporaryFile with delete=False for debugging. |
| shutil | stdlib | FFmpeg availability check | shutil.which('ffmpeg') to detect system FFmpeg before processing. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| faster-whisper | openai-whisper | Original implementation: 4x slower, higher memory usage. Only use if you need exact OpenAI parity. |
| ffmpeg-python | pydub | Higher-level audio manipulation library, but adds abstraction layer. Use if you need audio editing (not needed for Phase 1). |
| Click | argparse | Standard library (no deps), but verbose for complex CLIs. Use only if external deps are forbidden. |
| Click | typer | Modern with type hints, but adds dependency. Consider for Phase 2+ if type safety is priority. |

**Installation:**
```bash
pip install faster-whisper ffmpeg-python click
```

**System dependency:**
```bash
# User must install FFmpeg separately
# macOS: brew install ffmpeg
# Ubuntu: apt-get install ffmpeg
# Windows: Download from ffmpeg.org, add to PATH
```

## Architecture Patterns

### Recommended Project Structure

```
transcribe-tool/
├── transcribe/
│   ├── __init__.py
│   ├── cli.py              # Click command definitions
│   ├── extractor.py        # Audio extraction logic
│   ├── transcriber.py      # Whisper transcription logic
│   ├── formatter.py        # Markdown output generation
│   └── validators.py       # FFmpeg check, file validation
├── pyproject.toml          # Modern packaging (replaces setup.py)
├── README.md
└── tests/
```

### Pattern 1: Lazy Model Loading

**What:** Initialize WhisperModel only when transcription is needed, not at CLI startup.

**When to use:** Always — model download (461MB for small) and GPU initialization add 2-10 seconds to startup.

**Example:**
```python
# Source: faster-whisper official docs
from faster_whisper import WhisperModel

class Transcriber:
    def __init__(self, model_size="small"):
        self.model_size = model_size
        self._model = None

    @property
    def model(self):
        if self._model is None:
            self._model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
        return self._model

    def transcribe(self, audio_path):
        segments, info = self.model.transcribe(audio_path, beam_size=5)
        return segments, info
```

### Pattern 2: Early Validation

**What:** Check all prerequisites (FFmpeg, file exists, file readable) before any processing.

**When to use:** Always — fail fast with clear errors instead of failing mid-pipeline.

**Example:**
```python
# Source: Python best practices + shutil docs
import shutil
from pathlib import Path

def validate_environment():
    """Check FFmpeg availability before processing."""
    if shutil.which('ffmpeg') is None:
        raise RuntimeError(
            "FFmpeg not found. Install it:\n"
            "  macOS: brew install ffmpeg\n"
            "  Ubuntu: apt-get install ffmpeg\n"
            "  Windows: Download from ffmpeg.org and add to PATH"
        )

def validate_video_file(video_path: Path):
    """Validate video file exists and is readable."""
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    if not video_path.is_file():
        raise ValueError(f"Path is not a file: {video_path}")

    # Check extension
    valid_extensions = {'.mp4', '.mkv', '.webm', '.avi'}
    if video_path.suffix.lower() not in valid_extensions:
        raise ValueError(
            f"Unsupported format: {video_path.suffix}\n"
            f"Supported: {', '.join(valid_extensions)}"
        )
```

### Pattern 3: Two-Stage Pipeline with Cleanup

**What:** Extract audio to temp file, transcribe, clean up temp file in finally block.

**When to use:** Always — ensures temp files are cleaned even on errors.

**Example:**
```python
# Source: tempfile stdlib docs + Python best practices
import tempfile
from pathlib import Path

def process_video(video_path: Path):
    """Extract audio, transcribe, clean up."""
    temp_audio = None
    try:
        # Extract audio to temp WAV file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            temp_audio = Path(f.name)

        extract_audio(video_path, temp_audio)

        # Transcribe
        segments, info = transcribe_audio(temp_audio)

        return segments, info

    finally:
        # Always clean up temp file
        if temp_audio and temp_audio.exists():
            temp_audio.unlink()
```

### Pattern 4: Segment Iterator to Text Blocks

**What:** faster-whisper returns generators; convert to timestamped markdown blocks.

**When to use:** Always — segments are generators (lazy evaluation), must iterate to trigger transcription.

**Example:**
```python
# Source: faster-whisper GitHub examples
def format_transcript(segments, info):
    """Convert segments generator to timestamped markdown."""
    lines = []
    lines.append(f"**Language:** {info.language} (confidence: {info.language_probability:.2f})")
    lines.append("")

    for segment in segments:
        timestamp = format_timestamp(segment.start)
        lines.append(f"[{timestamp}] {segment.text.strip()}")

    return "\n".join(lines)

def format_timestamp(seconds: float) -> str:
    """Convert seconds to [HH:MM:SS] format."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"
```

### Anti-Patterns to Avoid

- **Using subprocess.run(['ffmpeg', ...]) directly:** Use ffmpeg-python library for cleaner code and automatic argument escaping.
- **Loading large/medium models for Phase 1:** Unnecessary 1.5GB+ downloads and slower processing for 5-10 min videos. Use small model.
- **Synchronous progress without updates:** Click's progressbar expects iterable or manual update() calls. Don't use with non-iterable long operations without manual updates.
- **Hardcoded output paths:** Use pathlib to construct output path from input video path (video.mp4 → video_transcript.md in same directory).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Audio extraction from video | Custom FFmpeg subprocess wrapper | ffmpeg-python library | Handles argument escaping, error messages, stream filtering. Edge cases: corrupted files, missing audio tracks. |
| Speech-to-text transcription | Custom ML model or API calls | faster-whisper library | Handles model downloads, GPU/CPU selection, language detection, timestamp generation. Reinventing this is months of work. |
| Temporary file cleanup | Manual file deletion in try/except | tempfile.NamedTemporaryFile with context manager | Handles race conditions, permissions, OS differences. Cleanup guaranteed even on exceptions. |
| CLI argument parsing | Manual sys.argv parsing | Click framework | Handles help text, type validation, flag parsing, subcommands. Manual parsing is error-prone. |
| File path manipulation | String concatenation for paths | pathlib.Path | Handles Windows vs Unix separators, relative paths, parent directories. String manipulation breaks across platforms. |

**Key insight:** Video transcription has subtle complexity (audio codec variations, silence detection, memory management, language detection). Use battle-tested libraries instead of reimplementing.

## Common Pitfalls

### Pitfall 1: Assuming PyAV Replaces System FFmpeg

**What goes wrong:** faster-whisper bundles PyAV (which includes FFmpeg libraries) for **audio decoding during transcription**, but this does NOT provide the `ffmpeg` command-line tool. Audio extraction still requires system FFmpeg installation.

**Why it happens:** Documentation says "FFmpeg does not need to be installed" but this refers only to the transcription step, not the full pipeline.

**How to avoid:** Always check for system FFmpeg at startup using `shutil.which('ffmpeg')` and provide clear install instructions if missing.

**Warning signs:** Users report "ffmpeg command not found" errors during audio extraction step.

**Sources:** [faster-whisper GitHub](https://github.com/SYSTRAN/faster-whisper), [PyPI page](https://pypi.org/project/faster-whisper/)

### Pitfall 2: No-Speech Audio Causes ValueError

**What goes wrong:** faster-whisper raises `ValueError: max() arg is an empty sequence` when processing audio with no speech, especially with VAD filtering enabled.

**Why it happens:** Voice Activity Detection (VAD) filters out all segments, leaving empty sequence for language detection.

**How to avoid:** Wrap transcription in try/except for ValueError, check segment count, provide clear error: "No speech detected in video."

**Warning signs:** Error message "max() arg is an empty sequence" when processing videos with long silence or background noise only.

**Sources:** [faster-whisper Issue #1208](https://github.com/SYSTRAN/faster-whisper/issues/1208)

### Pitfall 3: Different Beam Size Defaults

**What goes wrong:** Results differ from openai-whisper examples. openai-whisper uses beam_size=1 by default, faster-whisper uses beam_size=5.

**Why it happens:** faster-whisper prioritizes accuracy over speed by default.

**How to avoid:** Explicitly set `beam_size=5` in transcribe() call (or adjust based on speed/accuracy preference). Document choice in code.

**Warning signs:** Transcripts differ from openai-whisper documentation examples.

**Sources:** [faster-whisper Discussion #458](https://github.com/SYSTRAN/faster-whisper/discussions/458)

### Pitfall 4: Segments Are Generators, Not Lists

**What goes wrong:** Code iterates over segments multiple times, but second iteration is empty. Or code tries `len(segments)` and gets error.

**Why it happens:** faster-whisper returns segments as generator for memory efficiency. Generators are consumed on first iteration.

**How to avoid:** Convert to list immediately if you need multiple iterations: `segments = list(model.transcribe(...)[0])`. Or iterate once and build output.

**Warning signs:** Transcript appears empty on second processing attempt, or `TypeError: object of type 'generator' has no len()`.

**Sources:** [faster-whisper GitHub transcribe.py](https://github.com/SYSTRAN/faster-whisper/blob/master/faster_whisper/transcribe.py)

### Pitfall 5: GPU Memory Errors Without Helpful Messages

**What goes wrong:** Transcription fails with CUDA out of memory error, or slow performance without explanation.

**Why it happens:** large models require 8GB+ VRAM, medium requires 4GB+. Users with 4GB cards hit limits.

**How to avoid:** For Phase 1 (5-10 min videos), use small model (461MB, ~2GB VRAM) on CPU with `compute_type="int8"`. Document GPU requirements if users want larger models.

**Warning signs:** "CUDA out of memory" errors, or unexpectedly slow transcription.

**Sources:** [VideoHelp Forum discussion](https://forum.videohelp.com/threads/410865-How-I-use-whisper-faster-on-my-machine)

### Pitfall 6: File Overwrite Without Warning

**What goes wrong:** Tool silently overwrites existing transcript, losing user edits or previous results.

**Why it happens:** No check for existing output file before writing.

**How to avoid:** Check if output file exists. If yes: prompt user "File exists. Overwrite? (y/n)" unless --force flag is set.

**Warning signs:** Users complain about lost transcripts.

**Sources:** User requirement from CONTEXT.md

### Pitfall 7: Cryptic FFmpeg Errors

**What goes wrong:** ffmpeg-python raises subprocess errors with full ffmpeg command output (hundreds of lines), hiding actual problem.

**Why it happens:** FFmpeg prints verbose diagnostic info to stderr even on success.

**How to avoid:** Catch `ffmpeg.Error` exceptions, parse stderr for specific error patterns (e.g., "Invalid data found", "No such file"), provide user-friendly message.

**Warning signs:** Error messages like "Exited with code 1" without explanation of what failed.

**Sources:** [ffmpeg-python GitHub](https://github.com/kkroening/ffmpeg-python)

## Code Examples

Verified patterns from official sources:

### Audio Extraction with Error Handling

```python
# Source: ffmpeg-python GitHub + best practices
import ffmpeg
from pathlib import Path

def extract_audio(video_path: Path, output_path: Path):
    """Extract audio from video to WAV format."""
    try:
        (
            ffmpeg
            .input(str(video_path))
            .output(str(output_path), acodec='pcm_s16le', ac=1, ar='16000')
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
    except ffmpeg.Error as e:
        stderr = e.stderr.decode('utf8')

        # Parse common errors
        if 'Invalid data found' in stderr or 'could not find codec' in stderr:
            raise RuntimeError(f"Could not read {video_path.name} — file may be corrupted")
        elif 'Output file is empty' in stderr or 'does not contain any stream' in stderr:
            raise RuntimeError(f"No audio track found in {video_path.name}")
        else:
            # Unknown error, show filtered output
            raise RuntimeError(f"FFmpeg error processing {video_path.name}") from e
```

### Basic Transcription with Language Detection

```python
# Source: faster-whisper official README
from faster_whisper import WhisperModel

def transcribe_audio(audio_path: Path, model_size="small"):
    """Transcribe audio file to text with timestamps."""
    model = WhisperModel(model_size, device="cpu", compute_type="int8")

    segments, info = model.transcribe(
        str(audio_path),
        beam_size=5,
        word_timestamps=False  # Segment-level timestamps only for Phase 1
    )

    # Convert generator to list to trigger transcription
    segments_list = list(segments)

    if not segments_list:
        raise ValueError(f"No speech detected in audio")

    return segments_list, info
```

### Click CLI with Progress Bar

```python
# Source: Click official docs
import click
from pathlib import Path

@click.command()
@click.argument('video_file', type=click.Path(exists=True))
@click.option('-q', '--quiet', is_flag=True, help='Suppress progress output')
@click.option('--force', is_flag=True, help='Overwrite existing output without asking')
def transcribe(video_file, quiet, force):
    """Transcribe VIDEO_FILE to markdown transcript."""
    video_path = Path(video_file)

    # Validate environment
    validate_environment()
    validate_video_file(video_path)

    # Check output file
    output_path = video_path.parent / f"{video_path.stem}_transcript.md"
    if output_path.exists() and not force:
        if not click.confirm(f"{output_path.name} exists. Overwrite?"):
            click.echo("Cancelled.")
            return

    # Process with progress
    if not quiet:
        with click.progressbar(length=100, label='Processing video') as bar:
            # Extract audio (50% of progress)
            extract_audio(video_path, temp_audio)
            bar.update(50)

            # Transcribe (remaining 50%)
            segments, info = transcribe_audio(temp_audio)
            bar.update(50)
    else:
        extract_audio(video_path, temp_audio)
        segments, info = transcribe_audio(temp_audio)

    # Write output
    write_transcript(output_path, segments, info, video_path)
    click.echo(f"Transcript saved to: {output_path}")
```

### Markdown Transcript Template

```python
# Source: Best practices for structured output
from datetime import datetime
from pathlib import Path

def write_transcript(output_path: Path, segments, info, video_path: Path):
    """Write transcript to markdown file with metadata header."""
    lines = []

    # Metadata header
    lines.append("# Transcript\n")
    lines.append(f"**Source:** {video_path.name}")
    lines.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"**Duration:** {format_duration(info.duration)}")
    lines.append(f"**Language:** {info.language} (confidence: {info.language_probability:.2%})")
    lines.append(f"**Model:** faster-whisper (small)")
    lines.append("\n---\n")

    # Timestamped transcript
    for segment in segments:
        timestamp = format_timestamp(segment.start)
        text = segment.text.strip()
        lines.append(f"**[{timestamp}]** {text}\n")

    output_path.write_text("\n".join(lines), encoding='utf-8')

def format_timestamp(seconds: float) -> str:
    """Convert seconds to HH:MM:SS format."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"

def format_duration(seconds: float) -> str:
    """Format duration for metadata header."""
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}m {secs}s"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| openai-whisper | faster-whisper with CTranslate2 | 2023 | 4x faster transcription, lower memory usage. Production deployments should use faster-whisper. |
| setup.py for packaging | pyproject.toml | 2020-2022 | Modern standard (PEP 518, 621). pip install -e works on folder with just pyproject.toml. |
| argparse for CLIs | Click or Typer | 2014 (Click), 2020 (Typer) | Click has 38.7% adoption. Better composability, less boilerplate. |
| os.path | pathlib.Path | Python 3.4 (2014) | Cross-platform by default, object-oriented, cleaner code. |
| subprocess.run for FFmpeg | ffmpeg-python library | 2018+ | Declarative API, automatic escaping, better error handling. |

**Deprecated/outdated:**
- **setup.py alone**: Still works but pyproject.toml is now standard. Can keep setup.py for backwards compatibility but define metadata in pyproject.toml.
- **openai-whisper for production**: Original implementation is reference, but faster-whisper is better for user-facing tools (speed matters).
- **Whisper large models for short videos**: Overkill for 5-10 min videos. large-v3 is 1.5GB+ download, requires 8GB+ VRAM. Use small (461MB) for Phase 1.

## Open Questions

1. **Model size for Phase 1: base vs small?**
   - What we know: base (141MB, 74M params), small (461MB, 244M params). Small has better accuracy, base is faster.
   - What's unclear: User's priority — speed or accuracy for 5-10 min videos.
   - Recommendation: Default to **small** (good balance), allow override via env var or config for advanced users. Document in README that base is faster but less accurate.

2. **Progress bar granularity during transcription?**
   - What we know: Click's progressbar needs iterable or manual update() calls. faster-whisper segments are generator (iterated once).
   - What's unclear: How to show progress during transcription without consuming generator twice.
   - Recommendation: Two-stage progress: "Extracting audio... [50%]" then "Transcribing... [100%]". Or use indeterminate spinner during transcription (click.progressbar with length=None shows spinner).

3. **Should we validate video has audio track before extraction?**
   - What we know: ffmpeg-python will fail with error if no audio track. Can catch ffmpeg.Error and parse stderr.
   - What's unclear: Worth adding ffprobe check before extraction, or just handle error gracefully?
   - Recommendation: Handle error gracefully (simpler). Use ffprobe only if users report confusing errors.

4. **Device selection for Whisper: CPU only or auto-detect GPU?**
   - What we know: GPU requires CUDA 12 + cuDNN 9 setup. Small model works fine on CPU (2-3x slower than GPU but acceptable for 5-10 min videos).
   - What's unclear: User's hardware. Auto-detecting GPU adds complexity.
   - Recommendation: Default to CPU with `compute_type="int8"` for Phase 1 (simplest, works everywhere). Add GPU support in Phase 2+ if users request it.

## Sources

### Primary (HIGH confidence)

- [faster-whisper GitHub](https://github.com/SYSTRAN/faster-whisper) - Installation, model sizes, usage examples, segment generation
- [faster-whisper PyPI](https://pypi.org/project/faster-whisper/) - Version 1.2.1 (Oct 2025), dependencies, Python requirements
- [Click documentation](https://click.palletsprojects.com/en/stable/) - CLI framework patterns, progress bars, arguments
- [ffmpeg-python GitHub](https://github.com/kkroening/ffmpeg-python) - Audio extraction patterns, error handling
- [Python pathlib docs](https://docs.python.org/3/library/pathlib.html) - Path manipulation, cross-platform file handling
- [Python tempfile docs](https://docs.python.org/3/library/tempfile.html) - Temporary file management, cleanup patterns

### Secondary (MEDIUM confidence)

- [Click vs argparse comparison](https://www.pythonsnacks.com/p/click-vs-argparse-python) - 38.7% adoption statistic (2025)
- [Whisper model size comparison](https://whishper.net/reference/models/) - Accuracy vs performance tradeoffs
- [Python packaging guide](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/) - pyproject.toml best practices
- [FFmpeg with Python guide](https://www.gumlet.com/learn/ffmpeg-python/) - Audio extraction patterns
- [pathlib guide 2026](https://devtoolbox.dedyn.io/blog/python-pathlib-complete-guide) - Modern file path handling

### Tertiary (LOW confidence - marked for validation)

- [faster-whisper Issue #1208](https://github.com/SYSTRAN/faster-whisper/issues/1208) - No-speech audio ValueError (needs testing in Phase 1)
- [faster-whisper Discussion #458](https://github.com/SYSTRAN/faster-whisper/discussions/458) - Beam size difference (verify with tests)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries verified via official sources (GitHub, PyPI, docs). Versions confirmed current.
- Architecture: HIGH - Patterns sourced from official examples and Python best practices. Two-stage pipeline is proven approach.
- Pitfalls: MEDIUM-HIGH - Most pitfalls from official GitHub issues and discussions. PyAV vs system FFmpeg distinction verified in docs. No-speech ValueError needs validation.

**Research date:** 2026-03-02
**Valid until:** ~2026-06-02 (90 days — Python ecosystem stable, but faster-whisper actively developed)
