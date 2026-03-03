"""Claude API-based transcript summarization.

Provides functions for summarizing transcripts using Claude API with:
- API key validation
- Cost calculation and tracking
- Semantic chunking for long transcripts
- Map-reduce strategy for transcripts exceeding context window
- Quality gate for low-confidence transcripts
"""

import os
import click
import anthropic

from transcribe.prompts import get_system_prompt


def check_api_key() -> str:
    """Check if ANTHROPIC_API_KEY environment variable is set.

    Returns:
        API key string

    Raises:
        RuntimeError: If ANTHROPIC_API_KEY is not set
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY environment variable not set.\n"
            "Get your API key from: https://console.anthropic.com/settings/keys\n"
            "Set it with: export ANTHROPIC_API_KEY='your-key-here'"
        )

    return api_key


def calculate_cost(
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0
) -> float:
    """Calculate Claude API cost for Sonnet 4.6.

    Args:
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        cache_read_tokens: Number of tokens read from cache
        cache_write_tokens: Number of tokens written to cache

    Returns:
        Total cost in USD

    Pricing (per million tokens):
        - Base input: $3
        - Output: $15
        - Cache write (5-min TTL): $3.75 (1.25x base)
        - Cache read: $0.30 (0.1x base)
    """
    # Base costs
    input_cost = input_tokens * 3.0 / 1_000_000
    output_cost = output_tokens * 15.0 / 1_000_000

    # Cache costs
    cache_write_cost = cache_write_tokens * 3.75 / 1_000_000
    cache_read_cost = cache_read_tokens * 0.30 / 1_000_000

    total = input_cost + output_cost + cache_write_cost + cache_read_cost
    return total


def split_into_semantic_chunks(text: str, max_tokens: int = 50000) -> list:
    """Split text into semantic chunks by paragraphs, staying under max_tokens.

    Args:
        text: Full transcript text
        max_tokens: Maximum tokens per chunk (default: 50000)

    Returns:
        List of text chunks (at least one chunk, even if empty input)
    """
    paragraphs = text.split('\n\n')
    chunks = []
    current_chunk = []
    current_tokens = 0

    for para in paragraphs:
        # Rough estimate: 1 token ≈ 4 characters
        para_tokens = len(para) // 4

        if current_tokens + para_tokens > max_tokens and current_chunk:
            # Finalize current chunk
            chunks.append('\n\n'.join(current_chunk))
            current_chunk = [para]
            current_tokens = para_tokens
        else:
            current_chunk.append(para)
            current_tokens += para_tokens

    # Add final chunk
    if current_chunk:
        chunks.append('\n\n'.join(current_chunk))

    # Always return at least one chunk
    if not chunks:
        chunks = [text]

    return chunks


def summarize_transcript(
    transcript_text: str,
    style: str,
    language: str = "en"
) -> tuple:
    """Summarize transcript using Claude API.

    Args:
        transcript_text: Full transcript text
        style: Summary style (executive, action-items, detailed)
        language: Language code (en, es)

    Returns:
        Tuple of (summary_text, input_tokens, output_tokens, cost_usd)
    """
    client = anthropic.Anthropic()  # Reads ANTHROPIC_API_KEY from env automatically

    # Get style-specific system prompt
    system_prompt = get_system_prompt(style, language)

    # Create summary
    response = client.messages.create(
        model="claude-sonnet-4-6-20250514",
        max_tokens=2048,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": f"Please summarize this transcript:\n\n{transcript_text}"
            }
        ]
    )

    # Extract usage metrics
    usage = response.usage
    input_tokens = usage.input_tokens
    output_tokens = usage.output_tokens

    # Calculate cost
    cost_usd = calculate_cost(input_tokens, output_tokens)

    # Extract summary text
    summary_text = response.content[0].text

    return (summary_text, input_tokens, output_tokens, cost_usd)


def summarize_long_transcript(
    transcript_text: str,
    style: str,
    language: str = "en"
) -> tuple:
    """Summarize long transcript using map-reduce strategy.

    For transcripts under 150K tokens, delegates to summarize_transcript().
    For longer transcripts, splits into chunks, summarizes each, then merges.

    Args:
        transcript_text: Full transcript text
        style: Summary style (executive, action-items, detailed)
        language: Language code (en, es)

    Returns:
        Tuple of (summary_text, total_input_tokens, total_output_tokens, cost_usd)
    """
    client = anthropic.Anthropic()

    # Step 1: Check token count
    token_count_response = client.messages.count_tokens(
        model="claude-sonnet-4-6-20250514",
        messages=[{"role": "user", "content": transcript_text}]
    )
    total_tokens = token_count_response.input_tokens

    # If under 150K tokens, process directly
    if total_tokens < 150_000:
        return summarize_transcript(transcript_text, style, language)

    # Step 2: Split into semantic chunks (~50K tokens each)
    chunks = split_into_semantic_chunks(transcript_text, max_tokens=50_000)

    # Step 3: Map - Summarize each chunk
    chunk_summaries = []
    total_input = 0
    total_output = 0

    for i, chunk in enumerate(chunks):
        response = client.messages.create(
            model="claude-sonnet-4-6-20250514",
            max_tokens=1024,
            system="Summarize this section of a longer transcript. Focus on key points, decisions, and topics.",
            messages=[{"role": "user", "content": chunk}]
        )
        chunk_summaries.append(response.content[0].text)
        total_input += response.usage.input_tokens
        total_output += response.usage.output_tokens

    # Step 4: Reduce - Merge chunk summaries into final summary
    merged_summaries = "\n\n".join([
        f"Section {i+1}:\n{summary}"
        for i, summary in enumerate(chunk_summaries)
    ])

    final_response = client.messages.create(
        model="claude-sonnet-4-6-20250514",
        max_tokens=2048,
        system=get_system_prompt(style, language),
        messages=[{
            "role": "user",
            "content": f"These are summaries of sections from a longer transcript. Create a cohesive {style} summary:\n\n{merged_summaries}"
        }]
    )

    total_input += final_response.usage.input_tokens
    total_output += final_response.usage.output_tokens

    # Calculate total cost
    cost_usd = calculate_cost(total_input, total_output)

    final_summary = final_response.content[0].text

    return (final_summary, total_input, total_output, cost_usd)


def summarize_with_quality_gate(
    transcript_text: str,
    confidence_pct: float,
    style: str,
    language: str = "en",
    quiet: bool = False
) -> tuple:
    """Summarize transcript with quality gate check.

    Checks transcript confidence and warns/prompts user if below 40% threshold.
    In quiet mode, attempts summary anyway. In interactive mode, asks user.

    Args:
        transcript_text: Full transcript text
        confidence_pct: Transcript confidence from Phase 2 (0-100)
        style: Summary style
        language: Language code
        quiet: If True, skip interactive prompts

    Returns:
        Tuple of (summary_text, cost_usd, attempted) where attempted=False if skipped
    """
    # Quality threshold: 40%
    if confidence_pct < 40:
        if quiet:
            # Quiet mode: attempt anyway but add disclaimer
            click.echo(f"Warning: Low transcript confidence ({confidence_pct:.0f}%)")
            summary, _, _, cost = summarize_long_transcript(transcript_text, style, language)
            disclaimer = f"> Note: Generated from low-confidence transcript ({confidence_pct:.0f}%). Verify key points.\n\n"
            return (disclaimer + summary, cost, True)
        else:
            # Interactive mode: ask user
            click.echo(f"Low transcript confidence ({confidence_pct:.0f}%).")
            if not click.confirm("Attempt summary anyway?", default=False):
                click.echo("Skipping summarization.")
                return ("", 0.0, False)

            # User confirmed - summarize with disclaimer
            summary, _, _, cost = summarize_long_transcript(transcript_text, style, language)
            disclaimer = f"> Note: Generated from low-confidence transcript ({confidence_pct:.0f}%). Verify key points.\n\n"
            return (disclaimer + summary, cost, True)

    # Confidence acceptable - proceed normally
    summary, _, _, cost = summarize_long_transcript(transcript_text, style, language)
    return (summary, cost, True)
