---
phase: 01-foundation-pipeline
plan: 03
subsystem: user-interface
tags:
  - cli
  - click
  - pipeline-integration
  - error-handling
  - user-experience
dependency_graph:
  requires:
    - audio-extraction-api (01-02)
    - whisper-transcription-api (01-02)
    - markdown-formatting-api (01-02)
    - validation-api (01-01)
  provides:
    - transcribe-cli-command
    - end-to-end-pipeline
  affects:
    - future CLI enhancements (batch processing, summarization)
tech_stack:
  added:
    - click (CLI framework)
  patterns:
    - fail-fast-validation (check environment before processing)
    - two-stage-pipeline-with-cleanup (extract → transcribe → cleanup)
    - simple-text-progress (click.echo for status updates)
    - file-overwrite-protection (confirm prompt + --force bypass)
key_files:
  created:
    - transcribe/cli.py (Click CLI command with full integration)
  modified: []
decisions:
  - Use Click framework for CLI (industry standard, clean argument/option handling)
  - Command name 'transcribe' with positional video_file argument
  - Simple text progress (click.echo) rather than progress bars for Phase 1
  - Automatic output naming (video.mp4 → video_transcript.md in same directory)
  - File overwrite protection with confirm prompt unless --force used
  - Temp file cleanup with try/finally pattern for reliability
metrics:
  duration: 142 seconds
  completed: 2026-03-02T22:28:48Z
  tasks: 2
  files: 1
---

# Phase 01 Plan 03: CLI Integration Summary

**One-liner:** Complete Click-based CLI tool integrating validation, extraction, transcription, and formatting into a single 'transcribe' command with progress display and error handling

## Overview

Implemented the final CLI layer that ties together all Phase 1 components (validation, audio extraction, Whisper transcription, markdown formatting) into a user-friendly command-line tool. The tool validates the environment, processes video files through a two-stage pipeline, displays progress, handles file existence, and outputs timestamped markdown transcripts.

## What Was Built

### CLI Interface (`transcribe/cli.py`)

**Purpose:** Provide a simple, reliable command-line interface for video transcription

**Command syntax:**
```bash
transcribe VIDEO_FILE [-q] [--force]
```

**Key features:**

**1. Argument and Options Handling:**
- Positional `video_file` argument with path validation (must exist)
- `--quiet` / `-q` flag to suppress progress output
- `--force` flag to overwrite existing output without confirmation

**2. Fail-Fast Validation Pattern:**
- Validates FFmpeg availability before processing (`validate_environment()`)
- Validates video file format and readability (`validate_video_file()`)
- Clear error messages with sys.exit(1) on validation failure

**3. Automatic Output Path Construction:**
- Pattern: `video.mp4` → `video_transcript.md`
- Output saved in same directory as source video
- File existence check with confirmation prompt: "video_transcript.md exists. Overwrite? [y/N]:"
- `--force` flag bypasses confirmation

**4. Two-Stage Pipeline with Cleanup:**
- Stage 1: Extract audio to temp WAV file (FFmpeg via extractor)
- Stage 2: Transcribe temp audio (faster-whisper via Transcriber)
- Format transcript to markdown with metadata header
- Write output file
- Cleanup: Delete temp audio in try/finally block (guaranteed cleanup even on error)

**5. Progress Display:**
- Default: Shows "Extracting audio...", "Transcribing...", "Transcript saved to: {path}"
- `--quiet` mode: Only shows final "Transcript saved to:" message
- Uses simple text (click.echo) rather than progress bars for Phase 1 simplicity

**6. Comprehensive Error Handling:**
- Known errors (FileNotFoundError, ValueError, RuntimeError): User-friendly messages
- FFmpeg missing: Clear error from validation with install instructions
- Corrupted files: Friendly message from extractor
- Unexpected errors: Generic message with troubleshooting suggestion
- All errors exit with status code 1

**7. Entry Point:**
- `if __name__ == '__main__':` guard for direct script execution
- Also works via installed entry point (setup.py console_scripts)

**Exports:** `main()` Click command

## Deviations from Plan

None - plan executed exactly as written.

