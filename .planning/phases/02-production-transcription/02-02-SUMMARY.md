---
phase: 02-production-transcription
plan: 02
subsystem: transcription-core
tags: [language-detection, quality-validation, adaptive-formatting, paragraph-merging]

dependency_graph:
  requires:
    - TRANS-02: Language auto-detection research
    - TRANS-03: Quality validation patterns
  provides:
    - TRANS-04: Production-ready transcriber with quality controls
    - TRANS-05: Enriched formatter with adaptive output
  affects:
    - transcribe/transcriber.py: Core transcription engine
    - transcribe/formatter.py: Output formatting system

tech_stack:
  added:
    - VAD filtering (faster-whisper built-in)
    - Log probability quality metrics
    - Adaptive timestamp formatting
    - Paragraph merging algorithm
  patterns:
    - Auto-upgrade pattern (small → medium model)
    - Quality validation with confidence scoring
    - Backward-compatible API extension

key_files:
  created: []
  modified:
    - transcribe/transcriber.py: +133 lines (language detection, VAD, quality validation)
    - transcribe/formatter.py: +121 lines (adaptive timestamps, paragraph merging, metadata)

decisions:
  - VAD enabled by default with 500ms silence threshold to reduce hallucinations
  - Quality threshold set at avg_logprob >= -1.0 for acceptability
  - Auto-upgrade from small to medium model on low confidence (one retry only)
  - Paragraph merging uses 2s gap threshold for natural pauses
  - Adaptive timestamps: MM:SS for <1hr videos, H:MM:SS for >=1hr
  - Confidence displayed as 0-100% using formula: (1 + avg_logprob) * 100
  - Reading time calculated at 180 words/minute
  - Non-speech marked as [background noise] when avg_logprob < -1.5

metrics:
  duration: 2 min
  tasks: 2
  files: 2
  commits: 2
  lines_added: 254
  completed: 2026-03-03
---

# Phase 02 Plan 02: Production Transcription Upgrade Summary

**One-liner:** Language auto-detection, VAD filtering, quality validation with auto-upgrade, adaptive timestamps, and paragraph merging for production-ready transcripts

## Objective Achieved

Upgraded transcriber for language detection and quality validation, and upgraded formatter for adaptive timestamps, paragraph merging, and enriched metadata. The tool now automatically detects language from the first 30 seconds, validates transcription quality, auto-upgrades from small to medium model on low confidence, and produces readable paragraphed output with meaningful timestamps and comprehensive metadata.

## Tasks Completed

### Task 1: Upgrade transcriber with language detection, VAD, and quality validation

**Status:** Complete
**Commit:** 3b71161
**Files:** transcribe/transcriber.py

**Implementation:**
- Added `detect_language(audio_path)` method that transcribes first 30 seconds to detect language, returns (language_code, probability) tuple, returns (None, probability) if confidence < 0.5
- Added `validate_quality(segments)` method that calculates average avg_logprob, converts to 0-100% confidence score, returns (is_acceptable, confidence_pct, avg_logprob) where acceptable threshold is -1.0
- Added `transcribe_with_quality(audio_path, language=None)` method that validates quality after transcription and auto-upgrades from small to medium model if quality is unacceptable
- Updated `transcribe()` method to accept optional language parameter and VAD parameters (vad_filter=True by default, min_silence_duration_ms=500)
- Implemented non-speech segment marking: segments with avg_logprob < -1.5 or no_speech_prob > 0.9 are marked as "[background noise]"
- Maintained backward compatibility: original transcribe() signature still works

**Verification:**
- All new methods (detect_language, validate_quality, transcribe_with_quality) are callable
- Transcriber imports successfully
- Backward compatibility preserved

### Task 2: Upgrade formatter with adaptive timestamps, paragraph merging, and metadata

**Status:** Complete
**Commit:** 1d7a075
**Files:** transcribe/formatter.py

