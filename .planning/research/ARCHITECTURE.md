# Architecture Research

**Domain:** Video Transcription and Summarization CLI Tool
**Researched:** 2026-03-02
**Confidence:** HIGH

## Standard Architecture

### System Overview

```
┌────────────────────────────────────────────────────────────────┐
│                     CLI Interface Layer                         │
│  ┌──────────┐  ┌────────────┐  ┌──────────┐  ┌─────────┐      │
│  │  Argparse│  │  Validator │  │  Logger  │  │ Progress│      │
│  │  Handler │  │  Component │  │          │  │  Tracker│      │
│  └────┬─────┘  └─────┬──────┘  └────┬─────┘  └────┬────┘      │
│       │              │              │             │            │
├───────┴──────────────┴──────────────┴─────────────┴────────────┤
│                    Orchestrator Layer                           │
│  ┌──────────────────────────────────────────────────────┐      │
│  │  Pipeline Coordinator                                 │      │
│  │  - Manages component lifecycle                        │      │
│  │  - Handles errors and retries                         │      │
│  │  - Coordinates data flow between components           │      │
│  └─────────────────┬────────────────────────────────────┘      │
│                    │                                            │
├────────────────────┴────────────────────────────────────────────┤
│                 Processing Components Layer                     │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐       │
│  │   Audio      │  │ Transcription│  │ Summarization  │       │
│  │  Extractor   │→ │   Engine     │→ │    Engine      │       │
│  │  (FFmpeg)    │  │  (Whisper)   │  │   (Claude)     │       │
│  └──────────────┘  └──────────────┘  └────────────────┘       │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                   Utilities Layer                               │
│  ┌─────────┐  ┌──────────┐  ┌────────┐  ┌──────────────┐      │
│  │  File   │  │  Temp    │  │ Format │  │   Timestamp  │      │
│  │ Manager │  │ Manager  │  │ Handler│  │   Adjuster   │      │
│  └─────────┘  └──────────┘  └────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| CLI Handler | Parse arguments, validate inputs, provide help | argparse or click library with custom validators |
| Pipeline Coordinator | Orchestrate the full transcription workflow | Python class managing sequential component execution |
| Audio Extractor | Extract audio stream from video files | FFmpeg subprocess wrapper with stream mapping |
| Transcription Engine | Convert audio to text with timestamps | Whisper API/local model with chunking logic |
| Summarization Engine | Generate summaries from transcripts | Claude API client with prompt templates |
| Temp Manager | Handle temporary audio files safely | contextlib for cleanup, tempfile for secure creation |
| File Manager | Read/write final outputs alongside source | pathlib for path manipulation, safe file operations |
| Timestamp Adjuster | Fix timestamps across chunked segments | Utility to add offsets to Whisper timestamp objects |

## Recommended Project Structure

```
transcribe_cli/
├── __init__.py
├── __main__.py              # Entry point for python -m transcribe_cli
├── cli.py                   # CLI interface and argument parsing
├── pipeline.py              # Main orchestration logic
├── components/
│   ├── __init__.py
│   ├── audio_extractor.py   # FFmpeg wrapper for audio extraction
│   ├── transcriber.py       # Whisper transcription engine
│   └── summarizer.py        # Claude API summarization engine
├── utils/
│   ├── __init__.py
│   ├── file_ops.py          # File I/O utilities
│   ├── temp_manager.py      # Temporary file management
│   ├── chunking.py          # Audio chunking for large files
│   ├── timestamp.py         # Timestamp adjustment utilities
│   └── validators.py        # Input validation helpers
├── config/
│   ├── __init__.py
│   └── settings.py          # Configuration constants and defaults
└── exceptions.py            # Custom exception hierarchy

tests/
├── __init__.py
├── test_audio_extractor.py
├── test_transcriber.py
├── test_summarizer.py
└── fixtures/
    └── sample_videos/       # Small test video files

