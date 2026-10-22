"""Database-owned ride events and signups, without Discord client dependencies."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from ridebot.repositories.ride_events_repository import RideEventsRepository
from ridebot.utils.time_helpers import get_current_cycle_start
from shared.core.database import AsyncSessionLocal
from shared.core.enums import AskRidesMessage, AskRidesMessageType, ChannelIds, Emoji, RideOption
from shared.core.models import (
    RideAnnouncement,
    RideAssignment,
    RideDriverOffer,
    RideEvent,
    RideRequest,
)
from shared.utils.datetimes import to_iso_utc

ASK_TO_TYPE: dict[str, AskRidesMessageType] = {
    AskRidesMessage.FRIDAY_FELLOWSHIP: AskRidesMessageType.FRIDAY_FELLOWSHIP,
    AskRidesMessage.SUNDAY_SERVICE: AskRidesMessageType.SUNDAY_SERVICE,
    AskRidesMessage.SUNDAY_CLASS: AskRidesMessageType.SUNDAY_CLASS,
}
DAY_TO_TYPE = {
    "friday": AskRidesMessageType.FRIDAY_FELLOWSHIP,
    "sunday": AskRidesMessageType.SUNDAY_SERVICE,
    "sunday_class": AskRidesMessageType.SUNDAY_CLASS,
    "wednesday": AskRidesMessageType.WEDNESDAY_FELLOWSHIP,
}


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
            if announcement is not None:
                await RideEventsRepository.lock_event(session, announcement.event_id)
                await session.refresh(announcement)
            if (
                announcement is None
                or announcement.deleted_at
                or choice.emoji not in announcement.signup_emojis
            ):
                return False
            if announcement.state_changed_at and timestamp < announcement.state_changed_at:
                return False
            if announcement.last_reconciled_at and timestamp < announcement.last_reconciled_at:
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
            await _refresh_workflow(session, announcement.event_id, timestamp)
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
            await _refresh_workflow(session, announcement.event_id, timestamp)

    @staticmethod
    async def clear_reactions(
        *, message_id: str, observed_at: datetime, emoji: str | None = None, deleted: bool = False
    ):
        """Record clear/delete gateway events with a fence against in-flight snapshots."""
        timestamp = _naive_utc(observed_at)
        async with AsyncSessionLocal() as session, session.begin():
            row = await RideEventsRepository.clear_reactions(
                session, message_id, timestamp, emoji=emoji, deleted=deleted
            )
            if row:
                await _refresh_workflow(session, row.event_id, timestamp)

    @staticmethod
    async def mark_sync_error(message_id: str, message: str):
        """Retain saved state on transport/permission failures and expose its freshness."""
        async with AsyncSessionLocal() as session, session.begin():
            row = await session.get(RideAnnouncement, message_id)
            if row:
                row.last_checked_at = datetime.now(UTC).replace(tzinfo=None)
                row.sync_error = message

    @staticmethod
    async def sync_targets():
        """Reconcile current/recent events rather than every historical message."""
        async with AsyncSessionLocal() as session:
            return await RideEventsRepository.sync_targets(
                session, get_current_cycle_start().date() - timedelta(days=7)
            )

    @staticmethod
    async def import_legacy_requests():
        """Keep previously entered non-Discord riders in the canonical workflow on rollout."""
        from ridebot.repositories.non_discord_rides_repository import NonDiscordRidesRepository

        async with AsyncSessionLocal() as session, session.begin():
            return await NonDiscordRidesRepository.import_requests(
                session, get_current_cycle_start().date()
            )

    @staticmethod
    async def resolve_event(
        *,
        day=None,
        message_id=None,
        channel_id=ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS,
        event_id=None,
        kind="rider",
    ):
        """Resolve explicit event IDs or legacy selectors entirely from the database."""
        async with AsyncSessionLocal() as session:
            if event_id is not None:
                return await session.get(RideEvent, int(event_id))
            if message_id is not None:
                announcement = await session.get(RideAnnouncement, str(message_id))
                if announcement is None or announcement.channel_id != str(channel_id):
                    return None
                return await session.get(RideEvent, announcement.event_id)
            message_type = ASK_TO_TYPE.get(str(day)) or DAY_TO_TYPE.get(str(day).lower())
            if message_type is None:
                raise ValueError(f"Unknown ride selector: {day}")
            from ridebot.utils.constants import GUILD_ID

            return await RideEventsRepository.current_event(
                session, str(message_type), channel_id, get_current_cycle_start().date(), GUILD_ID
            )

    @staticmethod
    async def current_message(day, channel_id, *, kind="rider"):
        """Return a stored source ID for compatibility with existing selectors."""
        message_type = ASK_TO_TYPE.get(str(day)) or DAY_TO_TYPE.get(str(day).lower())
        if message_type is None:
            return None
        async with AsyncSessionLocal() as session:
            row = await RideEventsRepository.current_announcement(
                session, str(message_type), channel_id, get_current_cycle_start().date(), kind=kind
            )
            return int(row.message_id) if row else None

    @staticmethod
    async def message_choices(message_id, channel_id):
        """Read recorded choices for a known message, verifying the requested channel."""
        async with AsyncSessionLocal() as session:
            announcement = await session.get(RideAnnouncement, str(message_id))
            if (
                announcement is None
                or announcement.channel_id != str(channel_id)
                or announcement.deleted_at
            ):
                return []
            return [
                r
                for r in await RideEventsRepository.source_choices(
                    session, announcement.event_id, announcement.kind
                )
                if r.message_id == str(message_id)
            ]

    @staticmethod
    async def status_message(day):
        """Build the existing status-card shape from explicit message mappings and saved counts."""
        channel_id = ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS
        message_id = await RideEventsService.current_message(day, channel_id)
        if message_id is None:
            return None
        data = await RideEventsService.breakdown(day, channel_id)
        return {
            "message_id": str(message_id),
            "reactions": {e: len(users) for e, users in data["reactions"].items()},
            "freshness": data["freshness"],
        }

    @staticmethod
    async def breakdown(day, channel_id, *, kind="rider"):
        """Return stored reaction breakdown and freshness without a gateway client."""
        event = await RideEventsService.resolve_event(day=day, channel_id=channel_id, kind=kind)
        if event is None:
            return None
        async with AsyncSessionLocal() as session:
            rows = await RideEventsRepository.source_choices(session, event.id, kind)
            roster = await RideEventsRepository.roster(session)
            announcements = [
                a
                for a in await RideEventsRepository.announcements(session, event.id)
                if a.kind == kind
            ]
            reactions = defaultdict(set)
            names = {}
            for row in rows:
                reactions[row.emoji].add(row.discord_username)
                person = roster.get(row.discord_user_id)
                if person:
                    names[row.discord_username] = person.name
            return {
                "reactions": {emoji: sorted(users) for emoji, users in reactions.items()},
                "username_to_name": names,
                "event_id": event.id,
                "event_date": event.event_date.isoformat(),
                "freshness": freshness(announcements),
            }

    @staticmethod
    async def workflow(event_id):
        """Read all participants, offers, and confirmed assignments for an event."""
        async with AsyncSessionLocal() as session:
            event = await session.get(RideEvent, event_id)
            if event is None:
                return None
            requests = await RideEventsRepository.requests(session, event_id)
            roster = await RideEventsRepository.roster(session)
            offers = await RideEventsRepository.offers(session, event_id)
            assignments = await RideEventsRepository.assignments(session, event_id)
            announcements = await RideEventsRepository.announcements(session, event_id)
            return event, requests, roster, offers, assignments, freshness(announcements)

    @staticmethod
    async def save_request(
        *,
        event_id,
        name,
        location=None,
        details=None,
        discord_user_id=None,
        identity_key=None,
        source="manual",
        pickup=True,
        return_preference="unknown",
        active=True,
    ):
        """Create/update a participant without requiring a Discord account or reaction."""
        if not name.strip() or return_preference not in {
            "home",
            "lunch",
            "custom",
            "unknown",
            "none",
        }:
            raise ValueError("A name and valid return preference are required")
        key = (
            f"discord:{discord_user_id}"
            if discord_user_id
            else (identity_key or f"manual:{uuid4()}")
        )
        now = datetime.now(UTC).replace(tzinfo=None)
        async with AsyncSessionLocal() as session, session.begin():
            if await RideEventsRepository.lock_event(session, event_id) is None:
                raise ValueError("Ride event not found")
            rows = await RideEventsRepository.requests(session, event_id, active_only=False)
            row = next((r for r in rows if r.identity_key == key), None)
            if row is None:
                row = RideRequest(
                    event_id=event_id,
                    identity_key=key,
                    source=source,
                    discord_user_id=discord_user_id,
                )
                session.add(row)
            row.name, row.location, row.details = name.strip(), location, details
            row.active, row.pickup, row.return_preference = active, pickup, return_preference
            row.needs_review = return_preference == "custom" or bool(details)
            row.updated_at = now
            await session.flush()
            for assignment in await RideEventsRepository.assignments(session, event_id):
                if assignment.request_id == row.id and (
                    not active
                    or (assignment.direction == "pickup" and not pickup)
                    or (assignment.direction == "return" and return_preference == "none")
                ):
                    await session.delete(assignment)
            return row

    @staticmethod
    async def save_custom_request(*, message_id, discord_user_id, name, text):
        """Keep a modal request durable even if its coordinator notification fails."""
        async with AsyncSessionLocal() as session:
            event = await RideEventsRepository.event_for_message(session, str(message_id))
        if event is None:
            raise ValueError("Announcement has not been imported into ride events")
        return await RideEventsService.save_request(
            event_id=event.id,
            discord_user_id=str(discord_user_id),
            name=name,
            details=text.strip(),
            source="discord",
            return_preference="custom",
        )

    @staticmethod
    async def save_offer(
        *,
        event_id,
        discord_user_id,
        discord_username,
        capacity,
        directions,
        availability="available",
        return_preference="either",
    ):
        """Confirm capacity and directions; refuse changes that invalidate saved assignments."""
        if capacity is not None and not 1 <= capacity <= 20:
            raise ValueError("Passenger capacity must be between 1 and 20")
        if (
            not directions
            or not set(directions) <= {"pickup", "return"}
            or availability not in {"available", "unavailable", "maybe"}
        ):
            raise ValueError("Invalid driver availability or directions")
        if return_preference not in {"home", "lunch", "either", "unknown", "custom"}:
            raise ValueError("Invalid driver return preference")
        async with AsyncSessionLocal() as session, session.begin():
            if await RideEventsRepository.lock_event(session, event_id) is None:
                raise ValueError("Ride event not found")
            row = next(
                (
                    o
                    for o in await RideEventsRepository.offers(session, event_id)
                    if o.discord_user_id == discord_user_id
                ),
                None,
            )
            if row is None:
                row = RideDriverOffer(event_id=event_id, discord_user_id=discord_user_id)
                session.add(row)
            row.discord_username, row.capacity, row.directions, row.availability = (
                discord_username,
                capacity,
                sorted(set(directions)),
                availability,
            )
            row.return_preference = return_preference
            row.source, row.updated_at = "manual", datetime.now(UTC).replace(tzinfo=None)
            await session.flush()
            _validate_assignments(
                await RideEventsRepository.assignments(session, event_id),
                await RideEventsRepository.requests(session, event_id),
                await RideEventsRepository.offers(session, event_id),
            )
            return row

    @staticmethod
    async def save_assignments(event_id, entries):
        """Atomically validate and replace a confirmed plan using stable request/offer IDs."""
        async with AsyncSessionLocal() as session, session.begin():
            if await RideEventsRepository.lock_event(session, event_id) is None:
                raise ValueError("Ride event not found")
            now = datetime.now(UTC).replace(tzinfo=None)
            rows = [
                RideAssignment(
                    event_id=event_id,
                    request_id=e["request_id"],
                    driver_offer_id=e["driver_offer_id"],
                    direction=e["direction"],
                    updated_at=now,
                )
                for e in entries
            ]
            _validate_assignments(
                rows,
                await RideEventsRepository.requests(session, event_id),
                await RideEventsRepository.offers(session, event_id),
            )
            await RideEventsRepository.replace_assignments(session, event_id, rows)

    @staticmethod
    async def pickup_data(
        *,
        day=None,
        message_id=None,
        event_id=None,
        channel_id=ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS,
        option=None,
    ):
        """Read canonical pickup/return participants with identity-safe Sunday class filtering."""
        event = await RideEventsService.resolve_event(
            day=day, message_id=message_id, event_id=event_id, channel_id=channel_id
        )
        if event is None:
            raise ValueError("Ride event not found; import/reconcile the announcement first")
        workflow = await RideEventsService.workflow(event.id)
        assert workflow is not None
        _, requests, roster, _, _, state = workflow
        async with AsyncSessionLocal() as session:
            latest_choices = {
                r.discord_user_id: r
                for r in await RideEventsRepository.source_choices(session, event.id)
            }
        excluded = set()
        if event.message_type == AskRidesMessageType.SUNDAY_SERVICE and not (
            option and "dropoff" in str(option).lower()
        ):
            async with AsyncSessionLocal() as session:
                class_events = await RideEventsRepository.list_events(
                    session,
                    date_from=event.event_date,
                    date_to=event.event_date,
                    guild_id=event.guild_id,
                )
                for class_event in class_events:
                    if class_event.message_type == AskRidesMessageType.SUNDAY_CLASS:
                        excluded.update(
                            r.identity_key
                            for r in await RideEventsRepository.requests(session, class_event.id)
                        )
        locations, reacted, found = defaultdict(list), set(), set()
        for row in requests:
            if row.identity_key in excluded:
                continue
            if option == RideOption.SUNDAY_DROPOFF_BACK and row.return_preference != "home":
                continue
            if option == RideOption.SUNDAY_DROPOFF_LUNCH and row.return_preference != "lunch":
                continue
            if (option is None or "dropoff" not in str(option).lower()) and not row.pickup:
                continue
            person = roster.get(row.discord_user_id)
            name = person.name if person else row.name
            location = person.location if person else row.location
            # Discord IDs drive joins/filtering; usernames are presentation only.
            username = None
            if row.discord_user_id:
                latest = latest_choices.get(row.discord_user_id)
                username = (
                    latest.discord_username
                    if latest
                    else ((person.discord_username if person else None) or row.discord_user_id)
                )
                reacted.add(username)
            if location:
                locations[location].append((name, username))
                if username:
                    found.add(username)
            elif not username:
                reacted.add(name)
        return locations, reacted, found, event, state

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


def freshness(announcements):
    """Report the oldest source snapshot; a recent gateway event cannot mask missing history."""
    active = [a for a in announcements if a.deleted_at is None]
    times = [a.last_reconciled_at for a in active if a.last_reconciled_at]
    timestamp = min(times) if times and len(times) == len(active) else None
    errors = [a.sync_error for a in announcements if a.sync_error]
    stale = bool(errors) or bool(
        active
        and (
            timestamp is None
            or datetime.now(UTC).replace(tzinfo=None) - timestamp > timedelta(minutes=15)
        )
    )
    return {
        "last_reconciled_at": to_iso_utc(timestamp),
        "is_stale": stale,
        "errors": errors,
        "source_count": len(active),
    }


async def _refresh_workflow(session, event_id, timestamp):
    """Project raw selections into stable participant/driver records in the same transaction."""
    rider_choices = await RideEventsRepository.source_choices(session, event_id)
    grouped = defaultdict(list)
    for row in rider_choices:
        grouped[row.discord_user_id].append(row)
    existing = {
        r.identity_key: r
        for r in await RideEventsRepository.requests(session, event_id, active_only=False)
    }
    roster = await RideEventsRepository.roster(session)
    known = {
        str(e)
        for e in (
            Emoji.LUNCH,
            Emoji.NO_LUNCH,
            Emoji.FRIDAY_FELLOWSHIP,
            Emoji.SUNDAY_CLASS,
            Emoji.DRIVE_BACK,
        )
    }
    for user_id, rows in grouped.items():
        key = f"discord:{user_id}"
        row = existing.get(key)
        if row is None:
            row = RideRequest(
                event_id=event_id,
                identity_key=key,
                discord_user_id=user_id,
                source="discord",
                details=None,
            )
            session.add(row)
        person = roster.get(user_id)
        if row.source == "manual":
            continue
        row.name = person.name if person else rows[-1].display_name
        row.location = person.location if person else row.location
        emojis = {r.emoji for r in rows}
        row.active, row.pickup = True, bool(emojis - {str(Emoji.DRIVE_BACK)})
        preferences = ({"lunch"} if str(Emoji.LUNCH) in emojis else set()) | (
            {"home"} if emojis & {str(Emoji.NO_LUNCH), str(Emoji.FRIDAY_FELLOWSHIP)} else set()
        )
        row.needs_review = bool(emojis - known) or len(preferences) > 1 or bool(row.details)
        row.return_preference = (
            next(iter(preferences))
            if len(preferences) == 1 and not row.needs_review
            else ("custom" if row.needs_review else "unknown")
        )
        row.updated_at = timestamp
    for row in existing.values():
        if row.source == "discord" and row.discord_user_id and row.discord_user_id not in grouped:
            row.active = bool(row.details)
            row.updated_at = timestamp
    drivers = defaultdict(list)
    for row in await RideEventsRepository.source_choices(session, event_id, "driver"):
        drivers[row.discord_user_id].append(row)
    offers = {o.discord_user_id: o for o in await RideEventsRepository.offers(session, event_id)}
    for user_id, rows in drivers.items():
        row = offers.get(user_id)
        if row is None:
            row = RideDriverOffer(event_id=event_id, discord_user_id=user_id)
            session.add(row)
        emojis = {r.emoji for r in rows}
        row.discord_username, row.source = rows[-1].discord_username, "discord"
        row.availability = (
            "unavailable"
            if str(Emoji.CANNOT_DRIVE) in emojis
            else ("maybe" if str(Emoji.SOMETHING_ELSE) in emojis else "available")
        )
        directions = []
        if str(Emoji.DRIVE_THERE) in emojis:
            directions.append("pickup")
        if str(Emoji.DRIVE_BACK) in emojis:
            directions.append("return")
        row.directions = directions or ["pickup", "return"]
        preferences = emojis & {str(Emoji.LUNCH), str(Emoji.NO_LUNCH)}
        row.return_preference = (
            "either"
            if len(preferences) == 2 or str(Emoji.EITHER_NO_PREFERENCE) in emojis
            else (
                "lunch"
                if str(Emoji.LUNCH) in emojis
                else ("home" if str(Emoji.NO_LUNCH) in emojis else "unknown")
            )
        )
        row.updated_at = timestamp
    for user_id, row in offers.items():
        if row.source == "discord" and user_id not in drivers:
            row.availability, row.updated_at = "unavailable", timestamp
    await session.flush()
    # A withdrawn signup/offer cannot leave a confirmed, unsafe assignment behind.
    requests = {r.id: r for r in await RideEventsRepository.requests(session, event_id)}
    driver_map = {o.id: o for o in await RideEventsRepository.offers(session, event_id)}
    for assignment in await RideEventsRepository.assignments(session, event_id):
        offer = driver_map.get(assignment.driver_offer_id)
        request = requests.get(assignment.request_id)
        incompatible_return = bool(
            request
            and offer
            and assignment.direction == "return"
            and request.return_preference in {"home", "lunch"}
            and offer.return_preference not in {request.return_preference, "either"}
        )
        if (
            request is None
            or offer is None
            or offer.availability != "available"
            or assignment.direction not in offer.directions
            or incompatible_return
        ):
            await session.delete(assignment)


def _validate_assignments(rows, requests, offers):
    """Enforce event membership, per-leg uniqueness, request needs, and passenger capacity."""
    participants, drivers = {r.id: r for r in requests}, {o.id: o for o in offers}
    seen, counts = set(), defaultdict(int)
    for row in rows:
        request, offer = participants.get(row.request_id), drivers.get(row.driver_offer_id)
        if request is None or offer is None or row.direction not in {"pickup", "return"}:
            raise ValueError("Assignment must reference an active request and driver in this event")
        if (
            offer.availability != "available"
            or row.direction not in offer.directions
            or offer.capacity is None
        ):
            raise ValueError("Driver must be available with confirmed capacity for this leg")
        if request.discord_user_id == offer.discord_user_id:
            raise ValueError("A driver cannot be assigned as their own passenger")
        if (row.direction == "pickup" and not request.pickup) or (
            row.direction == "return" and request.return_preference == "none"
        ):
            raise ValueError("Passenger did not request this leg")
        if (
            row.direction == "return"
            and request.return_preference in {"home", "lunch"}
            and offer.return_preference not in {request.return_preference, "either"}
        ):
            raise ValueError("Driver return preference does not cover this request")
        key = (row.request_id, row.direction)
        if key in seen:
            raise ValueError("A rider can be assigned only once per leg")
        seen.add(key)
        counts[row.driver_offer_id, row.direction] += 1
        if counts[row.driver_offer_id, row.direction] > offer.capacity:
            raise ValueError("Assignment exceeds driver passenger capacity")
