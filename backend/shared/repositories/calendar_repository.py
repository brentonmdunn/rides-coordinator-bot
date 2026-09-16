"""Repository for calendar data access."""

import datetime
import logging
from os import getenv

import httpx
import recurring_ical_events
from icalendar import Calendar

logger = logging.getLogger(__name__)

ICAL_URL = getenv("ICAL_URL")


class CalendarRepository:
    """Repository for accessing calendar events."""

    @staticmethod
    async def _fetch_calendar() -> Calendar | None:
        """
        Download and parse the iCal feed.

        Returns:
            The parsed Calendar, or None if the feed is unset, unreachable, or invalid.
        """
        if not ICAL_URL:
            logger.error("ICAL_URL environment variable not set.")
            return None

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(ICAL_URL)
            response.raise_for_status()
            return Calendar.from_ical(response.text)

        except httpx.HTTPError as e:
            logger.warning(f"Error downloading calendar: {e}")
            return None
        except ValueError as e:
            logger.warning(f"Error parsing iCal data: {e}")
            return None

    @staticmethod
    async def get_events_on_date(target_date: datetime.date) -> list:
        """
        Downloads iCal data from a URL and extracts all events on a specific date.

        Args:
            target_date: The date to fetch events for.

        Returns:
            A list of recurring_ical_events objects.
        """
        calendar = await CalendarRepository._fetch_calendar()
        if calendar is None:
            return []

        try:
            return recurring_ical_events.of(calendar).at(target_date)
        except ValueError as e:
            logger.warning(f"Error expanding recurring events: {e}")
            return []

    @staticmethod
    async def get_event_summaries(target_date: datetime.date) -> list[str]:
        """
        Get a list of event summaries for a specific date.

        Args:
            target_date: The date to fetch event summaries for.

        Returns:
            A list of event summary strings.
        """
        events_for_day = await CalendarRepository.get_events_on_date(target_date)

        if events_for_day:
            event_summary = []
            for event in events_for_day:
                summary = str(event.get("SUMMARY"))
                event_summary.append(summary)

            return event_summary

        return []

    @staticmethod
    async def get_event_summaries_by_date(
        start_date: datetime.date, end_date: datetime.date
    ) -> dict[datetime.date, list[str]]:
        """
        Get event summaries for every date in an inclusive range, grouped by date.

        The feed is downloaded once and expanded per day, rather than once per
        day, so announcing a whole week costs a single HTTP request.

        Args:
            start_date: First date in the range (inclusive).
            end_date: Last date in the range (inclusive).

        Returns:
            A dict mapping each date in the range to its event summaries. Every
            date in the range is present; dates with no events map to an empty
            list. Returns an empty dict if the calendar could not be fetched.
        """
        if end_date < start_date:
            logger.warning(
                "get_event_summaries_by_date called with end_date %s before start_date %s",
                end_date,
                start_date,
            )
            return {}

        calendar = await CalendarRepository._fetch_calendar()
        if calendar is None:
            return {}

        try:
            query = recurring_ical_events.of(calendar)
        except ValueError as e:
            logger.warning(f"Error expanding recurring events: {e}")
            return {}

        summaries_by_date: dict[datetime.date, list[str]] = {}
        current = start_date
        while current <= end_date:
            try:
                events = query.at(current)
            except ValueError as e:
                logger.warning(f"Error expanding recurring events for {current}: {e}")
                events = []
            summaries_by_date[current] = [str(event.get("SUMMARY")) for event in events]
            current += datetime.timedelta(days=1)

        return summaries_by_date
