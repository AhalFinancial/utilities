# Phase 2: Production Transcription - Research

**Researched:** 2026-03-02
**Domain:** Audio processing, speech recognition optimization, parallel processing
**Confidence:** HIGH

## Summary

Phase 2 upgrades the basic Phase 1 transcription pipeline to handle production workloads: videos from 5 minutes to 3+ hours. The core challenges are chunking long audio intelligently, processing chunks in parallel for speed, providing visual progress feedback, and validating transcription quality.

The research reveals a mature ecosystem with well-established patterns. faster-whisper's 30-second optimal chunk size aligns with Whisper's receptive field. pydub provides reliable silence detection for natural chunk boundaries. tqdm is the industry standard for CLI progress bars with minimal overhead (60ns/iteration). Python's concurrent.futures offers a simple high-level API for parallel chunk processing. The key pitfall is Whisper's tendency to hallucinate on non-speech audio (music, silence), which VAD filtering and confidence thresholds can mitigate.

**Primary recommendation:** Use pydub for silence-based chunking (min_silence_len=500ms, silence_thresh=-40dBFS), process chunks with ProcessPoolExecutor (workers=CPU count), display progress with tqdm, enable faster-whisper's VAD filter, and check segment confidence scores (threshold: -1.0 avg log probability) for quality validation.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Chunking strategy**
- Chunk size: Claude's discretion based on research into faster-whisper optimal chunk sizes
- Short videos (under 10 minutes): no chunking, process as single piece
- Long videos: split with overlap between chunks, then deduplicate overlapping text
- Process chunks in parallel for speed (user accepts higher RAM usage)

**Progress feedback**
- Visual progress bar with percentage: [████░░░░] 45%
- Show: time elapsed, ETA/time remaining, current chunk indicator
- Two separate stages: "Extracting audio... [done]" then "Transcribing... [████░░] 60%"
- Quiet mode (-q): minimal text output only ("Extracting... Transcribing... Done.") — no progress bar

**Timestamp granularity**
- Timestamps at natural pauses/topic changes only — fewer but more meaningful
- Adaptive format: [MM:SS] for videos under 1 hour, [HH:MM:SS] for longer
- Merge speech segments into flowing paragraphs under each timestamp
- Add word count and estimated reading time to metadata header

**Quality validation**
- Warn on low confidence but always save the transcript ("Low confidence detected" warning)
- Average confidence score in metadata header (e.g., "Confidence: 87%")
- Mark non-speech segments inline: [music], [background noise]
- Auto-upgrade model: if confidence is low with 'small' model, retry with 'medium' automatically

### Claude's Discretion

- Exact chunk size and overlap duration
- Silence detection threshold parameters
- Confidence score calculation method
- Progress bar library/implementation choice
- Deduplication algorithm for overlapping chunk text
- Parallel processing thread/process count

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| TRANS-02 | Tool auto-detects Spanish and English audio | faster-whisper supports automatic language detection from first 30s of audio; can detect from pool of 94 languages including Spanish/English |
| TRANS-03 | Transcript includes timestamps for navigation back to specific moments | Phase 1 already implements timestamps; Phase 2 adds adaptive formatting (MM:SS vs HH:MM:SS) and timestamp merging based on natural pauses |
| TRANS-04 | Tool uses smart chunking with silence detection for videos longer than 10 minutes | pydub split_on_silence provides silence-based chunking; combine with 30s optimal chunk size from faster-whisper research |
| CLI-02 | Tool displays progress bar during long video processing | tqdm provides industry-standard progress bars with ETA/elapsed time; 60ns overhead, minimal performance impact |

