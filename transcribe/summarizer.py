"""OpenAI GPT-5.1-based transcript summarization.

Provides functions for summarizing transcripts using OpenAI API with:
- API key validation
- Cost calculation and tracking
- Semantic chunking for long transcripts
- Map-reduce strategy for transcripts exceeding context window
- Quality gate for low-confidence transcripts
"""

import os
from pathlib import Path
import click
from openai import OpenAI

from transcribe.prompts import get_system_prompt
from transcribe.retry import api_retry
from transcribe.errors import APIKeyMissingError


def _parse_env_file(path: Path) -> dict:
    data = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                data[key] = value
    except Exception:
        return {}
    return data


def _load_api_key_from_env_files() -> str:
    candidates = [
        Path.cwd() / ".env",
        Path.home() / ".env",
        Path.home() / "Utilities" / "transcribe" / ".env",
    ]
    for path in candidates:
        if path.exists():
            values = _parse_env_file(path)
            api_key = values.get("OPENAI_API_KEY")
            if api_key:
                os.environ.setdefault("OPENAI_API_KEY", api_key)
                return api_key
    return ""


def check_api_key() -> str:
    """Check if OPENAI_API_KEY environment variable is set.

    Returns:
        API key string

    Raises:
        APIKeyMissingError: If OPENAI_API_KEY is not set
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        api_key = _load_api_key_from_env_files()

    if not api_key:
        raise APIKeyMissingError()

    return api_key


def calculate_cost(
    input_tokens: int,
    output_tokens: int,
) -> float:
    """Calculate OpenAI API cost for GPT-5.1.

    Args:
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens

    Returns:
        Total cost in USD

    Pricing (per million tokens):
        - Input: $1.25
        - Output: $10.00
    """
    input_cost = input_tokens * 1.25 / 1_000_000
    output_cost = output_tokens * 10.0 / 1_000_000

    return input_cost + output_cost


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


@api_retry
def summarize_transcript(
    transcript_text: str,
    style: str,
    language: str = "en"
) -> tuple:
    """Summarize transcript using OpenAI API.

    Args:
        transcript_text: Full transcript text
        style: Summary style (executive, action-items, detailed)
        language: Language code (en, es)

    Returns:
        Tuple of (summary_text, input_tokens, output_tokens, cost_usd)
    """
    client = OpenAI()  # Reads OPENAI_API_KEY from env automatically

    # Get style-specific system prompt
    system_prompt = get_system_prompt(style, language)

    # Create summary
    response = client.chat.completions.create(
        model="gpt-5.1",
        max_completion_tokens=2048,
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"Please summarize this transcript:\n\n{transcript_text}"
            }
        ]
    )

    # Extract usage metrics
    usage = response.usage
    input_tokens = usage.prompt_tokens
    output_tokens = usage.completion_tokens

    # Calculate cost
    cost_usd = calculate_cost(input_tokens, output_tokens)

    # Extract summary text
    summary_text = response.choices[0].message.content

    return (summary_text, input_tokens, output_tokens, cost_usd)


def summarize_long_transcript(
    transcript_text: str,
    style: str,
    language: str = "en"
) -> tuple:
    """Summarize long transcript using map-reduce strategy.

    For transcripts under 150K tokens (estimated), delegates to summarize_transcript().
    For longer transcripts, splits into chunks, summarizes each, then merges.

    Args:
        transcript_text: Full transcript text
        style: Summary style (executive, action-items, detailed)
        language: Language code (en, es)

    Returns:
        Tuple of (summary_text, total_input_tokens, total_output_tokens, cost_usd)
    """
    # Helper function for API calls with retry logic
    @api_retry
    def _api_call(client, messages, max_tokens):
        """Make API call with retry logic."""
        return client.chat.completions.create(
            model="gpt-5.1",
            max_completion_tokens=max_tokens,
            messages=messages
        )

    # Step 1: Estimate token count (1 token ≈ 4 characters)
    estimated_tokens = len(transcript_text) // 4

    # If under 150K tokens, process directly
    if estimated_tokens < 150_000:
        return summarize_transcript(transcript_text, style, language)

    # Step 2: Split into semantic chunks (~50K tokens each)
    chunks = split_into_semantic_chunks(transcript_text, max_tokens=50_000)

    client = OpenAI()

    # Step 3: Map - Summarize each chunk
    chunk_summaries = []
    total_input = 0
    total_output = 0

    for i, chunk in enumerate(chunks):
        response = _api_call(
            client,
            messages=[
                {"role": "system", "content": "Summarize this section of a longer transcript. Focus on key points, decisions, and topics."},
                {"role": "user", "content": chunk}
            ],
            max_tokens=1024
        )
        chunk_summaries.append(response.choices[0].message.content)
        total_input += response.usage.prompt_tokens
        total_output += response.usage.completion_tokens

    # Step 4: Reduce - Merge chunk summaries into final summary
    merged_summaries = "\n\n".join([
        f"Section {i+1}:\n{summary}"
        for i, summary in enumerate(chunk_summaries)
    ])

    final_response = _api_call(
        client,
        messages=[
            {"role": "system", "content": get_system_prompt(style, language)},
            {
                "role": "user",
                "content": f"These are summaries of sections from a longer transcript. Create a cohesive {style} summary:\n\n{merged_summaries}"
            }
        ],
        max_tokens=2048
    )

    total_input += final_response.usage.prompt_tokens
    total_output += final_response.usage.completion_tokens

    # Calculate total cost
    cost_usd = calculate_cost(total_input, total_output)

    final_summary = final_response.choices[0].message.content

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
