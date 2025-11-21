"""Repository for calendar data access."""

import datetime
from os import getenv

import recurring_ical_events
import requests
from icalendar import Calendar

from app.core.logger import logger

ICAL_URL = getenv("ICAL_URL")


class CalendarRepository:
    """Repository for accessing calendar events."""

    def get_events_on_date(self, target_date: datetime.date) -> list:
        """Downloads iCal data from a URL and extracts all events on a specific date.

        Args:
            target_date: The date to fetch events for.

        Returns:
            A list of recurring_ical_events objects.
        """
        if not ICAL_URL:
            logger.error("ICAL_URL environment variable not set.")
            return []

        try:
            # 1. Download the iCal content
            response = requests.get(ICAL_URL)
            response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
            ical_data = response.text

            # 2. Parse the iCal data
            calendar = Calendar.from_ical(ical_data)

            # 3. Get events for the specific date, handling recurrences
            events = recurring_ical_events.of(calendar).at(target_date)

            return events

        except requests.exceptions.RequestException as e:
            logger.debug(f"Error downloading calendar: {e}")
            return []
        except ValueError as e:
            logger.debug(f"Error parsing iCal data: {e}")
            return []

    def get_event_summaries(self, target_date: datetime.date) -> list[str]:
        """Get a list of event summaries for a specific date.

        Args:
            target_date: The date to fetch event summaries for.

        Returns:
            A list of event summary strings.
        """
        events_for_day = self.get_events_on_date(target_date)

        if events_for_day:
            event_summary = []
            for event in events_for_day:
                summary = str(event.get("SUMMARY"))
                event_summary.append(summary)

            return event_summary

        return []
