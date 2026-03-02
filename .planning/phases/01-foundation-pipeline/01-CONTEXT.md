# Phase 1: Foundation Pipeline - Context

**Gathered:** 2026-03-02
**Status:** Ready for planning

<domain>
## Phase Boundary

CLI tool that extracts audio from a local video file, transcribes it to text using faster-whisper, and outputs a structured markdown file. Supports MP4, MKV, WebM, and AVI formats. This phase covers basic single-file processing for short videos (5-10 min). Smart chunking, summarization, and batch processing are separate phases.

</domain>

<decisions>
## Implementation Decisions

### Output format
- Markdown (.md) output format
- Full metadata header: file name, date, duration, language detected, model used
- Output saved in same folder as source video (video.mp4 → video_transcript.md)
- If output file exists: warn and prompt user; --force flag to overwrite without asking

### CLI invocation
- Command name: `transcribe`
- Video file passed as positional argument: `transcribe video.mp4`
- Progress shown by default (extracting… transcribing… done); -q flag for quiet mode
- Check for FFmpeg on startup, fail early with clear install instructions if missing

### Video format handling
- Support all 4 formats: MP4, MKV, WebM, AVI
- No audio track: warn and skip (don't crash)
- Corrupted/unreadable file: clear error message ("Could not read video.mp4 — file may be corrupted")
- Validate FFmpeg availability before any processing

### Transcript style
- Timestamped blocks: [00:01:23] text... [00:02:45] next block...
- Timestamps at natural speech pauses (follow conversation flow)
- Polished output: proper punctuation and capitalization
- Output language matches audio language (Spanish audio → Spanish text, English → English)

### Claude's Discretion
- Installation/packaging approach (pip, pipx, uv, or local script)
- Exact progress message format and styling
- Whisper model size selection for Phase 1 (base/small/medium)
- Temp file management strategy
- Exact markdown template structure

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-foundation-pipeline*
*Context gathered: 2026-03-02*
