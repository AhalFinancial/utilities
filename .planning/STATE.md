# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-02)

**Core value:** Reliable transcription and useful summaries from meeting recordings — drop a video, get a readable text file
**Current focus:** Phase 4 - Polish & Resilience

## Current Position

Phase: 4 of 4 (Polish & Resilience)
Plan: 2 of 2 in current phase
Status: In Progress
Last activity: 2026-03-03 — Completed 04-01-PLAN.md (Error handling and resilience foundation)

Progress: [█████████░] 67%

## Performance Metrics

**Velocity:**
- Total plans completed: 8
- Average duration: 2.8 minutes
- Total execution time: 0.4 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 3 | 8 min | 3 min |
| 02 | 3 | 7 min | 2.3 min |
| 03 | 2 | 6 min | 3 min |
| 04 | 1 | 4 min | 4 min |

**Recent Plans:**

| Plan | Duration | Tasks | Files | Completed |
|------|----------|-------|-------|-----------|
| Phase 02 P03 | 2 min | 2 tasks | 3 files | 2026-03-02 |
| Phase 03 P01 | 4 min | 2 tasks | 3 files | 2026-03-03 |
| Phase 03 P02 | 2 min | 2 tasks | 2 files | 2026-03-02 |
| Phase 04 P01 | 4 min | 2 tasks | 6 files | 2026-03-03 |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Python as implementation language (best ecosystem for audio/ML)
- Whisper for transcription (industry standard, supports multiple languages)
- Claude API for summarization (user preference, strong multilingual capabilities)
- CLI-first interface (simplest path to usable tool)
- [Phase 01-01]: Use hatchling as build backend (modern, simple PyPA-recommended system)
- [Phase 01-01]: Require system FFmpeg (not bundled) - PyAV only handles transcription
- [Phase 01-02]: Use small Whisper model for Phase 1 (461MB, good accuracy/speed balance)
- [Phase 01-02]: Default to CPU with int8 quantization (simplest, works everywhere)
- [Phase 01-03]: Use Click framework for CLI (industry standard, clean argument/option handling)
- [Phase 01-03]: Simple text progress (click.echo) rather than progress bars for Phase 1
- [Phase 02-01]: Use pydub for silence detection (industry standard, simple API)
- [Phase 02-01]: Target 20-25 second chunks for optimal Whisper processing
- [Phase 02-01]: 3-second overlap between chunks prevents boundary word loss
- [Phase 02-01]: Use difflib.SequenceMatcher for deduplication (built-in, reliable)
- [Phase 02-01]: Added audioop-lts for Python 3.13 compatibility (pydub dependency)
- [Phase 02-02]: VAD enabled by default with 500ms silence threshold to reduce hallucinations
- [Phase 02-02]: Quality threshold set at avg_logprob >= -1.0 for acceptability
- [Phase 02-02]: Auto-upgrade from small to medium model on low confidence (one retry only)
- [Phase 02-02]: Paragraph merging uses 2s gap threshold for natural pauses
- [Phase 02-02]: Adaptive timestamps: MM:SS for <1hr videos, H:MM:SS for >=1hr
- [Phase 02-02]: Confidence displayed as 0-100% using formula: (1 + avg_logprob) * 100
- [Phase 02-02]: Reading time calculated at 180 words/minute
- [Phase 02-03]: ProcessPoolExecutor for parallel chunk transcription (CPU-bound workload)
- [Phase 02-03]: Conservative max_workers: min(cpu_count, 4) for typical 8GB machines
- [Phase 02-03]: Two-stage progress display (extraction done, then transcription bar)
- [Phase 02-03]: Smart chunking - short videos skip chunking entirely
- [Phase 03-01]: Use Claude Sonnet 4.6 for summarization (balanced cost/quality at $3/M input, $15/M output)
- [Phase 03-01]: Set quality gate threshold at 40% confidence from Phase 2 transcription
- [Phase 03-01]: Use map-reduce strategy for transcripts >150K tokens (split at 50K token chunks)
- [Phase 03-01]: Auto-detect summary style using keyword heuristics (action items vs executive vs detailed)
- [Phase 03-02]: Output naming: _notes.md with summary, _transcript.md without (user decision from context)
- [Phase 03-02]: Fail fast: Check API key before transcription to avoid wasted work
- [Phase 03-02]: Auto-detect summary style when --style not specified using keyword heuristics
- [Phase 03-02]: Graceful fallback to transcript-only on summarization failure or user cancellation
- [Phase 04-01]: Use tenacity for retry logic with exponential backoff (4-60s, 5 attempts) for API calls
- [Phase 04-01]: Fixed 2s retry for FFmpeg operations (I/O failures usually permanent)
- [Phase 04-01]: Only retry transient errors (rate limit, connection, timeout) not auth/validation failures
- [Phase 04-01]: FFmpeg probe validation added for file integrity and audio stream detection before processing

### Pending Todos

None yet.

### Blockers/Concerns

None yet.

## Session Continuity

Last session: 2026-03-03
Stopped at: Completed 04-01-PLAN.md (Error handling and resilience foundation)
Resume file: None

---
*State initialized: 2026-03-02*
