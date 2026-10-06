"""
Parse Slack message links.

A link copied from Slack ("Copy link") looks like
``https://<workspace>.slack.com/archives/C0123ABCD/p1791253088119709``, with
``?thread_ts=1791253000.000100&cid=C0123ABCD`` added for a reply in a thread.
The path segment after ``p`` is the message's ts with the dot removed.
"""

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

_PATH_PATTERN = re.compile(r"/archives/([A-Z0-9]+)/p(\d{7,})/?")
# Slack ts values always have six digits after the dot.
_TS_FRACTION_DIGITS = 6


@dataclass(frozen=True)
class SlackMessageLink:
    """The parts of a Slack message link."""

    channel_id: str
    ts: str
    thread_ts: str | None

    @property
    def is_thread_reply(self) -> bool:
        """Whether the link points at a reply inside a thread, not a top-level message."""
        return self.thread_ts is not None and self.thread_ts != self.ts


def parse_message_link(url: str) -> SlackMessageLink | None:
    """
    Parse a Slack message link.

    Args:
        url: A link copied from Slack, e.g.
            ``https://church.slack.com/archives/C0123ABCD/p1791253088119709``.

    Returns:
        The channel id, message ts and (for thread replies) thread ts, or None
        if *url* isn't a Slack message link.
    """
    parsed = urlparse(url.strip().strip("<>"))
    host = parsed.hostname or ""
    if parsed.scheme not in {"http", "https"} or not (
        host == "slack.com" or host.endswith(".slack.com")
    ):
        return None

    match = _PATH_PATTERN.fullmatch(parsed.path)
    if match is None:
        return None
    channel_id, digits = match.groups()
    ts = f"{digits[:-_TS_FRACTION_DIGITS]}.{digits[-_TS_FRACTION_DIGITS:]}"

    thread_ts = parse_qs(parsed.query).get("thread_ts", [None])[0]
    return SlackMessageLink(channel_id=channel_id, ts=ts, thread_ts=thread_ts)