README.md
requirements.txt
setup.py
pyproject.toml
```

### Structure Rationale

- **components/:** Isolates the three core processing units (extract, transcribe, summarize) for independent testing and potential future replacement
- **utils/:** Shared utilities that don't have external dependencies or business logic
- **pipeline.py:** Single orchestration point makes error handling and logging centralized
- **config/:** Separates configuration from code for easier environment-specific adjustments
- **Flat tests/:** Mirrors src structure for obvious test-to-code mapping

## Architectural Patterns

### Pattern 1: Pipeline Coordinator Pattern

**What:** A central orchestrator that manages the sequential execution of processing components, handles errors at each stage, and maintains state throughout the workflow.

**When to use:** For workflows where components have strict dependencies (audio extraction must precede transcription) and you need centralized error handling and progress tracking.

**Trade-offs:**
- Pros: Single point of control, easier debugging, straightforward error recovery
- Cons: Sequential processing (no parallelization), coordinator becomes a god object if not careful

**Example:**
```python
class TranscriptionPipeline:
    def __init__(self, audio_extractor, transcriber, summarizer):
        self.audio_extractor = audio_extractor
        self.transcriber = transcriber
        self.summarizer = summarizer
        self.logger = logging.getLogger(__name__)

    def process(self, video_path: Path, output_format: str = "txt") -> Path:
        """Execute the full pipeline for a video file."""
        try:
            # Stage 1: Extract audio
            self.logger.info(f"Extracting audio from {video_path}")
            audio_file = self.audio_extractor.extract(video_path)

            # Stage 2: Transcribe
            self.logger.info(f"Transcribing {audio_file}")
            transcript = self.transcriber.transcribe(audio_file)

            # Stage 3: Summarize
            self.logger.info("Generating summary")
            summary = self.summarizer.summarize(transcript.text)

            # Stage 4: Write output
            output_path = self._write_output(video_path, transcript, summary, output_format)

            return output_path
        finally:
            # Cleanup temporary files
            self._cleanup_temp_files()
```

### Pattern 2: Chunking with Overlap for Large Files

**What:** Split long audio files into overlapping chunks to respect API/model constraints (Whisper's 30-second receptive field, 25MB file limits) while maintaining accurate temporal boundaries.

**When to use:** For videos longer than 30 seconds (all realistic use cases), especially 3+ hour meeting recordings.

**Trade-offs:**
- Pros: Handles arbitrary-length videos, maintains timestamp accuracy, respects API limits
- Cons: More complex implementation, requires timestamp adjustment, slight processing overhead from overlap

**Example:**
```python
def chunk_audio_with_overlap(audio_file: Path, chunk_duration_s: int = 180,
                             stride_ratio: float = 1/6) -> List[AudioChunk]:
    """
    Split audio into chunks with overlap for seamless transcription.

    Args:
        audio_file: Path to audio file
        chunk_duration_s: Length of each chunk (3 minutes default)
        stride_ratio: Overlap ratio (1/6 means 30s overlap for 180s chunks)

    Returns:
        List of AudioChunk objects with start_time and file_path
    """
    stride_s = chunk_duration_s * stride_ratio
    chunks = []

    # Use FFmpeg to get total duration
    total_duration = get_audio_duration(audio_file)

    current_start = 0
    chunk_index = 0

    while current_start < total_duration:
        chunk_end = min(current_start + chunk_duration_s, total_duration)

        # Extract chunk using FFmpeg
        chunk_path = extract_segment(audio_file, current_start, chunk_duration_s)

        chunks.append(AudioChunk(
            file_path=chunk_path,
            start_time=current_start,
            end_time=chunk_end,
            index=chunk_index
        ))

        current_start += stride_s
        chunk_index += 1

    return chunks
```

### Pattern 3: Context Manager for Resource Cleanup

**What:** Use Python context managers to guarantee cleanup of temporary files, even if processing fails.

**When to use:** Always, for any temporary file creation (extracted audio, intermediate chunks).

**Trade-offs:**
- Pros: Guaranteed cleanup, prevents disk space leaks, cleaner error handling
- Cons: Requires slightly more boilerplate, but Python makes this minimal

**Example:**
```python
from contextlib import contextmanager
import tempfile
import shutil

@contextmanager
def temporary_audio_file(video_path: Path):
    """Extract audio to temporary file, guarantee cleanup."""
    temp_dir = None
    try:
        temp_dir = tempfile.mkdtemp(prefix="transcribe_")
        audio_path = Path(temp_dir) / f"{video_path.stem}.wav"

        # Extract audio
        extract_audio(video_path, audio_path)

        yield audio_path
    finally:
        if temp_dir and Path(temp_dir).exists():
            shutil.rmtree(temp_dir)

# Usage
with temporary_audio_file(video_path) as audio_path:
    transcript = transcriber.transcribe(audio_path)
    # audio_path is automatically cleaned up after this block
