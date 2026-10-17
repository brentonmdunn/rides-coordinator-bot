"""Service for recording ride reaction log events to the database."""

import datetime
import logging
from collections import defaultdict
from zoneinfo import ZoneInfo

import discord
from sqlalchemy import select

from ridebot.core import reaction_broadcaster
from ridebot.repositories.ride_reaction_events_repository import RideReactionEventsRepository
from ridebot.utils.parsing import get_message_and_embed_content
from shared.core.database import AsyncSessionLocal
from shared.core.enums import ReactionAction
from shared.core.models import Locations
from shared.utils.datetimes import to_iso_utc

logger = logging.getLogger(__name__)

LA_TZ = ZoneInfo("America/Los_Angeles")


class RideReactionLogService:
    """Business logic for persisting ride reaction events."""

    @staticmethod
    async def broadcast_driver_chat_reaction(
        user: discord.Member,
        payload: discord.RawReactionActionEvent,
        action: ReactionAction,
    ) -> None:
        """
        Broadcast a driver-chat reaction event to SSE subscribers.

        Driver-chat reactions are not persisted to the reaction log; this only
        notifies live listeners (e.g. the driver reactions and ride coverage
        views) so they can refetch. Exceptions are logged but never re-raised.

        Args:
            user: The Discord member who reacted.
            payload: The raw reaction action payload.
            action: Whether the reaction was added or removed.
        """
        try:
            await reaction_broadcaster.publish(
                {
                    "source": "driver_chat",
                    "message_id": str(payload.message_id),
                    "discord_username": user.name,
                    "emoji": str(payload.emoji),
                    "action": action.value,
                    "occurred_at": to_iso_utc(datetime.datetime.now(datetime.UTC)),
                }
            )
        except Exception:
            logger.exception("Failed to broadcast driver-chat reaction event")

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

            occurred_at = datetime.datetime.now(datetime.UTC)
            async with AsyncSessionLocal() as session:
                display_name = user.display_name
                logger.debug(
                    "record_ask_rides_reaction: display_name=%s, writing to DB", display_name
                )
                event_row = await RideReactionEventsRepository.record_event(
                    session=session,
                    message_id=str(payload.message_id),
                    discord_username=discord_username,
                    discord_user_id=str(user.id),
                    display_name=display_name,
                    emoji=str(payload.emoji),
                    action=action.value,
                    occurred_at=occurred_at,
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
            await reaction_broadcaster.publish(
                {
                    "source": "rides_announcements",
                    "id": event_row.id,
                    "message_id": event_row.message_id,
                    "discord_username": event_row.discord_username,
                    "discord_user_id": event_row.discord_user_id,
                    "display_name": event_row.display_name,
                    "emoji": event_row.emoji,
                    "action": event_row.action,
                    "occurred_at": to_iso_utc(event_row.occurred_at),
                    "ride_date": event_row.ride_date.isoformat() if event_row.ride_date else None,
                    "ride_type": event_row.ride_type,
                }
            )
        except Exception:
            logger.exception("Failed to record ask-rides reaction event")

    @staticmethod
    async def get_grouped_events(
        ride_type: str | None = None,
        date_from: datetime.date | None = None,
        date_to: datetime.date | None = None,
        emoji: str | None = None,
        search: str | None = None,
        person_id: int | None = None,
        remaining_only: bool = False,
    ) -> list[tuple[str, dict]]:
        """
        Fetch reaction events and return them grouped by message, newest rides first.

        Args:
            ride_type: Optional filter (friday | sunday | sunday_class | wednesday).
            date_from: Include events on or after this ride_date.
            date_to: Include events on or before this ride_date.
            emoji: Filter to a specific emoji string.
            search: Partial name or username, matched across each identity's history.
            person_id: Exact pickup-info person, taking precedence over search.
            remaining_only: Return only latest adds; implicit for person searches.

        Returns:
            Sorted list of (message_id, {"ride_type", "ride_date", "events": [row, ...]}).
        """
        async with AsyncSessionLocal() as session:
            events = await RideReactionEventsRepository.get_events(session)
            people = list((await session.scalars(select(Locations))).all())

        # Resolve identities before matching names or reducing the timeline. A name
        # can match an older event while its latest event uses a newer username.
        username_ids: dict[str, set[str]] = defaultdict(set)
        for person in people:
            if person.discord_username and person.discord_user_id:
                username_ids[person.discord_username.casefold()].add(person.discord_user_id)
        for event in events:
            if event.discord_user_id:
                username_ids[event.discord_username.casefold()].add(event.discord_user_id)

        def identity(user_id: str | None, username: str | None) -> tuple[str, str]:
            if user_id:
                return ("id", user_id)
            normalized = (username or "").casefold()
            ids = username_ids.get(normalized, set())
            if len(ids) == 1:
                return ("id", next(iter(ids)))
            return ("username", normalized)

        term = (search or "").strip().casefold()
        matched = set()
        for person in people:
            if (person_id is not None and person.id == person_id) or (
                person_id is None
                and term
                and any(
                    term in (value or "").casefold()
                    for value in (person.name, person.discord_username)
                )
            ):
                matched.add(identity(person.discord_user_id, person.discord_username))
        if person_id is None and term:
            for event in events:
                if any(
                    term in (value or "").casefold()
                    for value in (
                        event.discord_username,
                        event.display_name,
                    )
                ):
                    matched.add(identity(event.discord_user_id, event.discord_username))
        if term or person_id is not None:
            events = [
                event
                for event in events
                if identity(event.discord_user_id, event.discord_username) in matched
            ]

        if remaining_only or term or person_id is not None:
            latest = {}
            # Repository ordering is timestamp descending, then ID descending.
            for event in events:
                key = (
                    event.message_id,
                    identity(event.discord_user_id, event.discord_username),
                    event.emoji,
                )
                latest.setdefault(key, event)
            events = [event for event in latest.values() if event.action == "add"]
        # Filter after identity matching and state reduction so date filters
        # cannot hide an alias or a later removal of the same reaction.
        events = [
            event
            for event in events
            if (not emoji or event.emoji == emoji)
            and (not ride_type or event.ride_type == ride_type)
            and (not date_from or (event.ride_date is not None and event.ride_date >= date_from))
            and (not date_to or (event.ride_date is not None and event.ride_date <= date_to))
        ]

        groups: dict[str, dict] = defaultdict(
            lambda: {"ride_type": None, "ride_date": None, "events": []}
        )
        for event in events:
            mid = event.message_id
            groups[mid]["ride_type"] = event.ride_type
            groups[mid]["ride_date"] = event.ride_date
            groups[mid]["events"].append(event)

        def _sort_key(item: tuple) -> tuple:
            mid, data = item
            rd = data["ride_date"]
            date_key = rd if rd is not None else datetime.date.min
            return (date_key, mid)

        return sorted(groups.items(), key=_sort_key, reverse=True)


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
