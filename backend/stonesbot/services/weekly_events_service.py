"""
Service for the weekly events announcement.

Builds and posts the "events for the coming week" announcement and cleans up the
previous week's message. Called by the scheduled job and by any future entry
point (slash command, API route) so the logic lives in exactly one place.
"""

import datetime
import logging

import discord
from discord.ext.commands import Bot

from shared.core.database import AsyncSessionLocal
from shared.core.enums import ChannelIds, DaysOfWeekNumber
from shared.core.error_reporter import send_error_to_discord
from shared.core.models import WeeklyEventsAnnouncement
from shared.repositories.calendar_repository import CalendarRepository
from shared.utils.channels import resolve_channel_id
from shared.utils.constants import LA_TZ
from stonesbot.repositories.weekly_events_announcement_repository import (
    WeeklyEventsAnnouncementRepository,
)
from stonesbot.services.discord_events_service import DiscordEventsService

logger = logging.getLogger(__name__)

DAYS_IN_WEEK = 7
EMBED_COLOR = discord.Color.blurple()
EMBED_DESCRIPTION_LIMIT = 4096
NO_EVENTS_TEXT = "No events scheduled this week."

# The calendar feed carries far more than what belongs in the announcement, so
# only these events are announced. Matching is case-insensitive.
# Exact matches: the summary must equal one of these after stripping whitespace.
ALLOWED_EVENT_SUMMARIES = ("Regular Worship Service",)
# Substring matches: the summary must contain one of these anywhere.
ALLOWED_EVENT_SUBSTRINGS = ("Wildcard Sunday",)