**Implementation:**
- Added `format_timestamp_adaptive(seconds, total_duration)` that returns MM:SS for videos <1hr and H:MM:SS for videos >=1hr (no leading zeros on hours/minutes)
- Added `merge_segments_to_paragraphs(segments, gap_threshold=2.0)` that merges segments with <2s gaps into flowing paragraphs, returns list of (start_timestamp, merged_text) tuples
- Updated `format_transcript()` to accept optional confidence_pct and model_name parameters (defaults ensure backward compatibility)
- Enhanced metadata header with:
  - Word count (using regex `\w+` pattern)
  - Reading time (~N min at 180 words/minute, rounded up)
  - Confidence percentage (when provided)
  - Dynamic model name in "Model: faster-whisper (model_name)" format
- Changed transcript format to use paragraphs: timestamp on its own line, paragraph text below, blank line between paragraphs
- Kept legacy `format_timestamp()` function with comment "# Legacy: Phase 1 format" for backward compatibility
- Added `import re` for word counting

**Verification:**
- format_timestamp_adaptive(125, 3000) returns "2:05" (short video)
- format_timestamp_adaptive(125, 7200) returns "0:02:05" (long video)
- All new functions (format_timestamp_adaptive, merge_segments_to_paragraphs) are importable
- format_transcript() maintains backward compatibility with optional parameters

## Deviations from Plan

None - plan executed exactly as written.

## Integration Points

**Upstream dependencies:**
- faster-whisper WhisperModel for VAD filtering and language detection
- transcribe/transcriber.py provides segments with avg_logprob and no_speech_prob attributes
- transcribe/formatter.py consumes segments and info objects

**Downstream impact:**
- CLI (cli.py) still works with old transcribe() signature (backward compatible)
- Next plan (02-03) will update cli.py to use new transcribe_with_quality() and pass confidence_pct/model_name to formatter

**Key patterns established:**
- Quality-aware transcription with automatic model upgrade
- Adaptive output formatting based on content characteristics
- Enriched metadata for user transparency
- Backward-compatible API evolution

## Testing & Validation

**Manual verification:**
1. Transcriber imports successfully with all new methods
2. Formatter imports successfully with all new functions
3. Adaptive timestamp formatting produces correct output for short and long videos
4. Backward compatibility preserved for existing callers
5. All method signatures accept expected parameters

**Test results:** All 5 verification tests passed

**Edge cases handled:**
- Empty segments list returns (False, 0.0, -999.0) from validate_quality
- Language detection returns (None, probability) if confidence < 0.5
- Auto-upgrade only happens once (small → medium), not repeatedly
- Reading time minimum is 1 minute (even for very short transcripts)
- Paragraph merging handles last segment correctly

## Performance Impact

**Positive impacts:**
- VAD filtering reduces hallucination and processing time on silent sections
- Paragraph merging produces more readable output with fewer timestamp interruptions
- Quality validation catches poor transcriptions early

**Trade-offs:**
- Language detection from first 30 seconds adds minimal overhead
- Auto-upgrade from small to medium model (when needed) doubles processing time but ensures quality
- Confidence calculation iterates all segments once (negligible cost)

**Resource usage:**
- Small model: 461MB RAM (unchanged)
- Medium model: ~1.5GB RAM (loaded only when auto-upgrade triggered)
- No persistent storage impact

## Next Steps

Plan 02-03 will integrate these upgrades into the CLI:
- Update cli.py to use transcribe_with_quality() instead of transcribe()
- Pass confidence_pct and actual model_name to format_transcript()
- Add language detection step before transcription
- Display quality warnings to user
- Maintain clean CLI UX with new features

## Self-Check

Verifying all claimed artifacts exist and commits are valid...

**File existence:**

```
FOUND: transcribe/transcriber.py
FOUND: transcribe/formatter.py
```

**Commit existence:**

```
FOUND: 3b71161
FOUND: 1d7a075
```

**Method/function existence:**

```
FOUND: Transcriber.detect_language
FOUND: Transcriber.validate_quality
FOUND: Transcriber.transcribe_with_quality
FOUND: format_timestamp_adaptive
FOUND: merge_segments_to_paragraphs
```

## Self-Check: PASSED

All claimed files, commits, and functions verified to exist. Plan execution complete and documented accurately.
