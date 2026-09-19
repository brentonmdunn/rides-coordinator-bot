"""Parse temporary-driver durations ("3d", "2 weeks", "10/5", "2026-10-05") into expiry times."""

from datetime import datetime


def parse_expiry(text: str | None, now: datetime) -> datetime:
    """
    Turn a user-supplied duration or date into an expiry time.

    Args:
        text: Relative duration or date, or None/blank for the default (1 week).
        now: The current time, timezone-aware UTC.

    Returns:
        The expiry time, timezone-aware UTC.

    Raises:
        ValueError: With a user-facing message if the text is unparseable, not in the
            future, or beyond the maximum duration.
    """
    raise NotImplementedError