</phase_requirements>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| faster-whisper | >=1.2.1 | Speech transcription | 4x faster than OpenAI Whisper, same accuracy, less memory; industry standard for production Whisper deployments |
| tqdm | >=4.67.0 | Progress bars | Most popular Python progress bar library (60ns/iteration overhead); automatic ETA calculation, minimal code |
| pydub | >=0.25.1 | Silence detection & audio splitting | Established library for audio manipulation; provides split_on_silence for natural chunk boundaries |
| concurrent.futures | stdlib | Parallel processing | Python standard library; high-level API for ProcessPoolExecutor, simpler than raw multiprocessing |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| soundfile | >=0.12.1 | WAV format handling | For in-memory audio buffer conversions; optional but useful for chunk processing |
| difflib | stdlib | Text deduplication | For removing overlapping text between chunks; SequenceMatcher provides similarity ratios |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| tqdm | rich | Rich has beautiful output but higher overhead; tqdm's simplicity sufficient for CLI |
| tqdm | Click's progressbar | Click's built-in progress bar less customizable; tqdm offers more control for complex scenarios |
| pydub | ffmpeg-python | ffmpeg-python more low-level; pydub higher-level API better for silence detection |
| concurrent.futures | multiprocessing | Raw multiprocessing gives more control but requires more boilerplate; concurrent.futures simpler |

**Installation:**
```bash
pip install faster-whisper>=1.2.1 tqdm>=4.67.0 pydub>=0.25.1 soundfile>=0.12.1
```

## Architecture Patterns

### Recommended Project Structure
```
transcribe/
├── cli.py              # CLI entry point (existing)
├── transcriber.py      # Transcription logic (existing, needs updates)
├── formatter.py        # Markdown formatting (existing, needs updates)
├── extractor.py        # Audio extraction (existing)
├── validators.py       # Validation logic (existing)
├── chunker.py          # NEW: Audio chunking with silence detection
├── parallel.py         # NEW: Parallel chunk processing
└── progress.py         # NEW: Progress bar management
```

### Pattern 1: Silence-Based Audio Chunking

**What:** Split long audio files at natural silence points to create chunks for parallel processing
**When to use:** Videos longer than 10 minutes (as specified by user)
**Example:**
```python
# Source: pydub documentation + research findings
from pydub import AudioSegment
from pydub.silence import split_on_silence

def chunk_audio_by_silence(audio_path, min_silence_len=500, silence_thresh=-40):
    """
    Split audio at silence points for natural chunk boundaries.

    Args:
        audio_path: Path to audio file
        min_silence_len: Minimum silence duration in ms (default: 500ms)
        silence_thresh: Silence threshold in dBFS (default: -40)

    Returns:
        List of AudioSegment chunks
    """
    audio = AudioSegment.from_wav(audio_path)

    # Split on silence with keep_silence to avoid abrupt cuts
    chunks = split_on_silence(
        audio,
        min_silence_len=min_silence_len,
        silence_thresh=silence_thresh,
        keep_silence=100  # Keep 100ms silence at chunk boundaries
    )

    # Merge small chunks to approach optimal ~30s size
    merged_chunks = []
    current_chunk = AudioSegment.empty()

    for chunk in chunks:
        # If adding this chunk stays under 30s, merge it
        if len(current_chunk) + len(chunk) < 30000:  # 30s in ms
            current_chunk += chunk
        else:
            if len(current_chunk) > 0:
                merged_chunks.append(current_chunk)
            current_chunk = chunk

    if len(current_chunk) > 0:
        merged_chunks.append(current_chunk)

    return merged_chunks
```

### Pattern 2: Parallel Chunk Processing with Progress