```

### Pattern 4: Lazy Summarization

**What:** Generate summaries only on-demand rather than by default, since not all use cases require summarization and it adds API costs.

**When to use:** When users may only want transcripts without summaries, or when processing many files in batch.

**Trade-offs:**
- Pros: Saves API costs, faster processing when summary not needed, modular design
- Cons: Requires reading transcript back if summarizing later

**Example:**
```python
# CLI design with optional summarization
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("video", type=Path)
    parser.add_argument("--summarize", action="store_true",
                       help="Generate summary using Claude API")
    parser.add_argument("--summary-style", choices=["brief", "detailed"],
                       default="brief")
    args = parser.parse_args()

    # Always transcribe
    transcript = pipeline.transcribe(args.video)

    # Conditionally summarize
    if args.summarize:
        summary = pipeline.summarize(transcript, style=args.summary_style)
        output = combine_transcript_and_summary(transcript, summary)
    else:
        output = transcript

    write_output(args.video, output)
```

## Data Flow

### Standard Execution Flow

```
[User Command]
    ↓
[CLI Parser] → Validate arguments → Check file exists
    ↓
[Pipeline Coordinator]
    ↓
[Audio Extractor]
    ├─→ Call FFmpeg subprocess
    ├─→ Map audio stream to WAV/MP3
    └─→ Save to temp file
    ↓
[Chunking Logic] (for files > 30s)
    ├─→ Calculate chunk count
    ├─→ Extract overlapping segments
    └─→ Return list of chunk files
    ↓
[Transcription Engine] (per chunk)
    ├─→ Load Whisper model OR call Whisper API
    ├─→ Transcribe chunk
    ├─→ Adjust timestamps by chunk offset
    └─→ Collect chunk results
    ↓
[Merge Chunks]
    ├─→ Concatenate text segments
    └─→ Ensure timestamp continuity
    ↓
[Summarization Engine] (optional)
    ├─→ Chunk transcript if > Claude context limit
    ├─→ Call Claude API with prompt
    └─→ Return summary
    ↓
[Output Writer]
    ├─→ Format as .txt or .md
    ├─→ Save alongside video file
    └─→ Report success
    ↓
[Cleanup]
    └─→ Remove temporary audio files
```

### Error Handling Flow

```
[Component Error]
    ↓
[Catch at Pipeline Level]
    ↓
[Log Error Details] → Write to stderr
    ↓
[Cleanup Temp Files]
    ↓
[Return Exit Code ≠ 0]
```

### Key Data Flows

1. **Video → Audio extraction:** FFmpeg reads video file, demuxes to isolate audio stream, optionally re-encodes to standard format (16kHz WAV for Whisper), writes to temporary directory
2. **Audio → Transcript with timestamps:** Whisper processes audio (in chunks if necessary), returns text with word-level or segment-level timestamps, timestamps are adjusted to absolute time from start of original audio
3. **Transcript → Summary:** Claude API receives full transcript text (or chunked if very long), applies summarization prompt with user-specified style, returns structured summary
4. **Data → Output file:** Formatted text (transcript + optional summary) written to same directory as source video with matching base name

## Build Order Dependencies

### Phase Recommendations for Roadmap

Based on component dependencies and risk profile:

**Phase 1: Core Pipeline (Audio Extraction + Basic Transcription)**
- Build audio extractor (FFmpeg wrapper)
- Build basic transcriber (single file, no chunking yet)
- Build file I/O utilities
- Implement temporary file management
- **Rationale:** Establishes the foundational data flow and proves core feasibility

**Phase 2: Chunking for Long Files**
- Implement audio chunking logic
- Add timestamp adjustment utilities
- Update transcriber to handle chunks
- **Rationale:** Necessary before real-world use (most videos > 30s)

**Phase 3: CLI and Error Handling**
- Build CLI interface with argparse
- Implement comprehensive error handling
- Add progress tracking/logging
- **Rationale:** Makes the tool actually usable and debuggable

**Phase 4: Summarization**
- Build Claude API client
- Implement summarization prompts
- Add optional summarization to pipeline
- **Rationale:** Independent of transcription, can be built after core works

**Phase 5: Polish and Optimization**
- Add language auto-detection
- Optimize chunking parameters
- Add batch processing support
- Improve output formatting
- **Rationale:** Quality-of-life improvements once foundation is solid

### Component Build Order

```
Utilities (file_ops, validators) → Audio Extractor → Transcriber (basic)
    → Chunking Logic → Transcriber (chunked) → Pipeline Coordinator
    → CLI Interface → Summarizer → Output Formatting
