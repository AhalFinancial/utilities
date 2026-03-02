---
phase: 01-foundation-pipeline
plan: 02
subsystem: transcription-pipeline
tags:
  - audio-extraction
  - speech-to-text
  - transcript-formatting
  - ffmpeg
  - whisper
dependency_graph:
  requires:
    - package-structure (01-01)
    - system-ffmpeg
  provides:
    - audio-extraction-api
    - whisper-transcription-api
    - markdown-formatting-api
  affects:
    - cli-integration (next phase)
tech_stack:
  added:
    - ffmpeg-python (audio extraction wrapper)
    - faster-whisper (speech-to-text engine)
  patterns:
    - lazy-model-loading (WhisperModel instantiation)
    - two-stage-pipeline (extract → transcribe)
    - generator-to-list-conversion (segment handling)
key_files:
  created:
    - transcribe/extractor.py (audio extraction)
    - transcribe/transcriber.py (Whisper transcription)
    - transcribe/formatter.py (markdown output)
  modified: []
decisions:
  - Use small Whisper model (461MB, good accuracy/speed balance for 5-10 min videos)
  - Default to CPU with int8 quantization for Phase 1 (simplest, works everywhere)
  - Convert segment generators to lists immediately to avoid iteration issues
  - Parse FFmpeg stderr for user-friendly error messages
metrics:
  duration: 114 seconds
  completed: 2026-03-02T22:24:32Z
  tasks: 3
  files: 3
---

# Phase 01 Plan 02: Core Transcription Pipeline Summary

**One-liner:** Three-stage audio pipeline with ffmpeg-python extraction, lazy-loaded Whisper transcription, and timestamped markdown formatting

## Overview

Implemented the core transcription pipeline modules: audio extraction from video using ffmpeg-python, speech-to-text transcription using faster-whisper with lazy model loading, and markdown output formatting with metadata headers. The pipeline handles edge cases including corrupted files, missing audio tracks, and no-speech audio.

## What Was Built

### 1. Audio Extraction Module (`transcribe/extractor.py`)

**Purpose:** Extract audio from video files to WAV format optimized for Whisper

**Key features:**
- Uses ffmpeg-python for clean FFmpeg integration
- Outputs 16kHz mono WAV (PCM signed 16-bit little-endian) optimized for Whisper
- Handles corrupted files with user-friendly error: "Could not read {filename} — file may be corrupted"
- Handles missing audio tracks: "No audio track found in {filename}"
- Parses FFmpeg stderr for common error patterns

**Exports:** `extract_audio(video_path, output_path)`

### 2. Transcription Module (`transcribe/transcriber.py`)

**Purpose:** Transcribe audio to text using faster-whisper with language detection

**Key features:**
- Lazy model loading pattern: WhisperModel initialized only on first transcription
- Uses small model (461MB, 244M params) for good accuracy/speed balance
- CPU mode with int8 quantization (works everywhere, no GPU required)
- Converts segment generators to lists immediately to avoid iteration issues
- Handles no-speech audio: raises ValueError("No speech detected in audio")
- Uses beam_size=5 for better accuracy per faster-whisper best practices

**Exports:** `Transcriber` class with `transcribe(audio_path)` method

### 3. Formatting Module (`transcribe/formatter.py`)

**Purpose:** Convert transcription segments to timestamped markdown with metadata

**Key features:**
- `format_timestamp(seconds)`: Converts float seconds to HH:MM:SS format
- `format_transcript(segments, info, video_filename)`: Builds complete markdown document
- Metadata header includes: source filename, date, duration, language (with confidence), model
- Timestamped blocks: `[00:01:23] Transcribed text here`
- Output language matches audio language (Spanish → Spanish, English → English)

**Exports:** `format_timestamp()`, `format_transcript()`

## Deviations from Plan

None - plan executed exactly as written.

All three modules implemented according to research patterns: lazy model loading for fast startup, proper FFmpeg error handling, segment generator conversion, and metadata header structure matching user requirements.

## Verification Results

All verification commands passed:

1. **Timestamp conversion:** `format_timestamp(3665)` returns `01:01:05` ✓
2. **Transcriber initialization:** Lazy loading works, no model downloaded at init ✓
3. **FFmpeg error handling:** Extractor parses stderr for corrupted/no-audio errors ✓
4. **Module structure:** All three modules present in transcribe/ directory ✓
5. **Import test:** All modules importable without errors ✓

## Success Criteria Met

- [x] extractor.py implements extract_audio() with ffmpeg-python
- [x] Handles corrupted files and missing audio tracks with user-friendly messages
- [x] transcriber.py implements Transcriber class with lazy model loading
- [x] Converts segment generators to lists, handles no-speech audio
- [x] formatter.py implements format_timestamp() and format_transcript()
- [x] Metadata header includes all user-specified fields (filename, date, duration, language, model)
- [x] Timestamp format is HH:MM:SS as required
- [x] All modules are importable

## Next Steps

Phase 01 Plan 03 will integrate these pipeline modules into a CLI using Click framework, implementing:
- `transcribe` command with video file argument
- FFmpeg availability check at startup
- Progress display during extraction and transcription
- Output file overwrite handling with --force flag
- Temp file cleanup in try/finally block

## Technical Notes

**Lazy Loading Pattern:** WhisperModel instantiation deferred to first transcribe() call to avoid 2-10 second startup delay and unnecessary 461MB model download if user just runs `--help`.

**Segment Generator Handling:** faster-whisper returns segments as generator (lazy evaluation). Converting to list immediately triggers actual transcription and allows multiple iterations if needed.

**FFmpeg Error Parsing:** FFmpeg outputs verbose diagnostic info to stderr even on success. Catching ffmpeg.Error and parsing for specific patterns ("Invalid data", "No such file") provides actionable error messages instead of raw subprocess output.

**Model Selection:** small model chosen for Phase 1 based on research recommendation: 461MB download, 244M params, good accuracy for 5-10 min videos, works on CPU. Larger models (medium: 1.5GB, large: 3GB) unnecessary for target use case.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | 48f1236 | feat(01-02): implement audio extraction module |
| 2 | cb5ce98 | feat(01-02): implement transcription module with lazy loading |
| 3 | 826e363 | feat(01-02): implement transcript formatting module |

## Self-Check: PASSED

All claimed files and commits verified:
- ✓ transcribe/extractor.py exists
- ✓ transcribe/transcriber.py exists
- ✓ transcribe/formatter.py exists
- ✓ Commit 48f1236 exists
- ✓ Commit cb5ce98 exists
- ✓ Commit 826e363 exists

---

**Phase:** 01-foundation-pipeline
**Plan:** 02 of 03
**Status:** Complete
**Duration:** 1 minute 54 seconds
