---
phase: 04-polish-resilience
plan: 01
subsystem: error-handling-resilience
tags: [error-handling, retry-logic, validation, user-experience]
dependency_graph:
  requires:
    - CLI-03
  provides:
    - error-hierarchy
    - retry-decorators
    - enhanced-validation
  affects:
    - all-modules
tech_stack:
  added:
    - tenacity>=9.0.0
  patterns:
    - custom-exception-hierarchy
    - retry-with-exponential-backoff
    - ffmpeg-probe-validation
key_files:
  created:
    - transcribe/errors.py
    - transcribe/retry.py
  modified:
    - transcribe/validators.py
    - transcribe/summarizer.py
    - transcribe/extractor.py
    - pyproject.toml
decisions:
  - key: retry-strategy
    choice: tenacity with exponential backoff for API, fixed delay for FFmpeg
    rationale: API failures are often rate-limit/network (need backoff), FFmpeg failures are usually permanent (short retry sufficient)
  - key: error-display
    choice: display() method with click.style for colored output
    rationale: User-friendly terminal output with clear error/suggestion distinction
  - key: validation-strategy
    choice: FFmpeg probe after extension check
    rationale: Cheap check first (extension), expensive validation second (probe)
metrics:
  duration_minutes: 4.2
  tasks_completed: 2
  files_created: 2
  files_modified: 4
  commits: 2
  completed_date: 2026-03-03
---

# Phase 04 Plan 01: Error Handling and Resilience Foundation Summary

**One-liner:** Custom exception hierarchy with actionable error messages, FFmpeg probe validation, and retry decorators with exponential backoff (4-60s, 5 attempts) for transient API failures.

## What Was Built

Created a robust error handling and resilience layer for the transcription tool:

1. **Custom Exception Hierarchy** (`transcribe/errors.py`):
   - `TranscriptionError` base class with `display()` method for user-friendly terminal output
   - 7 specific exception subclasses (FileValidationError, NoAudioStreamError, CorruptedFileError, UnsupportedFormatError, APIKeyMissingError, APIRetryExhaustedError, FFmpegNotFoundError)
   - All exceptions provide clear error message + actionable suggestion
   - Color-coded output using click.style (red for errors, yellow for suggestions)

2. **Enhanced File Validation** (`transcribe/validators.py`):
   - Added FFmpeg probe validation to check file integrity before processing
   - Audio stream detection to catch videos without audio tracks early
   - Replaced generic RuntimeError/ValueError with specific exception types
   - Two-stage validation: extension check (cheap) then FFmpeg probe (expensive)

3. **Retry Logic** (`transcribe/retry.py`):
   - `api_retry` decorator: exponential backoff 4-60s with jitter, 5 attempts, only retries transient OpenAI errors (RateLimitError, APIConnectionError, APITimeoutError)
   - `ffmpeg_retry` decorator: fixed 2s delay, 3 attempts, only OS-level I/O errors
   - Retry attempts logged to stderr to keep users informed
   - Non-transient errors (auth failures, invalid requests) are NOT retried

4. **Integration**:
   - `summarizer.py`: Wrapped API calls with @api_retry, updated to use APIKeyMissingError
   - `extractor.py`: Wrapped extract_audio with @ffmpeg_retry, updated to use custom error classes
   - `pyproject.toml`: Added tenacity>=9.0.0 dependency

## Task Breakdown

### Task 1: Custom Exception Hierarchy and Enhanced File Validation
**Commit:** 6b36ccb
**Files:** transcribe/errors.py (created), transcribe/validators.py (modified)
**Duration:** ~2 minutes

Created complete exception hierarchy with display() method and updated validators to use FFmpeg probe for file integrity validation. All error classes provide message + suggestion fields.

### Task 2: Retry Logic and Integration
**Commit:** 3a0d953
**Files:** transcribe/retry.py (created), transcribe/summarizer.py, transcribe/extractor.py, pyproject.toml (modified)
**Duration:** ~2 minutes

Added tenacity dependency, created retry decorators, and wired them into summarizer and extractor modules. API calls retry with exponential backoff, FFmpeg operations retry with fixed delay.

## Deviations from Plan

None - plan executed exactly as written.

## Verification Results

All verifications passed:
- All new modules (errors.py, retry.py) importable without errors
- Enhanced validators.py uses FFmpeg probe for validation
- summarizer.py and extractor.py use retry decorators and custom exceptions
- tenacity 9.1.4 installed and declared in pyproject.toml
- Error classes all have message + suggestion fields
- Retry only targets transient errors (rate limit, connection, timeout, I/O)
- Non-transient errors (auth, validation) are NOT retried

## Technical Details

### Exception Hierarchy Design
```
TranscriptionError (base)
├── FileValidationError (generic validation failure)
├── NoAudioStreamError (missing audio track)
├── CorruptedFileError (unreadable file)
├── UnsupportedFormatError (wrong extension)
├── APIKeyMissingError (missing OPENAI_API_KEY)
├── APIRetryExhaustedError (all retries failed)
└── FFmpegNotFoundError (FFmpeg not installed)
```

### Retry Configuration

**API Retry:**
- Transient errors only: RateLimitError, APIConnectionError, APITimeoutError
- Wait strategy: exponential backoff with jitter (4-60 seconds)
- Max attempts: 5
- Logs each retry attempt to stderr

**FFmpeg Retry:**
- OS errors only: OSError, IOError
- Wait strategy: fixed 2-second delay
- Max attempts: 3
- No logging (fast failures expected)

### Validation Flow

1. Check file exists (FileNotFoundError)
2. Check is file (ValueError)
3. Check extension against allowed list (UnsupportedFormatError)
4. FFmpeg probe to validate integrity (CorruptedFileError)
5. Check for audio stream (NoAudioStreamError)
6. Return probe info for optional use by caller

## Impact

This plan provides the foundation for robust error handling throughout the tool:
- Users get clear, actionable error messages instead of stack traces
- API failures are automatically retried with backoff, reducing transient failure impact
- File validation catches corrupt/invalid files before expensive processing
- All error paths now use consistent exception types for easier handling

## Next Steps

Phase 04 Plan 02 will add progress indicators, implement quiet mode, and add color-coded status output using the error display foundation built here.

## Self-Check: PASSED

Verified created files exist:
- transcribe/errors.py: FOUND
- transcribe/retry.py: FOUND

Verified commits exist:
- 6b36ccb: FOUND (Task 1 - exception hierarchy and validation)
- 3a0d953: FOUND (Task 2 - retry logic and integration)

All claims verified successfully.