**What:** Process multiple audio chunks in parallel using ProcessPoolExecutor while showing progress
**When to use:** Long videos with multiple chunks
**Example:**
```python
# Source: Python concurrent.futures docs + tqdm integration
from concurrent.futures import ProcessPoolExecutor, as_completed
from tqdm import tqdm

def transcribe_chunks_parallel(chunks, model_size="small", max_workers=None):
    """
    Transcribe audio chunks in parallel with progress bar.

    Args:
        chunks: List of (chunk_id, audio_path) tuples
        model_size: Whisper model size
        max_workers: Number of parallel workers (default: CPU count)

    Returns:
        List of (chunk_id, segments, info) tuples
    """
    results = []

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        # Submit all chunks
        futures = {
            executor.submit(transcribe_single_chunk, chunk_path, model_size): chunk_id
            for chunk_id, chunk_path in chunks
        }

        # Process results as they complete with progress bar
        with tqdm(total=len(chunks), desc="Transcribing", unit="chunk") as pbar:
            for future in as_completed(futures):
                chunk_id = futures[future]
                try:
                    segments, info = future.result()
                    results.append((chunk_id, segments, info))
                except Exception as exc:
                    print(f"Chunk {chunk_id} error: {exc}")
                finally:
                    pbar.update(1)

    # Sort by chunk_id to maintain order
    results.sort(key=lambda x: x[0])
    return results

def transcribe_single_chunk(audio_path, model_size):
    """Worker function for parallel transcription."""
    from faster_whisper import WhisperModel

    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, info = model.transcribe(str(audio_path), vad_filter=True)
    return list(segments), info
```

### Pattern 3: Overlap Deduplication

**What:** Remove duplicate text from overlapping chunks using difflib
**When to use:** After merging parallel transcription results with overlapping chunks
**Example:**
```python
# Source: Python difflib documentation
from difflib import SequenceMatcher

def deduplicate_overlap(text1, text2, threshold=0.85):
    """
    Remove overlapping text between consecutive chunks.

    Args:
        text1: Text from first chunk (end portion)
        text2: Text from second chunk (start portion)
        threshold: Similarity threshold (0.0-1.0) for detecting overlap

    Returns:
        Deduplicated text2 with overlap removed
    """
    # Compare last N words of text1 with first N words of text2
    words1 = text1.split()[-50:]  # Check last 50 words
    words2 = text2.split()[:50]   # Check first 50 words

    matcher = SequenceMatcher(None, words1, words2)
    match = matcher.find_longest_match(0, len(words1), 0, len(words2))

    # If significant overlap found, remove it from text2
    if match.size > 0 and matcher.ratio() > threshold:
        # Remove overlapping words from start of text2
        return " ".join(words2[match.b + match.size:]) + " " + " ".join(text2.split()[50:])

    return text2
```

### Pattern 4: Adaptive Timestamp Formatting

**What:** Format timestamps as MM:SS for short videos, HH:MM:SS for long videos
**When to use:** When formatting transcript output
**Example:**
```python
# Source: Python time formatting research
def format_timestamp_adaptive(seconds, total_duration):
    """
    Format timestamp adaptively based on video duration.

    Args:
        seconds: Timestamp in seconds
        total_duration: Total video duration in seconds

    Returns:
        Formatted timestamp string
    """
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)

    # Use HH:MM:SS for videos 1 hour or longer
    if total_duration >= 3600:
        return f"{h}:{m:02d}:{s:02d}"
    else:
        return f"{m}:{s:02d}"
```

### Pattern 5: Quality Validation with Confidence Scores

**What:** Access segment confidence scores and calculate average for quality assessment
**When to use:** After transcription to validate quality and decide on model upgrade
**Example:**
```python
# Source: faster-whisper GitHub issues + documentation
def validate_transcription_quality(segments, confidence_threshold=-1.0):
    """
    Validate transcription quality using average log probability.

    Args:
        segments: List of transcription segments
        confidence_threshold: Threshold for avg log probability (default: -1.0)

    Returns:
        Tuple of (is_high_quality, avg_confidence)
    """
    # Extract avg_logprob from segments
    confidences = []
    for segment in segments:
        if hasattr(segment, 'avg_logprob'):
            confidences.append(segment.avg_logprob)

    if not confidences:
        return True, None  # No confidence data available

    avg_confidence = sum(confidences) / len(confidences)
    is_high_quality = avg_confidence >= confidence_threshold

    return is_high_quality, avg_confidence
```

### Pattern 6: Two-Stage Progress Display

