"""
Example:

import requests
import datetime
from icalendar import Calendar
import recurring_ical_events

# --- Configuration ---
ICAL_URL = "https://calendar.google.com/calendar/ical/mastercalendar%40lsccsd.com/public/basic.ics"
TARGET_DATE = datetime.date(2025, 12, 7)

# --- Function to Get Events ---

def get_events_on_date(ical_url, target_date):

    Downloads iCal data from a URL and extracts all events on a specific date.

    try:
        # 1. Download the iCal content
        response = requests.get(ical_url)
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
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

# --- Execution ---

events_for_day = get_events_on_date(ICAL_URL, TARGET_DATE)

if events_for_day:
    logger.debug(f"🎉 Events on {TARGET_DATE.strftime('%Y-%m-%d')}:")
    for event in events_for_day:
        # DTSTART and SUMMARY are common and useful properties
        start_time = event.get('DTSTART').dt
        summary = str(event.get('SUMMARY'))

        # Handle all-day vs. timed events for display
        if isinstance(start_time, datetime.datetime):
            # Timed event
            logger.debug(f"  - {start_time.strftime('%H:%M')} | {summary}")
        else:
            # All-day event (start_time will be a datetime.date object)
            logger.debug(f"  - All Day | {summary}")
else:
    logger.debug(f"No events found on {TARGET_DATE.strftime('%Y-%m-%d')}.")
"""

import datetime
from os import getenv

import recurring_ical_events
import requests
from icalendar import Calendar

from app.core.logger import logger

# --- Configuration ---
ICAL_URL = getenv("ICAL_URL")
TARGET_DATE = datetime.date(2025, 12, 7)

# --- Function to Get Events ---


def get_events_on_date(ical_url, target_date):
    """
    Downloads iCal data from a URL and extracts all events on a specific date.
    """
    try:
        # 1. Download the iCal content
        response = requests.get(ical_url)
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


# --- Execution ---


def get_event_summaries(target_date):
    events_for_day = get_events_on_date(ICAL_URL, target_date)

    if events_for_day:
        event_summary = []
        for event in events_for_day:
            summary = str(event.get("SUMMARY"))
            event_summary.append(summary)

        return event_summary

    return []
