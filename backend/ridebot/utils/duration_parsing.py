"""Parse temporary-driver durations ("3d", "2 weeks", "10/5", "2026-10-05") into expiry times."""

import re
from contextlib import suppress
from datetime import UTC, date, datetime, time, timedelta

from ridebot.utils.constants import TEMP_DRIVER_DEFAULT_DURATION, TEMP_DRIVER_MAX_DURATION
from shared.utils.constants import LA_TZ

_RELATIVE_RE = re.compile(
    r"^(\d+)\s*(h|hr|hrs|hour|hours|d|day|days|w|wk|wks|week|weeks)$", re.IGNORECASE
)

_UNIT_TO_TIMEDELTA_KWARGS: dict[str, str] = {
    "h": "hours",
    "hr": "hours",
    "hrs": "hours",
    "hour": "hours",
    "hours": "hours",
    "d": "days",
    "day": "days",
    "days": "days",
    "w": "weeks",
    "wk": "weeks",
    "wks": "weeks",
    "week": "weeks",
    "weeks": "weeks",
}


def _unparseable_error(text: str) -> ValueError:
    return ValueError(
        f"Couldn't understand duration '{text}'. Try 3d, 2w, 12h, 10/5, or 2026-10-05."
    )


def _too_long_error() -> ValueError:
    return ValueError("Temporary driver roles can last at most 90 days.")


def _next_occurrence(month: int, day: int, now: datetime) -> date:
    """The next occurrence of month/day in LA, this year if today or later, else next year."""
    today_la = now.astimezone(LA_TZ).date()
    candidate = date(today_la.year, month, day)
    if candidate < today_la:
        candidate = date(today_la.year + 1, month, day)
    return candidate


def _parse_date(stripped: str, now: datetime) -> date | None:
    """Try each accepted date format in order, returning the first match."""
    with suppress(ValueError):
        return datetime.strptime(stripped, "%Y-%m-%d").date()

    with suppress(ValueError):
        parsed = datetime.strptime(stripped, "%m/%d/%y")
        return date(2000 + (parsed.year % 100), parsed.month, parsed.day)

    with suppress(ValueError):
        return datetime.strptime(stripped, "%m/%d/%Y").date()

    with suppress(ValueError):
        parsed = datetime.strptime(stripped, "%m/%d")
        return _next_occurrence(parsed.month, parsed.day, now)

    return None


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
    stripped = (text or "").strip()

    if not stripped:
        expires_at = now + TEMP_DRIVER_DEFAULT_DURATION
    else:
        relative_match = _RELATIVE_RE.match(stripped)
        if relative_match:
            amount = int(relative_match.group(1))
            unit = relative_match.group(2).lower()
            kwarg = _UNIT_TO_TIMEDELTA_KWARGS[unit]
            try:
                expires_at = now + timedelta(**{kwarg: amount})
            except OverflowError:
                raise _too_long_error() from None
        else:
            day = _parse_date(stripped, now)
            if day is None:
                raise _unparseable_error(stripped)

            # A date means "through that day", so cap it by calendar day in LA rather than
            # by exact time — otherwise today+90 (which the date picker offers) would fail.
            today_la = now.astimezone(LA_TZ).date()
            if day - today_la > TEMP_DRIVER_MAX_DURATION:
                raise _too_long_error()

            # LA_TZ is a pytz timezone; attaching it directly via tzinfo= would use
            # the zone's LMT offset instead of the correct DST-aware one, so the
            # naive datetime must be localized instead.
            naive_la_dt = datetime.combine(day, time(23, 59, 59))
            la_dt = LA_TZ.localize(naive_la_dt)
            expires_at = la_dt.astimezone(UTC)
            if expires_at <= now:
                raise ValueError("That time is in the past.")
            return expires_at

    if expires_at <= now:
        raise ValueError("That time is in the past.")

    if expires_at > now + TEMP_DRIVER_MAX_DURATION:
        raise _too_long_error()

    return expires_at
