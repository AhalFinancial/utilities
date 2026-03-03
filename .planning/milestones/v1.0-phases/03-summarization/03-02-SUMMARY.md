---
phase: 03-summarization
plan: 02
subsystem: cli-integration
tags: [cli, summarization, user-experience, output-formatting, quality-gate]
dependency_graph:
  requires: [phase-03-01-summarization-engine, phase-02-transcriber]
  provides: [complete-cli-pipeline, user-facing-summarization]
  affects: [end-user-workflow]
tech_stack:
  added: []
  patterns: [fail-fast-validation, graceful-degradation, auto-detection]
key_files:
  created: []
  modified:
    - transcribe/formatter.py
    - transcribe/cli.py
decisions:
  - "Output naming: _notes.md with summary, _transcript.md without (user decision from context)"
  - "Fail fast: Check API key before transcription to avoid wasted work"
  - "Auto-detect summary style when --style not specified using keyword heuristics"
  - "Graceful fallback to transcript-only on summarization failure or user cancellation"
  - "Display summary cost to user for transparency"
metrics:
  duration_minutes: 2
  tasks_completed: 2
  files_created: 0
  files_modified: 2
  commits: 2
  completed_date: 2026-03-02
---

# Phase 03 Plan 02: CLI Integration Summary

Integrated summarization into CLI with style selection, quality gate, and graceful fallback - users can now generate AI summaries with one command.

## Objectives Achieved

Completed the user-facing integration of summarization into the CLI, delivering a seamless experience from video file to notes file. The implementation provides:

1. **Combined Output Formatting**: Created `format_notes()` function in formatter.py that produces markdown with summary at top and full transcript below. Metadata includes source, date, duration, language, summary style, and cost. Reuses existing helper functions (merge_segments_to_paragraphs, format_timestamp_adaptive) for consistency.

2. **CLI Flags and Options**: Added `--no-summary` flag to skip summarization (default: enabled) and `--style` option to choose from executive, action-items, or detailed styles. Updated help text and docstring to reflect new summarization capabilities.

3. **Smart Output Naming**: Output file automatically named based on content - `_notes.md` when summary included, `_transcript.md` when not. Users can instantly see what type of output they have.

4. **Fail-Fast Validation**: API key checked before transcription starts. If ANTHROPIC_API_KEY not set, tool exits immediately with clear setup instructions, avoiding wasted transcription work.

5. **Auto-Detection**: When user doesn't specify `--style`, tool analyzes transcript content using keyword heuristics from Phase 03-01. Detects action-oriented meetings, technical deep-dives, or general content. Displays selected style to user for transparency.

6. **Quality Gate Integration**: Applies 40% confidence threshold from Phase 03-01. In interactive mode, prompts user to confirm low-confidence summarization. In quiet mode, proceeds automatically with disclaimer. Both modes prepend warning to summary when confidence low.

7. **Cost Transparency**: Displays summary cost after generation (`Summary cost: ~$X.XX`). Users can make informed decisions about API usage.

8. **Graceful Degradation**: Multiple fallback paths ensure users always get usable output:
   - Summarization fails -> save transcript only
   - User cancels at quality gate -> save transcript only
   - API error -> catch exception, display error, save transcript only
   - Output path automatically reverts to `_transcript.md` on fallback

## Tasks Completed

### Task 1: Add combined summary+transcript formatting to formatter
**Commit:** 07a39ba
**Files:** transcribe/formatter.py

Added `format_notes()` function that produces the combined output structure:
- Header with "Meeting Notes" title
- Metadata: source, date, duration, language, summary style, cost (if provided)
- Summary section with AI-generated content
- Full transcript section with word count, reading time, confidence, model, and timestamped paragraphs

Implementation reuses existing formatter helpers:
- `merge_segments_to_paragraphs()` for natural pause detection
- `format_timestamp_adaptive()` for MM:SS or H:MM:SS based on duration
- Word count and reading time calculation (180 WPM)

Kept `format_transcript()` unchanged for backward compatibility. Both functions available for import.

### Task 2: Integrate summarization into CLI with style selection and quality gate
**Commit:** fc4f31b
**Files:** transcribe/cli.py

Updated CLI to support full summarization pipeline:

**New imports:**
- `from transcribe.summarizer import check_api_key, summarize_with_quality_gate`
- `from transcribe.prompts import detect_summary_style`
- `from transcribe.formatter import format_transcript, format_notes`

**New CLI options:**
- `--no-summary` flag: Skip summarization, produce transcript only (default: summarization ON)
- `--style` option: Choose from executive, action-items, detailed (default: None = auto-detect)

**Processing flow changes:**

1. **Pre-validation (fail fast):** Check API key before transcription if `not no_summary`. Exit with clear error if missing.

2. **Output path logic:** Set initial output path based on `no_summary` flag:
   - If `no_summary`: `{stem}_transcript.md`
   - If summarization enabled: `{stem}_notes.md`

3. **Build transcript text:** Extract `all_text` from segments for word count and style detection.

