"""Datetime serialization helpers shared by the API and the bots."""

from datetime import UTC, datetime


def to_iso_utc(value: datetime | None) -> str | None:
    """
    Serialize a timestamp as an ISO 8601 string with an explicit UTC offset.

    SQLite has no timezone-aware type, so timestamps read back from the database are
    naive even when they were written as UTC. Serializing those without an offset
    makes browsers parse them as *local* time, which shifts every timestamp by the
    viewer's offset and can place them in the future.

    Naive values are therefore assumed to be UTC, and aware values are converted to
    UTC, so the result always ends in ``+00:00``.

    Args:
        value: The timestamp to serialize, or None.

    Returns:
        An ISO 8601 string with a UTC offset, or None when ``value`` is None.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()
