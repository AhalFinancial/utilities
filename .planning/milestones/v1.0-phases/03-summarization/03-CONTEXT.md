# Phase 3: Summarization - Context

**Gathered:** 2026-03-03
**Status:** Ready for planning

<domain>
## Phase Boundary

AI-powered summaries that extract key points from transcripts using Claude API. Users get a summary section in the output file with key takeaways, decisions, and topics. Three summary styles available (executive, action items, detailed) with automatic style selection. Quality gate prevents garbage summaries from low-confidence transcripts.

</domain>

<decisions>
## Implementation Decisions

### Summary content & structure
- Auto-select the best summary style based on transcript content (e.g., meetings with action items get action-item style, presentations get executive style)
- User can override auto-selection with `--style executive|action-items|detailed` flag
- Executive style includes: bullet-point key takeaways, decisions made, and list of topics covered
- Summary language matches the transcript language (Spanish video = Spanish summary)

### Output formatting
- Summary at top of file, full transcript below — quick reading first, reference below
- Output file name changes to `_notes.md` when summary is included (e.g., `video_notes.md`)
- `--no-summary` flag available to get transcript only (reverts to `_transcript.md` naming)
- File naming toggles: with summary = `_notes.md`, without summary = `_transcript.md`

### Quality gate behavior
- Confidence threshold: below 40% triggers low-quality warning
- Interactive mode: warn and ask user "Attempt summary anyway? (y/n)"
- Quiet mode (-q): attempt summary silently regardless of quality (non-interactive)
- Low-confidence disclaimer: when summary is generated from low-quality transcript, add note at top: "> Note: Generated from low-confidence transcript (NN%). Verify key points."

### Claude API interaction
- Use Claude Sonnet model for summarization (balanced quality/cost)
- API key via ANTHROPIC_API_KEY environment variable (standard Anthropic SDK convention)
- Long transcripts exceeding context window: chunk transcript into sections, summarize each, then merge into one final summary
- Show estimated cost after summarization (e.g., "Summary cost: ~$0.02")

### Claude's Discretion
- Exact prompt engineering for each summary style
- How to detect which summary style fits best (content analysis heuristics)
- Chunk size and merge strategy for long transcripts
- How to structure the merged summary to feel cohesive
- Exact format of the disclaimer note for low-confidence summaries

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

*Phase: 03-summarization*
*Context gathered: 2026-03-03*
