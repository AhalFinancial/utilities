---
status: passed
phase: 03-summarization
source: [03-01-SUMMARY.md, 03-02-SUMMARY.md]
started: 2026-03-03T00:00:00Z
updated: 2026-03-03T00:00:00Z
---

## Current Test
<!-- OVERWRITE each test - shows where we are -->

number: 7
name: Cost Display
expected: |
  After summarization completes, the tool displays the API cost (e.g., "Summary cost: ~$0.02") so the user knows what the summary cost them.
result: pass

## Tests

### 1. CLI Help with New Flags
expected: Running `transcribe --help` shows the new --style option (with choices: executive, action-items, detailed) and --no-summary flag alongside existing options.
result: pass

### 2. Default Summarization (Auto-Detect Style)
expected: Running `transcribe <video.mp4>` with OPENAI_API_KEY set produces a `<video>_notes.md` file (not _transcript.md). Output includes a summary section at the top with key takeaways, followed by the full transcript below. Console shows detected language, transcription progress, and "Summary cost: ~$X.XX" after completion.
result: pass

### 3. Explicit Style Override
expected: Running `transcribe <video.mp4> --style action-items` produces a summary focused on action items (tasks, owners, deadlines) rather than the default executive style.
result: pass

### 4. No-Summary Mode
expected: Running `transcribe <video.mp4> --no-summary` produces a `<video>_transcript.md` file (not _notes.md) with only the transcript and no summary section. No OpenAI API call is made.
result: pass

### 5. Missing API Key Error
expected: Running `transcribe <video.mp4>` without OPENAI_API_KEY set shows a clear error message about the missing key with instructions on how to set it. Fails fast before transcription starts.
result: pass

### 6. Summary Language Matches Transcript
expected: When processing a Spanish-language video, the summary is generated in Spanish (matching the detected transcript language), not English.
result: pass

### 7. Cost Display
expected: After summarization completes, the tool displays the API cost (e.g., "Summary cost: ~$0.02") so the user knows what the summary cost them.
result: pass

## Summary

total: 7
passed: 7
issues: 0
pending: 0
skipped: 0

## Gaps

[none]
