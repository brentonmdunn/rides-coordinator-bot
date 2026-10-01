"""
Async retry helper for transient Discord 5xx / connection failures.

Discord's edge proxy occasionally returns transient 5xx responses (500/502/503/504)
or drops the connection mid-request. A single such blip should not take down an
event handler, so wrap the fragile call (e.g. ``channel.fetch_message``) with
``fetch_message_with_retry`` / the ``retry_transient_discord`` decorator.

Only genuinely transient failures are retried — permanent ones (404/403, other
4xx, rate limits which discord.py already backs off on) fail fast.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable

import discord
import tenacity

from shared.utils.constants import (
    DISCORD_FETCH_RETRY_ATTEMPTS,
    DISCORD_FETCH_RETRY_WAIT_SECONDS,
)

logger = logging.getLogger(__name__)


def is_transient_discord_error(exc: BaseException) -> bool:
    """
    Return True for transient Discord failures worth retrying.

    Retries:
    - ``discord.DiscordServerError`` (500/502/503/504 — the incident class)
    - ``asyncio.TimeoutError`` and connection-level ``OSError`` (covers
      ``aiohttp.ClientConnectionError``, a subclass, without importing the
      undeclared transitive ``aiohttp`` package)

    Does NOT retry:
    - ``discord.RateLimited`` — discord.py's HTTP layer handles 429 backoff itself
    - ``discord.NotFound`` / ``discord.Forbidden`` / other ``discord.HTTPException``
      (4xx) — retrying a deleted message or a permission error is pure latency
    """
    if isinstance(exc, discord.RateLimited):
        return False
    if isinstance(exc, discord.DiscordServerError):
        return True
    if isinstance(exc, discord.HTTPException):
        # Any other HTTP error (4xx: NotFound, Forbidden, generic) is permanent.
        return False
    return isinstance(exc, (asyncio.TimeoutError, OSError))


def _log_retry_attempt(retry_state: tenacity.RetryCallState) -> None:
    """Warn on each retry, mirroring llm_service.log_retry_attempt."""
    outcome = retry_state.outcome
    exc = outcome.exception() if outcome is not None else None
    logger.warning(
        "Transient Discord error, retrying fetch (attempt %s/%s). Exception was: %s",
        retry_state.attempt_number,
        DISCORD_FETCH_RETRY_ATTEMPTS,
        exc,
    )


retry_transient_discord = tenacity.retry(
    stop=tenacity.stop_after_attempt(DISCORD_FETCH_RETRY_ATTEMPTS),
    wait=tenacity.wait_exponential(multiplier=DISCORD_FETCH_RETRY_WAIT_SECONDS, max=5.0),
    retry=tenacity.retry_if_exception(is_transient_discord_error),
    before_sleep=_log_retry_attempt,
    reraise=True,
)


@retry_transient_discord
async def _call[T](func: Callable[[], Awaitable[T]]) -> T:
    return await func()


async def fetch_message_with_retry(
    channel: discord.abc.Messageable, message_id: int
) -> discord.Message:
    """
    Fetch a message, retrying only transient Discord 5xx / connection failures.

    Async throughout (never blocks the shared event loop). Permanent failures
    (``NotFound``, ``Forbidden``, other 4xx) propagate on the first attempt.
    """
    return await _call(lambda: channel.fetch_message(message_id))