```

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 1-10 files/day | Current architecture is sufficient; local Whisper model recommended to avoid API costs |
| 10-100 files/day | Consider Whisper API for faster processing; implement batch mode for overnight processing; add job queue |
| 100+ files/day | Switch to cloud-based architecture with parallel processing; use ECS Fargate or similar for transcription tasks; implement S3 for temporary storage instead of local disk |

### Scaling Priorities

1. **First bottleneck:** Transcription time for long videos (3+ hours)
   - **Solution:** Implement parallel chunk processing instead of sequential; use Whisper API instead of local model for speed

2. **Second bottleneck:** Disk space from temporary files
   - **Solution:** Stream audio extraction directly to transcription API; implement aggressive cleanup; use streaming instead of file-based processing

3. **Third bottleneck:** Claude API rate limits for summarization
   - **Solution:** Implement exponential backoff retry logic; consider batch API for non-urgent summaries (50% cost reduction); cache summaries by content hash to avoid reprocessing

## Anti-Patterns

### Anti-Pattern 1: Loading Entire Audio File Into Memory

**What people do:** Read the entire audio file into a byte array for processing
**Why it's wrong:** For 3-hour videos, audio files can be 100MB+ uncompressed; causes memory errors and slow startup
**Do this instead:** Use file paths and let FFmpeg/Whisper stream from disk; only load chunks if implementing chunking

### Anti-Pattern 2: Ignoring FFmpeg Return Codes

**What people do:** Call FFmpeg via subprocess without checking exit status
**Why it's wrong:** Silent failures lead to processing corrupt or missing audio; users get confusing errors from Whisper instead of clear "audio extraction failed" messages
**Do this instead:** Always check `subprocess.run().returncode` and raise specific exceptions for FFmpeg failures

### Anti-Pattern 3: Fixed-Size Text Chunking for Claude

**What people do:** Split transcripts every N characters for summarization
**Why it's wrong:** Splits sentences mid-word, loses context across chunks, produces incoherent summaries
**Do this instead:** Use semantic chunking (split on sentence or paragraph boundaries); for this use case, most transcripts fit in Claude's context window (200K tokens), so chunking may not be needed

### Anti-Pattern 4: Synchronous API Calls in Batch Processing

**What people do:** Process multiple videos sequentially, waiting for each transcription and summary to complete
**Why it's wrong:** Wastes time waiting for I/O; a batch of 10 videos could take 10x as long as necessary
**Do this instead:** Use async/await or multiprocessing to transcribe multiple files concurrently; respect rate limits but maximize throughput

### Anti-Pattern 5: Not Preserving Video Metadata

**What people do:** Output transcript/summary with generic filename like `transcript_1.txt`
**Why it's wrong:** Users lose connection between transcript and source video; hard to manage multiple transcripts
**Do this instead:** Always name output file `{video_stem}.txt` and save in same directory as source; optionally include video metadata in output (duration, creation date)

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| FFmpeg | Subprocess with explicit args | Must be installed separately; check availability at startup with `which ffmpeg` or `ffmpeg -version` |
| Whisper (Local) | Python library import | Requires PyTorch and transformers; first run downloads models (~1-3GB); subsequent runs load from cache |
| Whisper (API) | REST API with file upload | 25MB file size limit; requires API key; handles chunking internally but doesn't preserve timestamps across chunks |
| Claude API | REST API with JSON | Use Anthropic Python SDK; requires API key; 200K token context window (500K+ with extended context models) |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| CLI ↔ Pipeline | Direct function call | CLI creates Pipeline instance, calls `process()` method |
| Pipeline ↔ Components | Direct method calls | Pipeline owns component instances, passes data via method arguments |
| Transcriber ↔ Chunking | Utility function calls | Chunking logic is stateless utility, returns list of file paths |
| Components ↔ Temp Files | File system (Path objects) | Use pathlib.Path for type safety; components return paths, not file handles |

## Technology-Specific Patterns

### FFmpeg Integration

**Recommended command structure for audio extraction:**
```bash
ffmpeg -i input.mp4 -vn -acodec pcm_s16le -ar 16000 -ac 1 output.wav
```
- `-vn`: No video (audio only)
- `-acodec pcm_s16le`: Uncompressed 16-bit PCM (Whisper compatible)
- `-ar 16000`: 16kHz sample rate (Whisper's native rate)
- `-ac 1`: Mono channel (reduces file size, sufficient for speech)

**For stream copying (faster, preserves quality):**
```bash
ffmpeg -i input.mp4 -vn -acodec copy -map 0:a output.m4a
```
- Use when input audio codec is already Whisper-compatible (AAC, MP3)

### Whisper Integration

**Local model usage:**
```python
import whisper

