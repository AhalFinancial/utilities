# Video-to-Summary CLI

## What This Is

A command-line tool that extracts audio from video files, transcribes the speech to text, and generates concise summaries using AI. Designed for processing meeting recordings in Spanish and English, outputting both the full transcription and a summary to a text file alongside the original video.

## Core Value

Reliable transcription and useful summaries from meeting recordings — the user drops a video file, gets back a readable text file with what was said and the key takeaways.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Extract audio from video files (various formats: mp4, mkv, webm, etc.)
- [ ] Transcribe audio to text with accurate speech recognition
- [ ] Support Spanish and English audio (auto-detect language)
- [ ] Generate AI-powered summary from transcription using Claude API
- [ ] Output full transcription + summary to a .txt or .md file next to the source video
- [ ] CLI interface: pass a video file path, get the result
- [ ] Handle videos of varying length (5 min to 3+ hours)

### Out of Scope

- Web interface — CLI only for v1
- Video from URLs/YouTube — local files only
- Real-time/live transcription — post-processing only
- Speaker diarization (who said what) — nice to have but not v1
- Batch processing of directories — single file at a time for v1

## Context

- Primary use case: meeting recordings from work calls
- Videos are local files, various durations (quick syncs to long workshops)
- Both Spanish and English content, sometimes mixed
- User wants to quickly review what was discussed without re-watching
- Output should be a file saved alongside the source video for easy reference

## Constraints

- **Transcription**: Needs a model that handles Spanish and English well (Whisper is the standard)
- **Audio extraction**: Requires ffmpeg for reliable format handling
- **Summarization**: Uses Anthropic Claude API — requires API key
- **File size**: Long meetings produce large audio — need to handle chunking for transcription
- **Cost**: API calls for summarization have token costs proportional to transcript length

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Python as implementation language | Best ecosystem for audio/ML (Whisper, ffmpeg bindings), straightforward CLI tooling | — Pending |
| Whisper for transcription | Industry standard for speech-to-text, supports multiple languages, runs locally | — Pending |
| Claude API for summarization | User preference, strong multilingual summarization capabilities | — Pending |
| CLI-first interface | User preference, simplest path to usable tool | — Pending |

---
*Last updated: 2026-03-02 after initialization*