**What:** Show separate progress for audio extraction and transcription stages
**When to use:** Always, unless --quiet flag is set
**Example:**
```python
# Source: tqdm documentation + Click integration
import click
from tqdm import tqdm

def process_with_progress(video_path, quiet=False):
    """Process video with two-stage progress display."""

    if not quiet:
        # Stage 1: Audio extraction (no progress bar, just status)
        click.echo("Extracting audio... ", nl=False)

    extract_audio(video_path, temp_audio)

    if not quiet:
        click.echo("[done]")

        # Stage 2: Transcription with progress bar
        # For long videos with chunks
        with tqdm(total=num_chunks, desc="Transcribing",
                  unit="chunk", bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]') as pbar:
            # Process chunks and update progress
            pass
    else:
        # Quiet mode: minimal output
        click.echo("Extracting... Transcribing... Done.")
```

### Anti-Patterns to Avoid

- **Processing entire 3-hour audio as single file:** Causes memory issues and no progress feedback; always chunk long videos
- **Using threading for CPU-bound transcription:** Python GIL prevents true parallelism; use multiprocessing/ProcessPoolExecutor
- **Creating overlapping chunks without deduplication:** Results in duplicate text in transcript; always deduplicate overlaps
- **Not using VAD filter:** Whisper hallucinates on silence/music; VAD removes non-speech segments before transcription
- **Ignoring confidence scores:** Low confidence indicates poor transcription; validate and retry with better model
- **Loading all chunks into RAM:** Memory exhaustion on long videos; process chunks as a stream
- **Not handling picklability in parallel processing:** Lambda functions and local functions can't be pickled; use module-level functions

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Progress bars | Custom progress tracker with sys.stdout manipulation | tqdm | Handles terminal width, ETA calculation, nested bars, Unicode issues, refresh rate optimization |
| Silence detection | Custom audio analysis with numpy/scipy | pydub.silence.split_on_silence | Handles edge cases (very quiet vs silent, short blips), optimized thresholds, tested across audio formats |
| Parallel processing | Manual process spawning with multiprocessing.Process | concurrent.futures.ProcessPoolExecutor | Handles process pool lifecycle, exception propagation, result gathering, deadlock prevention |
| Text similarity | Custom word matching algorithm | difflib.SequenceMatcher | Handles longest common substring, fuzzy matching, optimized for text; well-tested algorithm |
| Timestamp formatting | String manipulation with division/modulo | time.strftime or divmod-based utility | Handles edge cases (midnight, 24+ hours), consistent formatting, locale support |
| Audio format conversion | Manual FFmpeg command construction | pydub AudioSegment | Handles format detection, codec selection, sample rate conversion, error handling |

**Key insight:** Audio processing and parallel computing have subtle edge cases that mature libraries have solved through years of production usage. The time saved by using these libraries far exceeds any "not invented here" benefits.

## Common Pitfalls

### Pitfall 1: Whisper Hallucination on Non-Speech Audio

**What goes wrong:** Whisper generates plausible-sounding but completely incorrect transcriptions when processing silence, music, or background noise

**Why it happens:** Whisper is trained to always output text; when given non-speech audio, it hallucinates content based on audio patterns (research shows 80%+ hallucination rate on non-speech audio)

**How to avoid:**
1. Enable VAD filter in faster-whisper: `vad_filter=True`
2. Set `min_silence_duration_ms=500` in vad_parameters
3. Use pydub to detect and skip long silent sections before transcription
4. Mark remaining non-speech segments with confidence-based detection

**Warning signs:**
- Transcripts containing repeated phrases or loops
- Transcription of background music as gibberish words
- Very low confidence scores (avg_logprob < -1.0)
- Transcript length much shorter/longer than expected

### Pitfall 2: Memory Exhaustion from Parallel Processing

**What goes wrong:** Processing many chunks in parallel causes RAM usage to spike and system to freeze or crash

**Why it happens:** Each worker process loads its own Whisper model (~461MB for small, ~769MB for medium), plus audio data; 8 workers = 3-6GB RAM

**How to avoid:**
1. Limit max_workers based on available RAM: `max_workers = min(cpu_count, ram_gb // 2)`
2. Use context manager to ensure cleanup: `with ProcessPoolExecutor(...) as executor`
3. Process results as they complete rather than waiting for all: `as_completed(futures)`
4. Don't load all chunks into memory; stream from disk

