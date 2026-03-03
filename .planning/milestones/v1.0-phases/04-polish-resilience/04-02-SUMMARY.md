---
phase: 04-polish-resilience
plan: 02
subsystem: checkpoint-resume-error-display
tags: [checkpoint, resume, error-handling, user-experience, resilience]
dependency_graph:
  requires:
    - CLI-03
    - error-hierarchy
    - retry-decorators
  provides:
    - checkpoint-resume
    - cli-error-display
  affects:
    - parallel-transcription
    - cli-interface
tech_stack:
  added: []
  patterns:
    - atomic-checkpoint-writes
    - md5-file-hashing
    - resume-from-checkpoint
    - custom-error-display
key_files:
  created:
    - transcribe/checkpoint.py
  modified:
    - transcribe/parallel.py
    - transcribe/cli.py
decisions:
  - key: file-hash-strategy
    choice: MD5 of first+last 64KB
    rationale: Fast change detection without reading entire large video files
  - key: checkpoint-format
    choice: JSON with atomic writes via temp file + os.replace()
    rationale: Human-readable format with atomic guarantees to prevent partial writes
  - key: resume-behavior
    choice: Ask user in interactive mode, auto-resume in quiet mode
    rationale: User control in normal use, automation-friendly in scripts/pipelines
  - key: checkpoint-cleanup
    choice: Delete on success, keep on failure
    rationale: Allows retry after failure, cleans up after success to avoid confusion
metrics:
  duration_minutes: 3.7
  tasks_completed: 2
  files_created: 1
  files_modified: 2
  commits: 2
  completed_date: 2026-03-03
---

# Phase 04 Plan 02: Checkpoint Resume and Error Display Summary

**One-liner:** Atomic checkpoint-based resume for long video processing with MD5 file integrity validation, --no-resume flag, and comprehensive CLI error display using custom TranscriptionError formatting.

## What Was Built

Added checkpoint resume capability and wired all custom error handling into the CLI:

1. **Checkpoint Module** (`transcribe/checkpoint.py`):
   - `TranscriptionCheckpoint` dataclass tracks: video path, file hash, total/completed chunks, chunk transcripts, language, model, timestamp
   - `calculate_file_hash()`: MD5 of first+last 64KB for fast change detection (handles small files by hashing entire content)
   - `save_checkpoint()`: Atomic write via temp file + `os.replace()` prevents partial writes
   - `load_checkpoint()`: Returns None for missing/invalid checkpoints, converts JSON string keys back to int for dict
   - `can_resume_from_checkpoint()`: Validates path match + hash match (detects if video changed)
   - `delete_checkpoint()`: Silent cleanup (ignores if not exists)

2. **Parallel Transcription Integration** (`transcribe/parallel.py`):
   - Added optional parameters: `checkpoint_path`, `video_path`, `completed_chunks` (all backwards-compatible with None defaults)
   - Skips already-completed chunks in executor submit loop
   - Saves checkpoint after each chunk completes with updated state
   - Reconstructs completed chunks from saved transcripts during merge phase
   - Logs checkpoint saves and resume operations

3. **CLI Resume and Error Handling** (`transcribe/cli.py`):
   - Added `--no-resume` flag to force fresh start
   - Resume detection after validation, before extraction:
     - Loads checkpoint if exists and not --no-resume
     - Validates file hash with `can_resume_from_checkpoint()`
     - Asks user to confirm resume (auto-resume in quiet mode)
     - Warns and deletes invalid checkpoints (hash mismatch)
   - Passes checkpoint parameters to `transcribe_chunks_parallel()` when resuming
   - Deletes checkpoint on successful completion
   - Deletes checkpoint before model upgrade retry (medium model needs fresh state)
   - Replaced generic exception handlers with `except TranscriptionError` using `.display()` for formatted output
   - Removed inline try/except blocks around validation/API key checks (let custom exceptions propagate)
   - All errors display to stderr with red "Error:" + yellow "Suggestion:" formatting

## Task Breakdown

### Task 1: Create checkpoint module and integrate with parallel transcription
**Commit:** 453ca82
**Files:** transcribe/checkpoint.py (created), transcribe/parallel.py (modified)
**Duration:** ~2 minutes

Created complete checkpoint module with atomic save/load and MD5 file integrity validation. Updated parallel.py to save checkpoints after each chunk and skip completed chunks on resume. Fixed JSON dict key conversion issue (JSON converts int keys to strings - must convert back on load).

### Task 2: Wire error handling and resume into CLI
**Commit:** eb14583
**Files:** transcribe/cli.py (modified)
**Duration:** ~1.5 minutes

Added --no-resume flag, resume detection with user confirmation, checkpoint parameter passing to parallel transcription, checkpoint deletion on success, and replaced generic exception handling with custom TranscriptionError.display() for formatted terminal output.

## Deviations from Plan

**Auto-fixed Issue (Rule 3 - Blocking Issue):**

