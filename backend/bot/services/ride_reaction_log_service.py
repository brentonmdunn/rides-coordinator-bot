"""Service for recording ride reaction log events to the database."""

import datetime
import logging
from zoneinfo import ZoneInfo

import discord

from bot.core.database import AsyncSessionLocal
from bot.core.enums import ReactionAction
from bot.repositories.ride_reaction_events_repository import RideReactionEventsRepository
from bot.repositories.whois_repository import WhoisRepository
from bot.utils.parsing import get_message_and_embed_content

logger = logging.getLogger(__name__)

LA_TZ = ZoneInfo("America/Los_Angeles")


class RideReactionLogService:
    """Business logic for persisting ride reaction events."""

    @staticmethod
    async def record_ask_rides_reaction(
        user: discord.Member,
        payload: discord.RawReactionActionEvent,
        message: discord.Message,
        action: ReactionAction,
    ) -> None:
        """
        Record a reaction event on an ask-rides announcement message.

        Detects the ride type from message content, resolves the user's display
        name from the database, and persists the event. Exceptions are logged
        but never re-raised so this never blocks the reaction handler.

        Args:
            user: The Discord member who reacted.
            payload: The raw reaction action payload.
            message: The message that was reacted to.
            action: Whether the reaction was added or removed.
        """
        try:
            logger.debug(
                "record_ask_rides_reaction: user=%s emoji=%s action=%s message_id=%s",
                user.name,
                payload.emoji,
                action,
                payload.message_id,
            )
            content = get_message_and_embed_content(message)
            logger.debug("record_ask_rides_reaction: content=%r", content[:200] if content else "")
            ride_type = _detect_ride_type(content)
            logger.debug("record_ask_rides_reaction: detected ride_type=%s", ride_type)

            # Convert to LA timezone before extracting the date so late-evening
            # UTC timestamps (e.g. 23:00 UTC = 15:00 LA) resolve to the correct day.
            created_at = message.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=datetime.UTC)
            ride_date = created_at.astimezone(LA_TZ).date()
            logger.debug("record_ask_rides_reaction: ride_date=%s", ride_date)

            discord_username = user.name

            async with AsyncSessionLocal() as session:
                display_name = await WhoisRepository.get_display_name(session, discord_username)
                logger.debug(
                    "record_ask_rides_reaction: display_name=%s, writing to DB", display_name
                )
                await RideReactionEventsRepository.record_event(
                    session=session,
                    message_id=str(payload.message_id),
                    discord_username=discord_username,
                    display_name=display_name,
                    emoji=str(payload.emoji),
                    action=action.value,
                    occurred_at=datetime.datetime.now(datetime.UTC),
                    ride_date=ride_date,
                    ride_type=ride_type,
                )
            logger.info(
                "record_ask_rides_reaction: saved event user=%s emoji=%s action=%s ride_type=%s ride_date=%s",
                discord_username,
                payload.emoji,
                action,
                ride_type,
                ride_date,
            )
        except Exception:
            logger.exception("Failed to record ask-rides reaction event")


def _detect_ride_type(content: str) -> str | None:
    """
    Detect the ride type from lowercased message content.

    Args:
        content: The combined message and embed text (already lowercased by
            get_message_and_embed_content).

    Returns:
        One of "sunday_class", "sunday", "friday", "wednesday", or None.
    """
    lowered = content.lower()
    if "sunday" in lowered and "class" in lowered:
        return "sunday_class"
    if "sunday" in lowered:
        return "sunday"
    if "friday" in lowered:
        return "friday"
    if "wednesday" in lowered:
        return "wednesday"
    return None