**Warning signs:**
- System slowdown during transcription
- Swap usage increasing
- Process killed by OOM killer
- Longer processing time than single-threaded (thrashing)

### Pitfall 3: Timestamp Drift from Chunk Reassembly

**What goes wrong:** Timestamps from chunked processing don't match original video timeline; segments jump backward in time or overlap

**Why it happens:** Each chunk is transcribed independently with timestamps starting at 0; reassembling without adjusting timestamps causes misalignment

**How to avoid:**
1. Track each chunk's start time in original audio: `chunk_metadata = [(chunk_id, start_time, duration), ...]`
2. Adjust segment timestamps during reassembly: `segment.start += chunk_start_time`
3. Validate timestamp monotonicity after reassembly
4. Keep overlap metadata to handle boundary segments correctly

**Warning signs:**
- Timestamps not monotonically increasing
- Timestamp jumps backward between segments
- Segments at chunk boundaries duplicated with different timestamps
- Final segment timestamp doesn't match video duration

### Pitfall 4: Pickle Errors in Parallel Processing

**What goes wrong:** `PicklingError` or `AttributeError` when trying to process chunks in parallel

**Why it happens:** ProcessPoolExecutor serializes functions and data with pickle; lambda functions, local functions, and certain objects can't be pickled

**How to avoid:**
1. Define worker functions at module level, not inside other functions
2. Don't use lambda functions for worker tasks
3. Don't pass complex objects (file handles, threads) to workers
4. Pass paths/primitives and reconstruct objects in worker

**Warning signs:**
- `can't pickle <lambda>` error
- `AttributeError: Can't pickle local object` error
- Function works normally but fails with ProcessPoolExecutor
- Different behavior between map() and submit()

### Pitfall 5: Language Detection Failure on Short Chunks

**What goes wrong:** Language detection inconsistent across chunks; some chunks detected as wrong language

**Why it happens:** Whisper detects language from first 30 seconds of audio; short chunks (<30s) may not have enough context for accurate detection

**How to avoid:**
1. Detect language once from full audio or first chunk before chunking
2. Pass detected language explicitly to all chunk transcriptions: `language="es"`
3. Don't rely on auto-detection for each chunk independently
4. For mixed-language videos, process as separate sections

**Warning signs:**
- Different language codes in different chunks
- Some chunks with very low language_probability (<0.5)
- Transcription quality varies dramatically between chunks
- Obvious Spanish transcribed as English or vice versa

### Pitfall 6: Progress Bar Artifacts in Logs

**What goes wrong:** Progress bars leave artifacts in log files or CI/CD output; garbled terminal output

**Why it happens:** Progress bars use ANSI escape codes and carriage returns that don't render correctly in non-terminal contexts

**How to avoid:**
1. Detect terminal context: `if not sys.stdout.isatty(): disable=True`
2. Respect --quiet flag to disable progress completely
3. Use tqdm's `file` parameter to redirect to stderr: `file=sys.stderr`
4. For logging, use separate logger instead of mixing with tqdm

**Warning signs:**
- Log files contain `\r` characters or ANSI codes
- CI/CD logs show garbled output
- Progress bar overwrites important messages
- Terminal height detection errors

## Code Examples

Verified patterns from official sources:

### faster-whisper Transcription with VAD

```python
# Source: https://github.com/SYSTRAN/faster-whisper README
from faster_whisper import WhisperModel

model = WhisperModel("small", device="cpu", compute_type="int8")

# Enable VAD to filter out non-speech segments
segments, info = model.transcribe(
    "audio.mp3",
    vad_filter=True,
    vad_parameters=dict(min_silence_duration_ms=500)
)

# Access confidence scores
for segment in segments:
    print(f"[{segment.start:.2f}s -> {segment.end:.2f}s] {segment.text}")
    print(f"Confidence: {segment.avg_logprob:.2f}")
```

