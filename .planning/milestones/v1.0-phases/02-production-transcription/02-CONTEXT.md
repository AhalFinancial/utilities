# Phase 2: Production Transcription - Context

**Gathered:** 2026-03-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Reliable transcription for real-world usage: long videos (up to 3+ hours), smart chunking with silence detection, visual progress feedback, language auto-detection (Spanish/English), and quality validation. This phase upgrades the basic Phase 1 pipeline to handle production workloads. Summarization is a separate phase.

</domain>

<decisions>
## Implementation Decisions

### Chunking strategy
- Chunk size: Claude's discretion based on research into faster-whisper optimal chunk sizes
- Short videos (under 10 minutes): no chunking, process as single piece
- Long videos: split with overlap between chunks, then deduplicate overlapping text
- Process chunks in parallel for speed (user accepts higher RAM usage)

### Progress feedback
- Visual progress bar with percentage: [████░░░░] 45%
- Show: time elapsed, ETA/time remaining, current chunk indicator
- Two separate stages: "Extracting audio... [done]" then "Transcribing... [████░░] 60%"
- Quiet mode (-q): minimal text output only ("Extracting... Transcribing... Done.") — no progress bar

### Timestamp granularity
- Timestamps at natural pauses/topic changes only — fewer but more meaningful
- Adaptive format: [MM:SS] for videos under 1 hour, [HH:MM:SS] for longer
- Merge speech segments into flowing paragraphs under each timestamp
- Add word count and estimated reading time to metadata header

### Quality validation
- Warn on low confidence but always save the transcript ("Low confidence detected" warning)
- Average confidence score in metadata header (e.g., "Confidence: 87%")
- Mark non-speech segments inline: [music], [background noise]
- Auto-upgrade model: if confidence is low with 'small' model, retry with 'medium' automatically

### Claude's Discretion
- Exact chunk size and overlap duration
- Silence detection threshold parameters
- Confidence score calculation method
- Progress bar library/implementation choice
- Deduplication algorithm for overlapping chunk text
- Parallel processing thread/process count

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

*Phase: 02-production-transcription*
*Context gathered: 2026-03-02*