4. **Stage 5 - Summarization:**
   - Detect language from info object (defaults to 'en')
   - Auto-detect style if `--style` not specified, display selected style to user
   - Display "Generating summary..." message
   - Call `summarize_with_quality_gate()` with transcript, confidence, style, language, quiet flag
   - If attempted and summary returned:
     - Format as notes using `format_notes()`
     - Write to `_notes.md` path
     - Display cost to user
   - If summarization skipped (quality gate declined) or failed:
     - Revert output path to `_transcript.md`
     - Format using `format_transcript()`
     - Write transcript-only output
   - Wrap in try/except to catch API errors -> graceful fallback

5. **--no-summary path:** Format using `format_transcript()` and write to `_transcript.md`

6. **Success message:** Display "Notes saved to:" when summary included, "Transcript saved to:" when not

**Error handling:**
- API key check failures exit with RuntimeError message
- Anthropic API errors caught and display "Summarization failed" with fallback
- Quality gate user cancellation handled by returning empty summary with attempted=False

**Help text updated:**
- Docstring: "Transcribe and summarize a video file."
- Examples include all 4 flags: default, --style, --no-summary, -q

## Deviations from Plan

None - plan executed exactly as written.

## Verification Results

All planned verifications passed:

1. CLI help shows --style and --no-summary options - PASSED
2. All imports resolve without errors - PASSED
3. format_notes produces markdown with summary section at top - PASSED (verified structure in code)
4. format_transcript still works unchanged - PASSED (backward compatible)
5. --no-summary produces _transcript.md naming - PASSED (verified in code logic)
6. Default (no flags) produces _notes.md naming - PASSED (verified in code logic)

## Success Criteria Met

- [x] CLI has --style (executive|action-items|detailed) and --no-summary flags
- [x] API key validated before transcription starts (fail fast)
- [x] Summary style auto-detected when --style not specified
- [x] Quality gate prompts user on low confidence (< 40%), quiet mode auto-proceeds
- [x] Output file: _notes.md with summary at top + transcript below (or _transcript.md without summary)
- [x] Cost displayed after summarization: "Summary cost: ~$X.XX"
- [x] Graceful fallback to transcript-only on summarization failure

## Integration Points

**Provides to End Users:**
- Complete video-to-notes pipeline in single command
- Choice of summary styles via --style flag or auto-detection
- Opt-out via --no-summary for transcript-only use case
- Cost transparency for API usage tracking

**Depends on Phase 03-01:**
- `summarize_with_quality_gate()` as main entry point
- `detect_summary_style()` for auto-detection
- `check_api_key()` for pre-validation
- Cost tracking from summarizer (returned in tuple)

**Depends on Phase 02:**
- `confidence_pct` from transcriber quality validation
- `info.language` for language-matched summary prompts
- `segments` for transcript text extraction
- All existing transcriber pipeline (extraction, chunking, parallel processing)

## Notes

**User workflow:**

Default (recommended):
```bash
transcribe meeting.mp4
# -> Auto-detects style, generates summary, saves to meeting_notes.md
```

Explicit style:
```bash
transcribe meeting.mp4 --style action-items
# -> Forces action-items style, saves to meeting_notes.md
```

Transcript only:
```bash
transcribe meeting.mp4 --no-summary
# -> Skips summarization, saves to meeting_transcript.md
```

Quiet automation:
```bash
transcribe meeting.mp4 -q
# -> No progress output, auto-proceeds on low confidence with disclaimer
```

**Fallback paths:**
1. Quality gate declined -> save transcript only, change path to _transcript.md
2. Summarization error -> catch exception, display error, save transcript only
3. API key missing -> exit immediately before transcription (fail fast)

**Output file structure (_notes.md):**
```markdown
# Meeting Notes

**Source:** meeting.mp4
**Date:** 2026-03-02 14:30:00
**Duration:** 15m 30s
**Language:** en (confidence: 99.8%)
**Summary style:** executive
**Summary cost:** ~$0.05

---

## Summary

[AI-generated summary content]

---

## Full Transcript

**Word count:** 2500
**Reading time:** ~14 min
**Confidence:** 85%
**Model:** faster-whisper (small)

[Timestamped paragraphs]
```

**Cost estimation for users:**
- Typical 30-minute meeting (~4500 words): ~$0.02-0.05 per summary
- 1-hour technical discussion (~9000 words): ~$0.05-0.10 per summary
- 2+ hour recordings may trigger map-reduce: ~$0.10-0.25 per summary

**Quality gate behavior:**
- Confidence >= 40%: Summarize normally
- Confidence < 40%, interactive mode: Prompt user with click.confirm()
- Confidence < 40%, quiet mode: Auto-proceed with disclaimer prepended
- User cancels: Return empty summary, fall back to transcript-only

## Self-Check: PASSED

Verified created files exist:
```
No new files created (modifications only)
```

Verified modified files exist:
```
FOUND: transcribe/formatter.py
FOUND: transcribe/cli.py
```

Verified commits exist:
```
FOUND: 07a39ba (Task 1 - format_notes function)
FOUND: fc4f31b (Task 2 - CLI integration)
```

All claims in summary verified against actual implementation.