### faster-whisper Language Detection

```python
# Source: https://github.com/SYSTRAN/faster-whisper issues
from faster_whisper import WhisperModel

model = WhisperModel("small", device="cpu", compute_type="int8")

# Auto-detect language (uses first 30 seconds)
segments, info = model.transcribe("audio.mp3")
print(f"Detected language: {info.language} (confidence: {info.language_probability:.2%})")

# For chunked processing, detect once and pass to all chunks
detected_language = info.language
segments, info = model.transcribe("chunk.mp3", language=detected_language)
```

### faster-whisper Word Timestamps

```python
# Source: https://github.com/SYSTRAN/faster-whisper README
from faster_whisper import WhisperModel

model = WhisperModel("small", device="cpu", compute_type="int8")

segments, info = model.transcribe("audio.mp3", word_timestamps=True)

for segment in segments:
    for word in segment.words:
        print(f"[{word.start:.2fs -> {word.end:.2fs}] {word.word}")
```

### tqdm Basic Progress Bar

```python
# Source: https://github.com/tqdm/tqdm README
from tqdm import tqdm
import time

# Wrap any iterable
for i in tqdm(range(100)):
    time.sleep(0.01)

# Manual updates
with tqdm(total=100) as pbar:
    for i in range(10):
        time.sleep(0.1)
        pbar.update(10)
```

### tqdm with Custom Format

```python
# Source: https://github.com/tqdm/tqdm documentation
from tqdm import tqdm

# Custom bar format showing elapsed and remaining time
with tqdm(total=100, bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]') as pbar:
    for i in range(100):
        pbar.update(1)
```

### ProcessPoolExecutor Basic Usage

```python
# Source: https://docs.python.org/3/library/concurrent.futures.html
from concurrent.futures import ProcessPoolExecutor, as_completed

def process_chunk(chunk_id, data):
    # CPU-intensive work here
    return chunk_id, result

chunks = [(i, data) for i in range(10)]

with ProcessPoolExecutor(max_workers=4) as executor:
    # Submit all tasks
    futures = {executor.submit(process_chunk, i, d): i for i, d in chunks}

    # Process results as they complete
    for future in as_completed(futures):
        chunk_id = futures[future]
        try:
            result = future.result()
            print(f"Chunk {chunk_id} done: {result}")
        except Exception as exc:
            print(f"Chunk {chunk_id} error: {exc}")
```

### pydub Silence Detection

```python
# Source: https://github.com/jiaaro/pydub/blob/master/pydub/silence.py
from pydub import AudioSegment
from pydub.silence import split_on_silence, detect_silence

# Load audio
audio = AudioSegment.from_wav("audio.wav")

# Detect silence ranges
silent_ranges = detect_silence(
    audio,
    min_silence_len=1000,  # 1 second
    silence_thresh=-40     # -40 dBFS
)

# Split on silence
chunks = split_on_silence(
    audio,
    min_silence_len=500,   # 500ms minimum silence
    silence_thresh=-40,    # -40 dBFS threshold
    keep_silence=100       # Keep 100ms at boundaries
)

print(f"Split into {len(chunks)} chunks")
```

### Reading Time Estimation

