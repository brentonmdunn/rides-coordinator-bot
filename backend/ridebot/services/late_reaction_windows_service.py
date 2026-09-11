"""Service layer for the configurable late-reaction time windows global setting."""

import json
import logging
import re
import time

from bot.core.database import AsyncSessionLocal
from bot.core.enums import DaysOfWeek
from bot.repositories.global_settings_repository import GlobalSettingsRepository
from bot.utils.time_helpers import TimeWindow

logger = logging.getLogger(__name__)

LATE_REACTION_WINDOWS_KEY = "late_reaction_windows"

# Cache TTL: reactions fire often, so avoid a DB read on every reaction.
_CACHE_TTL_SECONDS = 60

_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")

DEFAULT_LATE_REACTION_WINDOWS: dict[DaysOfWeek, TimeWindow] = {
    DaysOfWeek.WEDNESDAY: TimeWindow(
        start_day=DaysOfWeek.TUESDAY,
        start_hour=19,
        end_day=DaysOfWeek.WEDNESDAY,
        end_hour=19,
    ),
    DaysOfWeek.FRIDAY: TimeWindow(
        start_day=DaysOfWeek.THURSDAY,
        start_hour=19,
        end_day=DaysOfWeek.FRIDAY,
        end_hour=19,
    ),
    DaysOfWeek.SUNDAY: TimeWindow(
        start_day=DaysOfWeek.SATURDAY,
        start_hour=10,
        end_day=DaysOfWeek.SUNDAY,
        end_hour=10,
    ),
}

# Maps the JSON key used in storage to the DaysOfWeek member it configures.
_DAY_KEY_TO_ENUM: dict[str, DaysOfWeek] = {
    "wednesday": DaysOfWeek.WEDNESDAY,
    "friday": DaysOfWeek.FRIDAY,
    "sunday": DaysOfWeek.SUNDAY,
}


def _parse_time(value: str) -> tuple[int, int]:
    """Parse an ``HH:MM`` string into (hour, minute). Raises ValueError if invalid."""
    match = _TIME_RE.match(value.strip()) if isinstance(value, str) else None
    if not match:
        raise ValueError(f"Invalid time format {value!r}; expected HH:MM")
    return int(match.group(1)), int(match.group(2))


def _parse_day(value: str) -> DaysOfWeek:
    """Parse a day string into a ``DaysOfWeek`` member. Raises ValueError if invalid."""
    try:
        return DaysOfWeek(str(value).capitalize())
    except ValueError as e:
        raise ValueError(f"Invalid day {value!r}; must be a valid day of week") from e


def _build_time_window(entry: dict) -> TimeWindow:
    """
    Build and validate a ``TimeWindow`` from a raw window entry.

    Raises ValueError if any field is missing/invalid, or if it is a same-day
    window with start > end.
    """
    start_day = _parse_day(entry["start_day"])
    end_day = _parse_day(entry["end_day"])
    start_hour, start_minute = _parse_time(entry["start_time"])
    end_hour, end_minute = _parse_time(entry["end_time"])

    if start_day == end_day:
        start_total = start_hour * 60 + start_minute
        end_total = end_hour * 60 + end_minute
        if start_total > end_total:
            raise ValueError(
                f"Invalid window for {start_day.value}: start time {entry['start_time']} "
                f"is after end time {entry['end_time']}"
            )

    return TimeWindow(
        start_day=start_day,
        start_hour=start_hour,
        start_minute=start_minute,
        end_day=end_day,
        end_hour=end_hour,
        end_minute=end_minute,
    )


class LateReactionWindowsService:
    """Owns reading, writing, validating, and caching the late-reaction windows setting."""

    _cache: dict[DaysOfWeek, TimeWindow] | None = None
    _fetched_at: float = 0.0

    @classmethod
    def invalidate_cache(cls) -> None:
        """Drop the cached windows so the next read re-fetches from the DB."""
        cls._cache = None
        cls._fetched_at = 0.0

    @classmethod
    async def get_windows(cls) -> dict[DaysOfWeek, TimeWindow]:
        """Return the configured late-reaction windows, falling back to defaults on errors."""
        now = time.monotonic()
        if cls._cache is not None and (now - cls._fetched_at) < _CACHE_TTL_SECONDS:
            return cls._cache

        windows = await cls._load_windows()
        cls._cache = windows
        cls._fetched_at = now
        return windows

    @classmethod
    async def _load_windows(cls) -> dict[DaysOfWeek, TimeWindow]:
        async with AsyncSessionLocal() as session:
            raw_value = await GlobalSettingsRepository.get(session, LATE_REACTION_WINDOWS_KEY)

        if not raw_value:
            # An unset key is the normal state until someone saves; not a warning.
            logger.debug(
                "No %s setting found; using default late-reaction windows",
                LATE_REACTION_WINDOWS_KEY,
            )
            return dict(DEFAULT_LATE_REACTION_WINDOWS)

        try:
            parsed = json.loads(raw_value)
        except (json.JSONDecodeError, TypeError):
            logger.exception(
                "Malformed JSON in %s setting; using default late-reaction windows",
                LATE_REACTION_WINDOWS_KEY,
            )
            return dict(DEFAULT_LATE_REACTION_WINDOWS)

        if not isinstance(parsed, dict):
            logger.warning(
                "%s setting is not a JSON object; using default late-reaction windows",
                LATE_REACTION_WINDOWS_KEY,
            )
            return dict(DEFAULT_LATE_REACTION_WINDOWS)

        windows: dict[DaysOfWeek, TimeWindow] = {}
        for key, day_enum in _DAY_KEY_TO_ENUM.items():
            entry = parsed.get(key)
            if not isinstance(entry, dict):
                logger.warning(
                    "Missing or invalid %r entry in %s; using default for %s",
                    key,
                    LATE_REACTION_WINDOWS_KEY,
                    day_enum.value,
                )
                windows[day_enum] = DEFAULT_LATE_REACTION_WINDOWS[day_enum]
                continue
            try:
                windows[day_enum] = _build_time_window(entry)
            except (KeyError, ValueError):
                logger.warning(
                    "Invalid %r entry in %s; using default for %s",
                    key,
                    LATE_REACTION_WINDOWS_KEY,
                    day_enum.value,
                )
                windows[day_enum] = DEFAULT_LATE_REACTION_WINDOWS[day_enum]

        return windows

    @classmethod
    async def set_windows(cls, windows_json: dict) -> None:
        """
        Validate and persist the given windows payload, then invalidate the cache.

        Args:
            windows_json: dict with "wednesday"/"friday"/"sunday" keys, each mapping
                to a dict with start_day/start_time/end_day/end_time.

        Raises:
            ValueError: if the payload is missing a required day or contains invalid data.
        """
        if not isinstance(windows_json, dict):
            raise ValueError("Late-reaction windows payload must be a dict")

        for key in _DAY_KEY_TO_ENUM:
            entry = windows_json.get(key)
            if not isinstance(entry, dict):
                raise ValueError(
                    f"Missing or invalid {key!r} entry in late-reaction windows payload"
                )
            # Validate defensively even though the route already validates via Pydantic.
            _build_time_window(entry)

        async with AsyncSessionLocal() as session:
            await GlobalSettingsRepository.set(
                session, LATE_REACTION_WINDOWS_KEY, json.dumps(windows_json)
            )

        cls.invalidate_cache()
        logger.info("Late-reaction windows updated")
