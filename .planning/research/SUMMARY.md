# Project Research Summary

**Project:** Video-to-Text Transcription and Summarization CLI
**Domain:** Multimedia processing, speech-to-text, AI summarization
**Researched:** 2026-03-02
**Confidence:** HIGH

## Executive Summary

This is a privacy-focused CLI tool for converting video recordings (primarily meetings) into searchable transcripts and AI-generated summaries. The standard approach uses a three-stage pipeline: FFmpeg for audio extraction, faster-whisper for local transcription (4x faster than openai-whisper with same accuracy), and Claude API for intelligent summarization. Research shows this is well-trodden ground with established patterns, but several critical pitfalls can break the user experience if not addressed early.

The recommended architecture is a sequential pipeline coordinator with component isolation. Core technologies are Python 3.10+, faster-whisper 1.2.1, Anthropic SDK, and Typer/Click for CLI. Critical success factors include: (1) smart chunking with overlap to preserve context in long videos, (2) VAD and hallucination detection to prevent garbage transcripts, (3) robust temporary file management to avoid disk space issues, and (4) comprehensive error handling with retry logic for API failures.

Key risks are Whisper hallucinations on long/silent audio, naive chunking breaking context mid-sentence, FFmpeg codec compatibility issues across diverse video formats, and unreliable language auto-detection on code-switching content. All these risks have well-documented mitigation strategies and should be addressed in Phase 1 before exposing the tool to real-world video files.

## Key Findings

### Recommended Stack

Python 3.10+ provides the best ecosystem for this domain with modern CLI frameworks (Typer 0.24.1), testing tools (pytest 9.0+), and cross-platform path handling. faster-whisper 1.2.1 is the clear choice for transcription (4x performance over openai-whisper with identical accuracy, built-in VAD, 99 language support). Anthropic Python SDK 0.84.0+ handles Claude integration with streaming and async support. FFmpeg (latest stable) is industry standard for audio/video processing and required by most Python multimedia libraries.

**Core technologies:**
- **Python 3.10+**: Runtime — best ecosystem for audio/ML, required by modern tooling, pathlib improvements
- **faster-whisper 1.2.1**: Transcription — 4x faster than openai-whisper, CTranslate2 optimization, word-level timestamps, built-in VAD
- **Anthropic SDK 0.84.0+**: Summarization — official Claude integration, streaming responses, async operations
- **FFmpeg (latest)**: Audio processing — industry standard, supports all common video formats, required by MoviePy
- **Typer 0.24.1**: CLI framework — type-safe modern CLI with rich integration, 30% faster than Click
- **MoviePy 2.2.1**: Video manipulation — Python-friendly API for audio extraction, cross-platform
- **rich 14.3.3**: UX — flicker-free progress bars essential for long transcriptions

### Expected Features

Research shows clear separation between table stakes (must have for credibility) and differentiators (competitive advantage). Most critical insight: users expect transcription + summarization as coupled operations, not separate tools.

**Must have (table stakes):**
- Multiple video format support (MP4, MKV, WebM) — users expect "it just works"
- Audio extraction from video — core prerequisite, standard ffmpeg operation
- Plain text output (.txt) — universal format for downstream use
- Multi-language support (Spanish/English) — user requirement, Whisper handles natively
- Progress indicators — 3-hour videos appear broken without feedback, critical UX
- Automatic file naming alongside source — video.mp4 → video_transcript.txt reduces friction
- Basic error messages — file not found, API errors, unsupported formats must be clear
- Timestamp preservation — users need to navigate back to specific moments

**Should have (competitive):**
- Smart language auto-detection — saves configuration friction, Whisper does this well
- Intelligent chunking with silence detection — better accuracy than time-based splits
- Resume interrupted processing — 3-hour video interrupted at 80%? Resume, don't restart
- Multiple output formats (TXT, MD, SRT, VTT, JSON) — different use cases after MVP proven
- Multiple summary styles — meetings need different views (executive, action items, detailed)
- Batch processing mode — process folder of recordings overnight

**Defer (v2+):**
- Speaker diarization (2-5 speakers) — high complexity, only if users consistently request
- Custom vocabulary hints — adds value for specialized domains, wait for user demand
- Audio pre-processing enhancement — noise reduction for poor-quality recordings
- JSON output with metadata — programmatic access after core workflow validated

### Architecture Approach

