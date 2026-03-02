# Roadmap: Video-to-Summary CLI

## Overview

This roadmap delivers a production-ready CLI tool for extracting transcripts and summaries from meeting recordings. The journey progresses through four phases: establishing the core pipeline (audio extraction and basic transcription), making transcription production-ready for long videos with quality safeguards, adding AI-powered summarization, and finishing with error handling and UX polish. Each phase delivers verifiable user value, building toward the goal of "drop a video, get a readable text file with what was said and the key takeaways."

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3, 4): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Foundation Pipeline** - Audio extraction and basic transcription working
- [ ] **Phase 2: Production Transcription** - Reliable processing of long videos with quality validation
- [ ] **Phase 3: Summarization** - AI-powered summaries with quality safeguards
- [ ] **Phase 4: Polish & Resilience** - Error handling and production-ready UX

## Phase Details

### Phase 1: Foundation Pipeline
**Goal**: Establish core data flow from video file to text transcript
**Depends on**: Nothing (first phase)
**Requirements**: AUDIO-01, AUDIO-02, TRANS-01, CLI-01
**Success Criteria** (what must be TRUE):
  1. User can run CLI command with a video file path and get a text transcript
  2. Tool processes MP4, MKV, WebM, and AVI formats successfully
  3. Output file is automatically named based on source video (video.mp4 → video_transcript.md)
  4. Basic transcription works for short videos (5-10 minutes) in Spanish and English
**Plans**: 3 plans

Plans:
- [ ] 01-01-PLAN.md — Project foundation, dependencies, and validation logic
- [ ] 01-02-PLAN.md — Core pipeline: audio extraction, transcription, and formatting
- [ ] 01-03-PLAN.md — CLI interface with progress display and file handling

### Phase 2: Production Transcription
**Goal**: Reliable transcription for real-world usage (long videos, quality validation)
**Depends on**: Phase 1
**Requirements**: TRANS-02, TRANS-03, TRANS-04, CLI-02
**Success Criteria** (what must be TRUE):
  1. User can transcribe videos from 5 minutes to 3+ hours without quality degradation
  2. Transcript includes timestamps for navigation back to specific moments
  3. Tool displays progress bar during processing so user knows work is happening
  4. Tool auto-detects Spanish and English audio and produces accurate transcripts
  5. Long videos are processed using smart chunking with silence detection
**Plans**: 3 plans

Plans:
- [ ] 02-01-PLAN.md — Audio chunking with silence detection and overlap deduplication
- [ ] 02-02-PLAN.md — Transcriber language detection/quality validation and formatter upgrades
- [ ] 02-03-PLAN.md — Parallel processing, progress display, and CLI integration

### Phase 3: Summarization
**Goal**: AI-powered summaries that extract key points from transcripts
**Depends on**: Phase 2
**Requirements**: SUMM-01, SUMM-02, SUMM-03
**Success Criteria** (what must be TRUE):
  1. User gets AI-generated summary with key points and decisions in the output file
  2. User can choose summary style (executive, action items, or detailed) via CLI flag
  3. Tool skips summarization when transcript quality is detected as low (prevents garbage summaries)
  4. Output file contains both full transcript and summary sections
**Plans**: TBD

Plans:
- [ ] 03-01: TBD
- [ ] 03-02: TBD

### Phase 4: Polish & Resilience
**Goal**: Production-ready tool with robust error handling and excellent UX
**Depends on**: Phase 3
**Requirements**: CLI-03
**Success Criteria** (what must be TRUE):
  1. Tool provides clear error messages when files are missing, corrupt, or unsupported
  2. Tool retries API failures with exponential backoff (no crashes mid-processing)
  3. User can resume interrupted processing of long videos without starting over
  4. Tool validates input files before processing and rejects invalid formats early
**Plans**: TBD

Plans:
- [ ] 04-01: TBD
- [ ] 04-02: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation Pipeline | 0/3 | Not started | - |
| 2. Production Transcription | 0/3 | Not started | - |
| 3. Summarization | 0/2 | Not started | - |
| 4. Polish & Resilience | 0/2 | Not started | - |

---
*Roadmap created: 2026-03-02*
*Depth: quick (4 phases, 9 plans estimated)*