CLI implementation followed all specifications from PLAN.md and user decisions from CONTEXT.md:
- Click framework for clean CLI structure
- 'transcribe' command name with positional argument
- Progress display (suppressible with --quiet)
- File overwrite handling (prompt + --force bypass)
- FFmpeg validation on startup
- Two-stage pipeline with temp file cleanup
- Automatic output naming in source directory

## Verification Results

**Checkpoint verification (human-verify) approved by user.**

User tested the complete pipeline with real video files and confirmed:

1. Help display works (`transcribe --help`)
2. FFmpeg validation catches missing FFmpeg with clear error
3. Basic transcription works end-to-end (extract → transcribe → save)
4. Output file naming follows pattern (video.mp4 → video_transcript.md)
5. Transcript contains complete metadata header and timestamped text
6. File existence handling prompts for confirmation
7. `--force` flag bypasses confirmation
8. `--quiet` flag suppresses progress messages
9. Format support works for MP4, MKV, WebM, AVI
10. Error handling provides clear messages for invalid inputs
11. Transcript quality is good (proper formatting, timestamps, language detection)

## Success Criteria Met

- [x] CLI command 'transcribe' is accessible from shell
- [x] Help text displays with --help flag
- [x] Tool processes video files end-to-end (extract → transcribe → format → save)
- [x] Output file naming is automatic (video.mp4 → video_transcript.md) in source directory
- [x] Progress is shown by default, suppressed with --quiet
- [x] File existence prompts for confirmation unless --force used
- [x] FFmpeg validation runs on startup with clear install instructions if missing
- [x] All four video formats (MP4, MKV, WebM, AVI) are supported
- [x] Transcript includes metadata header with all required fields
- [x] Timestamps follow [HH:MM:SS] format
- [x] Language detection works for Spanish and English
- [x] User verification confirms transcript quality and functionality

## Phase 1 Completion

This plan completes Phase 1 (Foundation Pipeline). The transcription tool is now fully functional and meets all user requirements:

**User can now:**
1. Run `transcribe video.mp4` from any directory
2. Get a readable markdown transcript (`video_transcript.md`) in the same folder
3. See progress during processing
4. Trust the tool to handle errors gracefully
5. Process MP4, MKV, WebM, and AVI video files
6. Get properly formatted transcripts with metadata and timestamps
7. Work with Spanish and English audio

**Core value delivered:** "Drop a video, get a readable text file"

## Next Steps

Phase 1 is complete. Future phases will add:
- **Phase 2:** Smart chunking for longer videos (30+ min)
- **Phase 3:** Claude API integration for summaries
- **Phase 4:** Batch processing and enhanced CLI features

## Technical Notes

**Fail-Fast Validation:** Running `validate_environment()` and `validate_video_file()` before any processing catches common issues early (missing FFmpeg, invalid files) and provides actionable error messages before consuming time/resources on extraction.

**Temp File Cleanup Pattern:** Using `try/finally` with tempfile.NamedTemporaryFile(delete=False) ensures temp audio files are cleaned up even if transcription fails mid-process. This prevents temp file accumulation on repeated errors.

**Simple Text Progress:** Using click.echo for progress rather than click.progressbar avoids complexity of indeterminate progress bars during transcription (Whisper doesn't provide progress callbacks for small models). Text status updates ("Extracting...", "Transcribing...") provide sufficient user feedback for 5-10 min videos.

**Click Path Validation:** Using `type=click.Path(exists=True)` on the video_file argument provides automatic existence validation before main() executes, ensuring the file is present before any processing begins.

**Error Exit Codes:** All error paths use sys.exit(1) to signal failure to shell, enabling proper error handling in scripts and pipelines that might wrap the transcribe command.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | 194fad4 | feat(01-03): implement Click CLI with full pipeline integration |

## Self-Check: PASSED

All claimed files and commits verified:
- ✓ transcribe/cli.py exists
- ✓ Commit 194fad4 exists
- ✓ CLI imports all required modules (validators, extractor, transcriber, formatter)
- ✓ Click decorators present (@click.command, @click.argument, @click.option)
- ✓ Two-stage pipeline with cleanup implemented
- ✓ User verification checkpoint passed

---

**Phase:** 01-foundation-pipeline
**Plan:** 03 of 03
**Status:** Complete
**Duration:** 2 minutes 22 seconds
