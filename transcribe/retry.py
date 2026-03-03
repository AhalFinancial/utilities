"""Retry decorators for API and FFmpeg operations.

Provides pre-configured retry logic with exponential backoff for transient failures.
Uses tenacity library for robust retry handling.
"""

import click
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
    wait_fixed,
    RetryCallState,
)
from openai import RateLimitError, APIConnectionError, APITimeoutError


def _log_retry_attempt(retry_state: RetryCallState) -> None:
    """Log retry attempt to stderr.

    Args:
        retry_state: Tenacity retry state object
    """
    attempt_num = retry_state.attempt_number
    click.echo(f"Retrying API call (attempt {attempt_num}/5)...", err=True)


# API retry decorator for OpenAI calls
# Retries only transient errors (rate limit, connection, timeout)
# Exponential backoff with jitter: 4-60 seconds
# Maximum 5 attempts before giving up
api_retry = retry(
    retry=retry_if_exception_type((RateLimitError, APIConnectionError, APITimeoutError)),
    wait=wait_random_exponential(multiplier=1, min=4, max=60),
    stop=stop_after_attempt(5),
    reraise=True,
    before_sleep=_log_retry_attempt,
)


# FFmpeg/file I/O retry decorator
# Retries only OS-level I/O errors
# Fixed 2-second delay (I/O failures are usually permanent, so no backoff needed)
# Maximum 3 attempts
ffmpeg_retry = retry(
    retry=retry_if_exception_type((OSError, IOError)),
    wait=wait_fixed(2),
    stop=stop_after_attempt(3),
    reraise=True,
)