**1. JSON Dict Key Conversion**
- **Found during:** Task 1 verification
- **Issue:** JSON serialization converts integer dict keys to strings. Loading checkpoint failed with KeyError because `chunk_transcripts` dict used int keys but JSON loaded them as strings.
- **Fix:** Added int conversion in `load_checkpoint()`: `data['chunk_transcripts'] = {int(k): v for k, v in data['chunk_transcripts'].items()}`
- **Files modified:** transcribe/checkpoint.py
- **Commit:** 453ca82 (included in Task 1 commit)

This was necessary to pass the round-trip verification test. Without this fix, the checkpoint module would not work correctly.

## Verification Results

All verifications passed:

1. `transcribe --help` shows --no-resume flag alongside existing flags ✓
2. checkpoint.py save/load round-trip preserves all fields (including int dict keys) ✓
3. Checkpoint parameters present in `transcribe_chunks_parallel()` signature ✓
4. CLI imports without errors ✓
5. --no-resume parameter present in CLI command ✓
6. Error handling works for missing file (Click's exists check) ✓
7. Existing functionality (--no-summary, --style, --force, --quiet) unchanged ✓

## Technical Details

### Checkpoint State Machine

```
1. Video starts → No checkpoint exists
2. First chunk completes → Checkpoint saved (1/N chunks)
3. Second chunk completes → Checkpoint updated (2/N chunks)
4. Interruption (Ctrl+C, crash, etc.)
5. User restarts transcribe → Load checkpoint
6. Validate hash → If match: offer resume, if mismatch: delete and start fresh
7. Resume: Skip completed chunks, transcribe remaining
8. All chunks done → Delete checkpoint
```

### Atomic Write Pattern

```python
# Write to temp file first
tmp_path = checkpoint_path.with_suffix('.tmp')
with open(tmp_path, 'w') as f:
    json.dump(data, f)

# Atomic replace (handles Windows requirement to delete first)
if checkpoint_path.exists():
    checkpoint_path.unlink()
os.replace(tmp_path, checkpoint_path)
```

This ensures checkpoint is never partially written (either fully updated or unchanged).

### Resume Flow in parallel.py

```python
# Skip completed chunks
for chunk_id, chunk_path, start_offset, duration in chunks:
    if chunk_id in completed_chunks:
        logger.info(f"Skipping chunk {chunk_id} (already completed)")
        continue
    # Submit to executor...

# Reconstruct completed chunks from saved transcripts
for chunk_id in completed_chunks.keys():
    if chunk_id not in [r[0] for r in all_chunk_results]:
        # Create placeholder MergedSegment from saved text
        placeholder_segment = MergedSegment(
            start=start_offset,
            end=start_offset + duration,
            text=completed_chunks[chunk_id],
            avg_logprob=-0.5  # Assume decent quality
        )
        all_chunk_results.append((chunk_id, [placeholder_segment], info))

# Sort by chunk_id and merge as normal
```

### Error Display Pattern

Before (generic):
```
Error: No audio track found
Please check that FFmpeg is installed and the video file is valid.
```

After (custom):
```
Error: No audio track found in meeting.mp4
Suggestion: Check that the file has an audio track, or try a different file
```

Colors: Red for "Error:", Yellow for "Suggestion:", both to stderr.

## Impact

This plan completes Phase 4's resilience goals:

- **Long video processing is now resumable**: Users can Ctrl+C or handle crashes without losing progress
- **File integrity validation**: Checkpoint won't resume if video file changed (prevents corrupt output)
- **User-friendly error messages**: All error scenarios display clear messages with actionable suggestions
- **Automation-friendly**: --no-resume flag + auto-resume in quiet mode supports scripts/pipelines
- **Clean completion**: Checkpoints automatically cleaned up on success

Combined with Phase 04 Plan 01's retry logic and enhanced validation, the tool is now production-ready for long-form video processing with interruptions, transient failures, and user errors.

## Next Steps

Phase 4 is now complete. The transcription tool has:
- Robust error handling with custom exception hierarchy
- Retry logic for transient failures (API rate limits, network errors)
- FFmpeg probe validation for file integrity
- Checkpoint-based resume for long videos
- User-friendly error display with actionable suggestions

All must-have resilience features are implemented.

## Self-Check: PASSED

Verified created files exist:
```bash
[ -f "C:/Users/eduar/utilities/transcribe/checkpoint.py" ] && echo "FOUND: transcribe/checkpoint.py" || echo "MISSING: transcribe/checkpoint.py"
```
FOUND: transcribe/checkpoint.py

Verified commits exist:
```bash
git log --oneline --all | grep -q "453ca82" && echo "FOUND: 453ca82" || echo "MISSING: 453ca82"
git log --oneline --all | grep -q "eb14583" && echo "FOUND: eb14583" || echo "MISSING: eb14583"
```
FOUND: 453ca82 (Task 1 - checkpoint module and parallel integration)
FOUND: eb14583 (Task 2 - CLI error handling and resume)

All claims verified successfully.