Standard pattern is a Pipeline Coordinator managing sequential component execution with centralized error handling. Three core processing components (Audio Extractor → Transcription Engine → Summarization Engine) are isolated for independent testing and potential future replacement. Critical pattern is chunking with overlap for long files (respects Whisper's constraints while preserving context). Context managers guarantee temporary file cleanup even on failures.

**Major components:**
1. **CLI Handler** — argument parsing, input validation, help generation via Typer
2. **Pipeline Coordinator** — orchestrates workflow, manages component lifecycle, centralized error handling
3. **Audio Extractor** — FFmpeg subprocess wrapper, handles format normalization to 16kHz mono WAV
4. **Chunking Logic** — splits long audio at silence boundaries with overlap, adjusts timestamps
5. **Transcription Engine** — faster-whisper integration, processes chunks, handles VAD and hallucination detection
6. **Summarization Engine** — Claude API client with prompt templates, optional lazy execution
7. **Temp Manager** — context manager pattern for guaranteed cleanup, prevents disk space leaks

### Critical Pitfalls

Research identifies seven critical pitfalls that cause rewrites or break user trust. All have well-documented solutions and should be addressed in Phase 1.

1. **Naive chunking breaking context mid-sentence** — prevents transcription accuracy at chunk boundaries, requires silence detection and overlap strategy
2. **Whisper hallucinations on long/silent audio** — model generates fabricated text after 4-8 minutes, requires VAD filtering and hallucination detection
3. **Unreliable language auto-detection** — misidentifies Spanish/English especially with code-switching, requires validation and manual override option
4. **FFmpeg codec compatibility issues** — audio extraction fails on 15-25% of real-world videos with different codecs, requires format normalization
5. **API rate limits and failures** — tool crashes halfway through processing without retry logic, requires exponential backoff with progress tracking
6. **Summarization hallucinations from poor transcripts** — Claude generates fluent but incorrect summaries from garbage input, requires quality gates
7. **Temporary file cleanup failures** — disk fills up after 10-20 videos, requires context managers and crash recovery

## Implications for Roadmap

Based on research, suggested 5-phase structure prioritizing risk reduction and fast feedback:

### Phase 1: Core Pipeline (Audio → Transcript)
**Rationale:** Establishes foundational data flow and proves core technical feasibility. Audio extraction and basic transcription are prerequisites for everything else. This phase validates the technology stack works before investing in complex features.

**Delivers:** Working CLI that can process a single short video (5-10 min) and output plain text transcript.

**Addresses features:**
- Multiple video format support (MP4, MKV, WebM)
- Audio extraction from video
- Plain text output (.txt)
- Basic error messages
- Automatic file naming

**Avoids pitfalls:**
- FFmpeg codec compatibility (implement format normalization from start)
- Temporary file cleanup (use context managers immediately)
- Basic input validation to catch corrupt files early

**Research flag:** Standard patterns, extensive documentation — skip research-phase.

---

### Phase 2: Production-Ready Transcription (Chunking + Quality)
**Rationale:** Phase 1 proves feasibility but won't handle real-world usage (3-hour meetings, long silences). This phase addresses the three most critical transcription pitfalls before exposing tool to users.

**Delivers:** Reliable transcription for long videos with quality validation.

**Addresses features:**
- Handle file size variations (5min-3hr)
- Timestamp preservation in transcripts
- Progress indicators during processing
- Multi-language support (Spanish/English)

**Implements architecture:**
- Chunking logic with silence detection and overlap
- Timestamp adjustment utilities
- VAD integration for silence filtering
- Hallucination detection (repeated phrase checking)
- Language validation post-transcription

**Avoids pitfalls:**
- Naive chunking breaking context (use silence detection)
- Whisper hallucinations (add VAD + detection)
- Language auto-detection failures (add validation)
- No progress indication (implement rich progress bars)

**Research flag:** Needs shallow research — chunking parameters (overlap ratio, stride) and hallucination detection thresholds need validation with real meeting data.

---

### Phase 3: Error Handling & Resilience
**Rationale:** Real-world usage means API failures, network issues, interrupted processing. This phase makes the tool production-grade and prevents user frustration from lost progress.

**Delivers:** Resilient CLI that handles failures gracefully and provides excellent UX.

**Addresses features:**
- Resume interrupted processing
- Progress indicators (enhanced with time estimates)

**Implements architecture:**
- Comprehensive error handling hierarchy
- Exponential backoff retry logic for API calls
- Progress tracking with checkpoint persistence
- Input validation suite

**Avoids pitfalls:**
- API rate limits and failures (retry with backoff)
- No progress indication (add time estimates)
- Input validation gaps (comprehensive checks)

**Research flag:** Standard patterns — exponential backoff with tenacity library is well-documented, skip research-phase.

---

### Phase 4: Summarization
**Rationale:** Independent of transcription quality, can be built after core works. Requires transcription to be reliable first (output from Phase 2). Adds differentiating value but not blocking for transcription use case.

**Delivers:** AI-powered summaries with quality safeguards.

**Addresses features:**
- Claude API summarization (single style initially)
- Multiple summary styles (add after MVP validated)

**Implements architecture:**
- Claude API client with prompt templates
- Lazy summarization (optional flag)
- Quality gate between transcription and summarization
- Token counting to respect Claude limits

**Avoids pitfalls:**
- Summarization hallucinations from poor transcripts (quality gate)
- API rate limits (reuse retry logic from Phase 3)

**Research flag:** Needs moderate research — prompt engineering for meeting summarization styles (executive vs action items vs detailed) benefits from domain-specific examples.

---

### Phase 5: Polish & Batch Processing
**Rationale:** Quality-of-life improvements once foundation is solid. Batch mode is valuable for users with large backlogs but requires stable single-file processing first.

**Delivers:** Production-ready tool with advanced features.

**Addresses features:**
- Batch processing mode
- Multiple output formats (SRT, VTT, JSON)
- Confidence scores for low-quality sections
- Smart language auto-detection (enhanced)

**Avoids pitfalls:**
- Synchronous batch processing (implement concurrent processing with rate limit respect)
- Output file overwrites (add overwrite protection)
- No cost estimation (calculate and display API costs)

**Research flag:** Standard patterns — batch processing with async/concurrent is well-documented, skip research-phase.

---

### Phase Ordering Rationale

- **Phase 1 before all others:** Must prove basic data flow works and technology choices are sound before building complex features
- **Phase 2 before summarization:** Garbage transcripts produce garbage summaries — must fix transcription quality first
- **Phase 3 parallel to Phase 2:** Error handling can be built alongside chunking, but must complete before exposing to users
- **Phase 4 after Phase 2 + 3:** Summarization is independent but requires reliable transcription as input
- **Phase 5 last:** Batch mode and polish features assume stable single-file workflow

This ordering minimizes risk (proves hardest parts early), enables fast feedback (working CLI after Phase 1), and avoids rework (quality issues fixed before building on top).

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 2:** Chunking parameters (overlap ratio, stride, silence threshold) need empirical testing with real meeting data
- **Phase 4:** Prompt engineering for meeting summarization styles benefits from domain examples and user feedback

Phases with standard patterns (skip research-phase):
- **Phase 1:** Audio extraction and basic transcription are well-documented, multiple reference implementations
- **Phase 3:** Error handling and retry logic are general patterns with established libraries (tenacity)
- **Phase 5:** Batch processing and concurrent API calls are standard Python patterns

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All versions verified from PyPI, performance claims from official sources and benchmarks |
| Features | MEDIUM-HIGH | Table stakes validated against multiple competitor tools, differentiators extrapolated from CLI patterns |
| Architecture | HIGH | Standard pipeline pattern with extensive documentation and reference implementations |
| Pitfalls | MEDIUM | Critical issues well-documented from community experience, some mitigation strategies require empirical validation |

**Overall confidence:** HIGH — This is well-trodden domain with established patterns, clear best practices, and documented failure modes.

### Gaps to Address

Research was comprehensive but some areas need validation during implementation:

- **Chunking parameters:** Overlap ratio (1/6 recommended) and stride need testing with 3+ hour meeting recordings to validate accuracy doesn't degrade
- **Hallucination detection thresholds:** What constitutes "repeated phrase" (currently: same 10+ words repeat 3+ times) may need tuning
- **Language detection confidence:** Threshold for triggering validation (currently: >70% confidence to override auto-detection) needs empirical testing with bilingual content
- **API cost estimation accuracy:** Formulas for cost calculation need validation against actual usage patterns
- **Silence detection sensitivity:** VAD parameters for finding chunk boundaries need tuning per audio quality
- **Speaker diarization value:** Deferred to v2.0+ but worth validating user demand before committing to high implementation cost

## Sources

### Primary (HIGH confidence)
- **STACK.md** — All technology versions verified from PyPI Context7, performance claims from official sources (Modal blog, AssemblyAI)
- **FEATURES.md** — Feature expectations validated against competitor analysis (Otter.ai, Fireflies, clean-transcribe, OpenAI Cookbook)
- **ARCHITECTURE.md** — Architecture patterns from official documentation (Whisper GitHub, Claude API docs, FFmpeg guides)
- **PITFALLS.md** — Failure modes documented from community experience (GitHub issues, Stack Overflow, technical blogs)

### Secondary (MEDIUM confidence)
- Whisper long-form transcription patterns — community consensus on chunking approach (Hugging Face discussions, medium articles)
- CLI UX best practices — established patterns from multiple sources (clig.dev, Simon Willison blog)
- Speaker diarization accuracy claims — vendor marketing (80-95% accuracy) needs validation

### Tertiary (LOW confidence)
- Optimal chunking parameters (180s chunks, 1/6 stride ratio) — inference from research, needs empirical validation
- Hallucination detection thresholds — heuristic-based, not validated with ground truth data
- Cost estimation formulas — approximations based on API pricing, actual usage may vary

---
*Research completed: 2026-03-02*
*Ready for roadmap: yes*
