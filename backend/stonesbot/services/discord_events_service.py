"""
Service for creating Discord scheduled events from calendar entries.

Wraps `Guild.create_scheduled_event` so the rules for *which* calendar events
become Discord events — and with what time and location — live in one place
rather than inline in a job.
"""

import datetime
import logging
from dataclasses import dataclass

import discord

from shared.utils.constants import LA_TZ

logger = logging.getLogger(__name__)

# Calendar entries that get a matching Discord scheduled event, keyed by the
# exact (case-insensitively matched) event summary. The iCal feed's worship
# service entries are all-day, so the real time and place are pinned here.
WORSHIP_SERVICE_SUMMARY = "Regular Worship Service"
WORSHIP_SERVICE_START = datetime.time(10, 30)
WORSHIP_SERVICE_END = datetime.time(12, 0)
WORSHIP_SERVICE_LOCATION = "Jonas Salk Elementary School"


@dataclass(frozen=True)
class ScheduledEventSpec:
    """The details needed to create one Discord scheduled event."""

    name: str
    start: datetime.datetime
    end: datetime.datetime
    location: str


class DiscordEventsService:
    """Creates Discord scheduled events for recognized calendar entries."""

    @staticmethod
    def build_specs(
        summaries_by_date: dict[datetime.date, list[str]],
    ) -> list[ScheduledEventSpec]:
        """
        Turn calendar summaries into scheduled-event specs.

        Only summaries that map to a known event type produce a spec; everything
        else is ignored. Times are anchored in LA time, since the feed's entries
        are all-day and carry no usable time of their own.

        Args:
            summaries_by_date: Event summaries keyed by date.

        Returns:
            Specs sorted by start time. Duplicate summaries on the same date
            collapse into a single spec.
        """
        specs: list[ScheduledEventSpec] = []
        seen: set[tuple[str, datetime.datetime]] = set()

        for day in sorted(summaries_by_date):
            for summary in summaries_by_date[day]:
                if summary.strip().casefold() != WORSHIP_SERVICE_SUMMARY.casefold():
                    continue
                start = LA_TZ.localize(datetime.datetime.combine(day, WORSHIP_SERVICE_START))
                end = LA_TZ.localize(datetime.datetime.combine(day, WORSHIP_SERVICE_END))
                key = (WORSHIP_SERVICE_SUMMARY, start)
                if key in seen:
                    continue
                seen.add(key)
                specs.append(
                    ScheduledEventSpec(
                        name=WORSHIP_SERVICE_SUMMARY,
                        start=start,
                        end=end,
                        location=WORSHIP_SERVICE_LOCATION,
                    )
                )

        return specs

    @staticmethod
    def _already_exists(guild: discord.Guild, spec: ScheduledEventSpec) -> bool:
        """
        Whether the guild already has a scheduled event matching *spec*.

        Matching on name plus start time keeps re-runs of the weekly job (or a
        manual re-post) from stacking up duplicate events, without needing a
        table to track what was created.
        """
        for existing in guild.scheduled_events:
            if existing.name != spec.name or existing.start_time is None:
                continue
            if existing.start_time == spec.start:
                return True
        return False

    @staticmethod
    async def create_events(
        guild: discord.Guild,
        summaries_by_date: dict[datetime.date, list[str]],
        now: datetime.datetime | None = None,
    ) -> list[discord.ScheduledEvent]:
        """
        Create Discord scheduled events for recognized entries in the week.

        Best-effort: each event is created independently, so a permission error
        or an API failure on one does not stop the rest. Events whose start time
        has already passed are skipped, since Discord rejects them.

        Args:
            guild: The guild to create events in.
            summaries_by_date: Event summaries keyed by date.
            now: Override for the current time, for testing.

        Returns:
            The scheduled events that were created.
        """
        now = now or datetime.datetime.now(tz=LA_TZ)
        created: list[discord.ScheduledEvent] = []

        for spec in DiscordEventsService.build_specs(summaries_by_date):
            if spec.start <= now:
                logger.info(
                    "Skipping scheduled event '%s' at %s: start time is in the past",
                    spec.name,
                    spec.start.isoformat(),
                )
                continue

            if DiscordEventsService._already_exists(guild, spec):
                logger.info(
                    "Scheduled event '%s' at %s already exists; skipping",
                    spec.name,
                    spec.start.isoformat(),
                )
                continue

            try:
                event = await guild.create_scheduled_event(
                    name=spec.name,
                    start_time=spec.start,
                    end_time=spec.end,
                    entity_type=discord.EntityType.external,
                    privacy_level=discord.PrivacyLevel.guild_only,
                    location=spec.location,
                    reason="Weekly events announcement",
                )
            except discord.Forbidden:
                logger.exception(
                    "Missing permission to create scheduled event '%s' in guild %s",
                    spec.name,
                    guild.id,
                )
                continue
            except discord.HTTPException:
                logger.exception(
                    "Failed to create scheduled event '%s' at %s",
                    spec.name,
                    spec.start.isoformat(),
                )
                continue

            logger.info(
                "Created scheduled event '%s' at %s (%s)",
                spec.name,
                spec.start.isoformat(),
                spec.location,
            )
            created.append(event)

        return created
