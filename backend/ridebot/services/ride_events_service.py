"""Database-owned ride events and signups, without Discord client dependencies."""

from dataclasses import dataclass
from datetime import UTC, date, datetime

from ridebot.repositories.ride_events_repository import RideEventsRepository
from shared.core.database import AsyncSessionLocal
from shared.core.enums import AskRidesMessageType
from shared.core.models import RideAnnouncement, RideEvent


@dataclass(frozen=True)
class ReactionChoice:
    """A Discord adapter's observation of one rider's reaction choice."""

    discord_user_id: str
    discord_username: str
    display_name: str
    emoji: str


def _naive_utc(value: datetime) -> datetime:
    """Normalize observations for SQLite, rejecting ambiguous local timestamps."""
    if value.tzinfo is None:
        raise ValueError("Observation timestamps must include a timezone")
    return value.astimezone(UTC).replace(tzinfo=None)


class RideEventsService:
    """Own transaction boundaries for event registration and current signup state."""

    @staticmethod
    async def ensure_event(
        *, guild_id: str, message_type: AskRidesMessageType, event_date: date
    ) -> RideEvent:
        """Persist a dated event before attempting to announce it externally."""
        async with AsyncSessionLocal() as session, session.begin():
            return await RideEventsRepository.ensure_event(
                session, guild_id=guild_id, message_type=message_type.value, event_date=event_date
            )

    @staticmethod
    async def bind_announcement(
        *,
        event_id: int,
        channel_id: str,
        message_id: str,
        signup_emojis: list[str],
        kind: str = "rider",
    ) -> None:
        """Associate a Discord message with an already-persisted event."""
        if kind not in {"rider", "driver"}:
            raise ValueError("Announcement kind must be rider or driver")
        async with AsyncSessionLocal() as session, session.begin():
            if await session.get(RideEvent, event_id) is None:
                raise ValueError("Ride event not found")
            await RideEventsRepository.bind_announcement(
                session,
                event_id=event_id,
                channel_id=channel_id,
                message_id=message_id,
                signup_emojis=list(dict.fromkeys(signup_emojis)),
                kind=kind,
            )

    @staticmethod
    async def record_reaction(
        *, message_id: str, choice: ReactionChoice, active: bool, observed_at: datetime
    ) -> bool:
        """Apply a known announcement's configured choice; ignore unrelated reactions."""
        timestamp = _naive_utc(observed_at)
        async with AsyncSessionLocal() as session, session.begin():
            announcement = await session.get(RideAnnouncement, message_id)
            if announcement is None or choice.emoji not in announcement.signup_emojis:
                return False
            await RideEventsRepository.set_reaction(
                session,
                message_id=message_id,
                discord_user_id=choice.discord_user_id,
                discord_username=choice.discord_username,
                display_name=choice.display_name,
                emoji=choice.emoji,
                active=active,
                observed_at=timestamp,
            )
            return True

    @staticmethod
    async def reconcile(
        *, message_id: str, choices: list[ReactionChoice], observed_at: datetime
    ) -> None:
        """Atomically replace a complete snapshot, retaining newer gateway observations."""
        timestamp = _naive_utc(observed_at)
        async with AsyncSessionLocal() as session, session.begin():
            announcement = await session.get(RideAnnouncement, message_id)
            if announcement is None:
                raise ValueError("Ride announcement not found")
            if not await RideEventsRepository.begin_snapshot(session, message_id, timestamp):
                return
            await RideEventsRepository.clear_snapshot(session, message_id, timestamp)
            for choice in choices:
                if choice.emoji not in announcement.signup_emojis:
                    continue
                await RideEventsRepository.set_reaction(
                    session,
                    message_id=message_id,
                    discord_user_id=choice.discord_user_id,
                    discord_username=choice.discord_username,
                    display_name=choice.display_name,
                    emoji=choice.emoji,
                    active=True,
                    observed_at=timestamp,
                )

    @staticmethod
    async def list_events(*, date_from: date, date_to: date, guild_id: str | None = None):
        """List recorded events independently of Discord availability."""
        async with AsyncSessionLocal() as session:
            return await RideEventsRepository.list_events(
                session, date_from=date_from, date_to=date_to, guild_id=guild_id
            )

    @staticmethod
    async def get_event(event_id: int):
        """Return recorded choices plus roster data, without mutable-name matching."""
        async with AsyncSessionLocal() as session:
            event = await session.get(RideEvent, event_id)
            if event is None:
                return None
            announcements = await RideEventsRepository.announcements(session, event_id)
            choices = await RideEventsRepository.active_signups(session, event_id)
            return event, announcements, choices
