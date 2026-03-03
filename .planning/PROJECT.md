# Video-to-Summary CLI

## What This Is

A command-line tool that extracts audio from video files, transcribes speech to text using faster-whisper, and generates AI-powered summaries using OpenAI GPT-5.1. Processes meeting recordings in Spanish and English with smart chunking for long videos, outputting timestamped transcriptions and structured summaries as markdown files alongside the source video.

## Core Value

Reliable transcription and useful summaries from meeting recordings — drop a video file, get a readable text file with what was said and the key takeaways.

## Requirements

### Validated

- ✓ Extract audio from video files (MP4, MKV, WebM, AVI) — v1.0
- ✓ Transcribe audio to text with faster-whisper speech recognition — v1.0
- ✓ Auto-detect Spanish and English audio — v1.0
- ✓ Generate AI-powered summary using OpenAI GPT-5.1 (3 styles) — v1.0
- ✓ Output transcription + summary as markdown alongside source video — v1.0
- ✓ Single CLI command: `transcribe video.mp4` — v1.0
- ✓ Handle videos from 5 minutes to 3+ hours with smart chunking — v1.0
- ✓ Timestamps for navigation back to specific moments — v1.0
- ✓ Progress bar during long video processing — v1.0
- ✓ Clear error messages and retry logic for API/file failures — v1.0
- ✓ Quality gate skips summarization on low-confidence transcripts — v1.0
- ✓ Checkpoint-based resume for interrupted long video processing — v1.0

### Active

(None — planning next milestone)

### Out of Scope

- Web interface — CLI-first, simple and effective
- Video from URLs/YouTube — local files only, avoids legal/API complexity
- Real-time/live transcription — post-processing only, different architecture
- Speaker diarization — nice-to-have for future milestone
- Batch processing of directories — single file at a time for now
- Audio-only input — focus on video pipeline

## Context

Shipped v1.0 with 2,527 LOC Python across 14 modules.
Tech stack: Click CLI, faster-whisper, ffmpeg-python, pydub, OpenAI API, tenacity.
4 phases completed in 2 days with 10 plans and 20 tasks.
All 12 v1 requirements satisfied, milestone audit passed.

## Constraints

- **Transcription**: faster-whisper with small/medium models, CPU with int8 quantization
- **Audio extraction**: Requires system FFmpeg installation
- **Summarization**: Uses OpenAI GPT-5.1 API — requires OPENAI_API_KEY
- **File size**: Smart chunking with silence detection handles long videos (20-25s chunks, 3s overlap)
- **Cost**: GPT-5.1 at $1.25/M input, $10/M output tokens

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Python as implementation language | Best ecosystem for audio/ML (Whisper, ffmpeg bindings) | ✓ Good |
| faster-whisper for transcription | Industry standard, multi-language, runs locally | ✓ Good |
| OpenAI GPT-5.1 for summarization | Switched from Claude to OpenAI during Phase 3 per user preference | ✓ Good |
| CLI-first with Click | Simple, clean argument handling, industry standard | ✓ Good |
| hatchling build backend | Modern, simple, PyPA-recommended | ✓ Good |
| pydub for silence detection | Simple API, industry standard for audio chunking | ✓ Good |
| ProcessPoolExecutor for parallel chunks | CPU-bound workload, conservative max_workers: min(cpu, 4) | ✓ Good |
| tenacity for retry logic | Exponential backoff 4-60s for API, fixed 2s for FFmpeg | ✓ Good |
| MD5 hash (first+last 64KB) for checkpoints | Fast file integrity check for resume capability | ✓ Good |
| Map-reduce for long transcripts | Split at 50K token chunks for transcripts >150K tokens | ✓ Good |

---
*Last updated: 2026-03-03 after v1.0 milestone*