model = whisper.load_model("base")  # or "small", "medium", "large-v3"
result = model.transcribe(audio_path, language="es")  # or "en", or None for auto-detect

# result contains:
# - text: full transcript as string
# - segments: list of segments with timestamps
# - language: detected language
```

**Timestamp adjustment after chunking:**
```python
def adjust_timestamps(segments: List[dict], offset_seconds: float) -> List[dict]:
    """Add time offset to all segment timestamps."""
    for segment in segments:
        segment["start"] += offset_seconds
        segment["end"] += offset_seconds
        # Also adjust word-level timestamps if present
        if "words" in segment:
            for word in segment["words"]:
                word["start"] += offset_seconds
                word["end"] += offset_seconds
    return segments
```

### Claude API Integration

**Summarization prompt template:**
```python
SUMMARY_PROMPT = """You are transcribing a video. Here is the full transcript:

<transcript>
{transcript_text}
</transcript>

Please provide a {style} summary of this transcript. Focus on:
- Main topics discussed
- Key points and conclusions
- Action items (if any)

Format the summary in markdown with clear sections."""

# Usage
from anthropic import Anthropic

client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
response = client.messages.create(
    model="claude-opus-4-6",
    max_tokens=4000,
    messages=[{
        "role": "user",
        "content": SUMMARY_PROMPT.format(
            transcript_text=transcript,
            style="detailed"
        )
    }]
)
summary = response.content[0].text
```

## Sources

**Architecture and System Design:**
- [Designing a Scalable Audio Transcription System that Processes 100K+ Files/Day](https://medium.com/@onkars.dev/designing-a-scalable-audio-transcription-system-that-processes-100k-files-day-d24df9423e2b) - Comprehensive architecture for large-scale systems
- [The Ultimate 2026 Guide to Speech-to-Text (STT) APIs: Architecture, Providers, and Best Practices](https://aimlapi.com/blog/introduction-to-speech-to-text-technology) - STT pipeline architecture patterns

**Whisper and Transcription:**
- [Whisper Long-Form Transcription](https://medium.com/@yoad/whisper-long-form-transcription-1924c94a9b86) - Details on Whisper's sequential vs chunked algorithms
- [openai/whisper-large-v2 - Optimal long audio chunking](https://huggingface.co/openai/whisper-large-v2/discussions/67) - Chunking parameters and stride ratios
- [How to Build a Long Audio Transcription Tool with OpenAI's Whisper API](https://www.buildwithmatija.com/blog/building-a-long-audio-transcription-tool-with-openai-s-whisper-api) - Timestamp adjustment techniques
- [GitHub - openai/whisper](https://github.com/openai/whisper) - Official Whisper implementation

**FFmpeg Integration:**
- [How to extract audio from video files using FFmpeg](https://www.mux.com/articles/extract-audio-from-a-video-file-with-ffmpeg) - FFmpeg command patterns
- [Extracting Audio From Video Files Using FFmpeg](https://www.baeldung.com/linux/ffmpeg-audio-from-video) - Stream mapping and codec options

**Python CLI Best Practices:**
- [Best Practices for Structuring a Python CLI Application](https://medium.com/@ernestwinata/best-practices-for-structuring-a-python-cli-application-1bc8f8a57369) - Project structure patterns
- [Things I've learned about building CLI tools in Python](https://simonwillison.net/2023/Sep/30/cli-tools-python/) - Practical CLI design lessons
- [The Ultimate Guide to Error Handling in Python](https://blog.miguelgrinberg.com/post/the-ultimate-guide-to-error-handling-in-python) - Exception handling patterns

**Claude API and Summarization:**
- [Summarization with Claude](https://platform.claude.com/cookbook/capabilities-summarization-guide) - Official Claude summarization guide
- [Legal summarization - Claude API Docs](https://platform.claude.com/docs/en/about-claude/use-case-guides/legal-summarization) - Long document processing patterns

**Video Processing:**
- [Build Datasets for Video Generation: A 2026 Masterclass](https://www.huuphan.com/2026/02/build-datasets-for-video-generation.html) - Shot boundary detection vs blind chunking
- [Python Video Processing: 6 Useful Libraries and a Quick Tutorial](https://cloudinary.com/guides/front-end-development/python-video-processing-6-useful-libraries-and-a-quick-tutorial) - Library comparison

---
*Architecture research for: Video Transcription and Summarization CLI Tool*
*Researched: 2026-03-02*
