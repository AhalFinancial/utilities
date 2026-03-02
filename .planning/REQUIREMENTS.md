# Requirements: Video-to-Summary CLI

**Defined:** 2026-03-02
**Core Value:** Reliable transcription and useful summaries from meeting recordings — drop a video, get a readable text file

## v1 Requirements

### Audio Extraction

- [ ] **AUDIO-01**: User can process MP4, MKV, WebM, and AVI video files
- [ ] **AUDIO-02**: Tool automatically names output file based on source video (video.mp4 → video_transcript.md)

### Transcription

- [ ] **TRANS-01**: User can transcribe speech from video to text using faster-whisper
- [ ] **TRANS-02**: Tool auto-detects Spanish and English audio
- [ ] **TRANS-03**: Transcript includes timestamps for navigation back to specific moments
- [ ] **TRANS-04**: Tool uses smart chunking with silence detection for videos longer than 10 minutes

### Summarization

- [ ] **SUMM-01**: User gets AI-generated summary with key points and decisions via Claude API
- [ ] **SUMM-02**: User can choose summary style: executive, action items, or detailed
- [ ] **SUMM-03**: Tool skips summarization if transcript quality is detected as low

### CLI & UX

- [ ] **CLI-01**: User runs a single command with a video file path to get transcript + summary
- [ ] **CLI-02**: Tool displays progress bar during long video processing
- [ ] **CLI-03**: Tool provides clear error messages and retry logic for API/file failures

## v2 Requirements

### Advanced Features

- **BATCH-01**: User can process a folder of videos in batch mode
- **FMT-01**: User can choose output format (SRT, VTT, JSON in addition to TXT/MD)
- **DIAR-01**: Tool identifies different speakers in the transcript
- **COST-01**: Tool estimates API cost before processing and asks for confirmation
- **RESUME-01**: Tool can resume interrupted processing of long videos

## Out of Scope

| Feature | Reason |
|---------|--------|
| Web interface | CLI-first for v1, web UI adds complexity without core value |
| YouTube/URL download | Local files only, avoids legal/API complexity |
| Real-time transcription | Post-processing only, real-time requires different architecture |
| Mobile app | Desktop CLI tool, mobile later if needed |
| Audio-only input (no video) | Focus on video pipeline, audio-only is simpler variant for later |
| Custom vocabulary/jargon hints | Nice-to-have, defer until users request domain-specific tuning |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| AUDIO-01 | — | Pending |
| AUDIO-02 | — | Pending |
| TRANS-01 | — | Pending |
| TRANS-02 | — | Pending |
| TRANS-03 | — | Pending |
| TRANS-04 | — | Pending |
| SUMM-01 | — | Pending |
| SUMM-02 | — | Pending |
| SUMM-03 | — | Pending |
| CLI-01 | — | Pending |
| CLI-02 | — | Pending |
| CLI-03 | — | Pending |

**Coverage:**
- v1 requirements: 12 total
- Mapped to phases: 0
- Unmapped: 12 ⚠️

---
*Requirements defined: 2026-03-02*
*Last updated: 2026-03-02 after initial definition*