```python
# Source: Research on reading time calculation
import re

def estimate_reading_time(text, wpm=180):
    """
    Estimate reading time for text.

    Args:
        text: Text to analyze
        wpm: Words per minute (default: 180 for monitor reading)

    Returns:
        Reading time in minutes
    """
    word_count = len(re.findall(r'\w+', text))
    reading_time = word_count / wpm
    return reading_time

# Example usage
transcript = "..." # transcript text
word_count = len(re.findall(r'\w+', transcript))
reading_time_min = estimate_reading_time(transcript)

print(f"Word count: {word_count}")
print(f"Estimated reading time: {reading_time_min:.1f} minutes")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| OpenAI Whisper | faster-whisper | 2023 | 4x faster, same accuracy, less memory via CTranslate2 optimization |
| Process entire audio as single file | VAD + silence-based chunking | 2024-2025 | Reduces hallucinations, enables parallel processing, better progress feedback |
| Fixed HH:MM:SS timestamps | Adaptive MM:SS or HH:MM:SS based on duration | Best practice | More readable for short videos, matches user expectations |
| Ignore confidence scores | Validate with avg_logprob threshold | Research (Jan 2025) | Enables quality detection and auto-retry with better models |
| Text-only progress (Phase 1) | Visual progress bars with tqdm | Industry standard | Better UX for long-running operations |
| Threading for I/O | ProcessPoolExecutor for CPU-bound | Python best practice | True parallelism for transcription, simpler API than raw multiprocessing |

**Deprecated/outdated:**
- **word_timestamps=True for every segment:** Performance impact; Phase 2 only needs segment-level timestamps merged into paragraphs
- **BatchedInferencePipeline:** Faster but less stable than standard transcription; stick with standard API for production
- **Global language detection per chunk:** Causes inconsistency; detect once from full audio or first chunk

## Recommended Implementation Strategy

Based on user constraints and research findings:

### 1. Chunk Size Calculation

**Recommendation:** Target 20-25 second chunks with silence-based splitting

**Rationale:**
- Whisper's optimal receptive field is 30 seconds
- Silence-based splitting creates natural boundaries (500ms silence threshold)
- 20-25s average leaves headroom for Whisper's context window
- Smaller chunks enable finer progress granularity

**Implementation:** Use pydub to split on silence, then merge small chunks to reach target duration

### 2. Overlap Strategy

**Recommendation:** 2-3 second overlap between chunks

**Rationale:**
- Prevents losing words at chunk boundaries
- Small enough to not waste processing time
- Large enough to reliably detect duplicates with difflib
- Industry practice for speech recognition chunking

**Implementation:** When splitting audio, include last 2-3s of previous chunk in next chunk; deduplicate after transcription

### 3. Silence Detection Thresholds

**Recommendation:**
- `min_silence_len=500` (500ms)
- `silence_thresh=-40` (dBFS)
- `keep_silence=100` (100ms)

**Rationale:**
- 500ms catches natural pauses without splitting mid-sentence
- -40 dBFS works for typical meeting/presentation audio (not studio quality)
- 100ms keep_silence prevents abrupt cuts that confuse Whisper

**Implementation:** Use pydub defaults as starting point, these values from research

### 4. Parallel Processing Workers

**Recommendation:** `max_workers = min(os.cpu_count(), max(1, available_ram_gb // 2))`

**Rationale:**
- Each worker loads ~500MB model (small) or ~800MB (medium)
- Limit by RAM to prevent thrashing
- Use CPU count as upper bound for CPU-bound work

**Implementation:** Check available RAM with psutil, calculate safe worker count

### 5. Progress Bar Configuration

**Recommendation:** Use tqdm with custom format showing chunks and ETA

**Format:** `Transcribing: [████░░░░] 45% (chunk 9/20) [01:23<01:52]`

**Rationale:**
- User requested: percentage, elapsed, ETA, chunk indicator
- tqdm provides all metrics automatically
- Custom bar_format assembles them cleanly

**Implementation:** Single tqdm instance updated as chunks complete via `as_completed()`

### 6. Confidence Threshold

**Recommendation:** `avg_logprob >= -1.0` for acceptable quality

**Rationale:**
- Whisper authors use -1.0 as threshold in their papers
- Research shows this effectively filters low-quality transcriptions
- Balances strictness with usability

**Implementation:** Calculate average of segment.avg_logprob values, warn if below threshold, auto-retry with medium model

### 7. Timestamp Merging Strategy

**Recommendation:** Merge segments with <2 second gap into paragraphs

**Rationale:**
- Natural speaking includes <2s pauses within thought
- >2s pauses indicate topic/speaker change
- Creates readable paragraphs instead of single-sentence segments

**Implementation:** Iterate segments, accumulate text until gap >2s, emit paragraph with first segment's timestamp

### 8. Non-Speech Detection

**Recommendation:** Use VAD filter + confidence-based post-processing

**Rationale:**
- VAD removes obvious non-speech (silence, continuous noise)
- Confidence scores catch hallucinations VAD misses (music, background)
- Two-stage approach reduces false positives

**Implementation:** Enable vad_filter=True, mark segments with avg_logprob < -1.5 as [background noise]

## Open Questions

1. **Optimal balance between chunk count and parallelism**
   - What we know: More chunks = finer progress but more overhead
   - What's unclear: Sweet spot for 1-3 hour videos on typical hardware
   - Recommendation: Start with 20-25s chunks, measure performance, adjust if needed

2. **Model upgrade threshold precision**
   - What we know: avg_logprob < -1.0 indicates low quality
   - What's unclear: Best threshold for auto-upgrade decision (stricter? more lenient?)
   - Recommendation: Use -1.0 initially, collect user feedback on false positives/negatives

3. **Memory usage on low-RAM systems**
   - What we know: Each worker needs ~500-800MB for model
   - What's unclear: Graceful degradation strategy for <4GB RAM systems
   - Recommendation: Detect RAM, fallback to serial processing with warning if <2GB available

4. **Language detection edge cases**
   - What we know: First 30s used for detection, can fail on short clips
   - What's unclear: Should we require minimum duration for auto-detection?
   - Recommendation: Detect from first chunk, if confidence <0.5, try next chunk

5. **Reading time calculation accuracy**
   - What we know: Standard 180 WPM for monitor reading, 200 WPM for paper
   - What's unclear: Adjust for technical content, non-native languages, etc.?
   - Recommendation: Use 180 WPM baseline, note as "estimated" in metadata

## Sources

### Primary (HIGH confidence)

- [faster-whisper GitHub Repository](https://github.com/SYSTRAN/faster-whisper) - API usage, VAD filter, confidence scores, language detection
- [Python concurrent.futures Documentation](https://docs.python.org/3/library/concurrent.futures.html) - ProcessPoolExecutor patterns, exception handling
- [tqdm GitHub Repository](https://github.com/tqdm/tqdm) - Progress bar API, performance characteristics
- [pydub silence.py Source](https://github.com/jiaaro/pydub/blob/master/pydub/silence.py) - Silence detection parameters and defaults
- [Python difflib Documentation](https://docs.python.org/3/library/difflib.html) - SequenceMatcher for text deduplication

### Secondary (MEDIUM confidence)

- [Faster Whisper Optimal Chunk Size Discussion](https://github.com/SYSTRAN/faster-whisper/issues/985) - Verified 30s optimal chunk size, VAD approach
- [Whisper Model Size Comparison](https://openwhispr.com/blog/whisper-model-sizes-explained) - Small vs medium accuracy (~95% vs ~99%) and speed comparison
- [Python Concurrency Best Practices](https://realpython.com/python-concurrency/) - When to use ProcessPoolExecutor vs threading
- [Timestamp Formatting in Python](https://pynative.com/python-convert-seconds-to-hhmmss/) - Multiple approaches verified
- [Reading Time Estimation Methods](https://mfouesneau.github.io/posts/python_readtime_estimate.html) - WPM standards and calculation

### Tertiary (LOW confidence)

- [Whisper Hallucination Research](https://arxiv.org/html/2501.11378v1) - Non-speech hallucination rates, recent (Jan 2025) but not peer-reviewed yet
- [Confidence Score Estimation Research](https://arxiv.org/abs/2502.13446) - C-Whisper approach, recent (Feb 2025) research paper

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries are mature, widely used, with extensive documentation
- Architecture: HIGH - Patterns verified from official sources and production usage
- Pitfalls: HIGH - Based on documented issues, GitHub discussions, and established best practices
- Optimal parameters: MEDIUM - Research-backed but may need tuning for specific hardware/content

**Research date:** 2026-03-02
**Valid until:** 2026-06-02 (90 days) - Stack is mature and stable, unlikely to change significantly