class WeeklyEventsService:
    """Posts the weekly events announcement and removes the previous one."""

    @staticmethod
    def get_announcement_week(today: datetime.date) -> tuple[datetime.date, datetime.date]:
        """
        Resolve the Monday-Sunday week an announcement made on *today* should cover.

        Always the next week that has not started yet: the first Monday strictly
        after *today*, through the Sunday six days later. Run on a Sunday (the
        scheduled case) that is tomorrow through the Sunday a week out.

        Args:
            today: The date the announcement is being made on.

        Returns:
            A (week_start, week_end) tuple of dates, inclusive.
        """
        days_until_monday = (DaysOfWeekNumber.MONDAY - today.weekday()) % DAYS_IN_WEEK or (
            DAYS_IN_WEEK
        )
        week_start = today + datetime.timedelta(days=days_until_monday)
        week_end = week_start + datetime.timedelta(days=DAYS_IN_WEEK - 1)
        return week_start, week_end

    @staticmethod
    def is_allowed_event(summary: str) -> bool:
        """
        Whether an event summary belongs in the announcement.

        Args:
            summary: The event's SUMMARY text from the calendar feed.

        Returns:
            True if the summary exactly matches an allowed event name, or
            contains an allowed substring. Matching is case-insensitive and
            ignores surrounding whitespace.
        """
        normalized = summary.strip().casefold()
        if normalized in {allowed.casefold() for allowed in ALLOWED_EVENT_SUMMARIES}:
            return True
        return any(substring.casefold() in normalized for substring in ALLOWED_EVENT_SUBSTRINGS)

    @staticmethod
    def filter_allowed_events(
        summaries_by_date: dict[datetime.date, list[str]],
    ) -> dict[datetime.date, list[str]]:
        """
        Drop every event that is not on the allowlist, keeping the date keys.

        Dates are preserved even when all of their events are filtered out;
        the embed skips days with no events.

        Args:
            summaries_by_date: Event summaries keyed by date.

        Returns:
            A new dict with the same dates and only allowed summaries.
        """
        return {
            day: [s for s in summaries if WeeklyEventsService.is_allowed_event(s)]
            for day, summaries in summaries_by_date.items()
        }

    @staticmethod
    def build_embed(
        week_start: datetime.date,
        week_end: datetime.date,
        summaries_by_date: dict[datetime.date, list[str]],
    ) -> discord.Embed:
        """
        Build the single embed covering the whole week.

        Events are sparse, so only days that have events are listed, in date
        order, as a compact block in the description: a bold day heading with
        that day's events bulleted beneath it. Days with nothing on them are
        omitted entirely rather than rendered as empty rows.

        Args:
            week_start: First date of the week (inclusive).
            week_end: Last date of the week (inclusive).
            summaries_by_date: Event summaries keyed by date. Missing dates are
                treated as having no events; dates outside the week are ignored.

        Returns:
            A discord.Embed whose description lists the week's events, or says
            nothing is scheduled.
        """
        day_blocks = [
            f"**{day:%A, %b %-d}**\n" + "\n".join(f"• {summary}" for summary in summaries)
            for day, summaries in sorted(summaries_by_date.items())
            if summaries and week_start <= day <= week_end
        ]

        description = "\n\n".join(day_blocks) if day_blocks else NO_EVENTS_TEXT
        if len(description) > EMBED_DESCRIPTION_LIMIT:
            description = description[: EMBED_DESCRIPTION_LIMIT - 1] + "…"

        return discord.Embed(
            title=f"Events for {week_start:%b %-d} – {week_end:%b %-d}",
            description=description,
            color=EMBED_COLOR,
        )

    @staticmethod
    async def _delete_previous_messages(bot: Bot, previous: list[WeeklyEventsAnnouncement]) -> None:
        """
        Delete the Discord messages for previously posted announcements.

        Best-effort: a message that is already gone, or that the bot can no
        longer see, is logged and skipped rather than failing the run.
        """
        for announcement in previous:
            channel = bot.get_channel(int(announcement.channel_id))
            if not isinstance(channel, discord.TextChannel):
                logger.warning(
                    "Cannot delete previous announcement %s: channel %s unavailable",
                    announcement.message_id,
                    announcement.channel_id,
                )
                continue
            try:
                message = await channel.fetch_message(int(announcement.message_id))
                await message.delete()
                logger.info(
                    "Deleted previous weekly events announcement %s", announcement.message_id
                )
            except discord.NotFound:
                logger.info(
                    "Previous weekly events announcement %s was already deleted",
                    announcement.message_id,
                )
            except discord.HTTPException:
                logger.exception(
                    "Failed to delete previous weekly events announcement %s",
                    announcement.message_id,
                )

    @staticmethod
    async def _create_scheduled_events(
        guild: discord.Guild | None, summaries_by_date: dict[datetime.date, list[str]]
    ) -> None:
        """
        Create Discord scheduled events for the week's recognized entries.

        Best-effort and deliberately last: the announcement has already been
        posted by this point, so a failure here is logged and reported but never
        costs the channel its message.
        """
        if guild is None:
            logger.warning("Cannot create scheduled events: announcement channel has no guild")
            return

        try:
            await DiscordEventsService.create_events(guild, summaries_by_date)
        except Exception as e:
            logger.exception("Failed to create Discord scheduled events")
            await send_error_to_discord(
                "**Error** creating Discord scheduled events for the weekly announcement",
                error=e,
            )

    @staticmethod
    async def post_weekly_announcement(
        bot: Bot,
        channel_id: int = ChannelIds.REFERENCES__CHURCH_ANNOUNCEMENTS,
        today: datetime.date | None = None,
    ) -> discord.Message | None:
        """
        Post the announcement for the coming week and remove the previous one.

        The new message is posted first, then the previous announcement is
        deleted, so a failure to send never leaves the channel with no
        announcement at all.

        Args:
            bot: The Discord bot instance.
            channel_id: The channel to announce in.
            today: Override for the current date, for testing.

        Returns:
            The sent message, or None if it could not be sent.
        """
        today = today or datetime.datetime.now(tz=LA_TZ).date()
        week_start, week_end = WeeklyEventsService.get_announcement_week(today)

        resolved_channel_id = resolve_channel_id(channel_id)
        raw_channel = bot.get_channel(resolved_channel_id)
        if not isinstance(raw_channel, discord.TextChannel):
            logger.warning(f"Channel not found with ID: {resolved_channel_id}")
            return None
        channel: discord.TextChannel = raw_channel

        summaries_by_date = await CalendarRepository.get_event_summaries_by_date(
            week_start, week_end
        )
        summaries_by_date = WeeklyEventsService.filter_allowed_events(summaries_by_date)
        embed = WeeklyEventsService.build_embed(week_start, week_end, summaries_by_date)

        async with AsyncSessionLocal() as session:
            previous = await WeeklyEventsAnnouncementRepository.get_all(session)
            session.expunge_all()

        try:
            sent_message = await channel.send(
                embed=embed, allowed_mentions=discord.AllowedMentions.none()
            )
        except discord.HTTPException as e:
            logger.exception(f"Failed to send weekly events announcement to {resolved_channel_id}")
            await send_error_to_discord(
                f"**Error** sending weekly events announcement to channel {resolved_channel_id}",
                error=e,
            )
            return None

        logger.info(
            "Posted weekly events announcement %s for %s-%s",
            sent_message.id,
            week_start,
            week_end,
        )

        try:
            async with AsyncSessionLocal() as session:
                for announcement in await WeeklyEventsAnnouncementRepository.get_all(session):
                    await WeeklyEventsAnnouncementRepository.delete(session, announcement)
                await WeeklyEventsAnnouncementRepository.create(
                    session,
                    message_id=str(sent_message.id),
                    channel_id=str(channel.id),
                    week_start=week_start,
                    week_end=week_end,
                )
                await session.commit()
        except Exception as e:
            logger.exception("Failed to record weekly events announcement %s", sent_message.id)
            await send_error_to_discord(
                f"**Error** recording weekly events announcement `{sent_message.id}`; "
                "next week's run may not delete it",
                error=e,
            )

        await WeeklyEventsService._delete_previous_messages(bot, previous)
        await WeeklyEventsService._create_scheduled_events(channel.guild, summaries_by_date)

        return sent_message
