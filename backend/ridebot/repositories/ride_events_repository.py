"""
Database access for dated events and current reaction-based signups.

The caller owns the transaction. SQLite upserts make repeated gateway deliveries
idempotent and prevent older snapshots from replacing newer observed changes.
"""

from datetime import date, datetime

from sqlalchemy import delete, or_, select, update
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.ext.asyncio import AsyncSession

from shared.core.models import (
    Locations,
    RideAnnouncement,
    RideAssignment,
    RideDriverOffer,
    RideEvent,
    RideRequest,
    RideSignup,
)


class RideEventsRepository:
    """Persist event identities, announcement bindings, and reaction state."""

    @staticmethod
    async def event_for_message(session: AsyncSession, message_id: str) -> RideEvent | None:
        """Resolve an explicit message mapping without interpreting its content."""
        return await session.scalar(
            select(RideEvent)
            .join(RideAnnouncement, RideAnnouncement.event_id == RideEvent.id)
            .where(RideAnnouncement.message_id == message_id)
        )

    @staticmethod
    async def ensure_event(
        session: AsyncSession, *, guild_id: str, message_type: str, event_date: date
    ) -> RideEvent:
        """Get or create the event without committing the caller's transaction."""
        await session.execute(
            insert(RideEvent)
            .values(guild_id=guild_id, message_type=message_type, event_date=event_date)
            .on_conflict_do_nothing(index_elements=["guild_id", "message_type", "event_date"])
        )
        return (
            await session.scalars(
                select(RideEvent).where(
                    RideEvent.guild_id == guild_id,
                    RideEvent.message_type == message_type,
                    RideEvent.event_date == event_date,
                )
            )
        ).one()

    @staticmethod
    async def bind_announcement(
        session: AsyncSession,
        *,
        event_id: int,
        channel_id: str,
        message_id: str,
        signup_emojis: list[str],
        kind: str = "rider",
    ) -> RideAnnouncement:
        """Bind a message once; reject attempts to reinterpret its event or choices."""
        await session.execute(
            insert(RideAnnouncement)
            .values(
                event_id=event_id,
                channel_id=channel_id,
                message_id=message_id,
                signup_emojis=signup_emojis,
                kind=kind,
            )
            .on_conflict_do_nothing(index_elements=["message_id"])
        )
        row = await session.get(RideAnnouncement, message_id)
        assert row is not None
        if (
            row.event_id != event_id
            or row.channel_id != channel_id
            or set(row.signup_emojis) != set(signup_emojis)
            or row.kind != kind
        ):
            raise ValueError("Announcement is already bound to another event or configuration")
        return row

    @staticmethod
    async def set_reaction(
        session: AsyncSession,
        *,
        message_id: str,
        discord_user_id: str,
        discord_username: str,
        display_name: str,
        emoji: str,
        active: bool,
        observed_at: datetime,
    ) -> None:
        """Apply one choice, retaining removals to guard against stale snapshots."""
        stmt = insert(RideSignup).values(
            message_id=message_id,
            discord_user_id=discord_user_id,
            discord_username=discord_username,
            display_name=display_name,
            emoji=emoji,
            active=active,
            updated_at=observed_at,
        )
        await session.execute(
            stmt.on_conflict_do_update(
                index_elements=["message_id", "discord_user_id", "emoji"],
                set_={
                    "discord_username": stmt.excluded.discord_username,
                    "display_name": stmt.excluded.display_name,
                    "active": stmt.excluded.active,
                    "updated_at": stmt.excluded.updated_at,
                },
                where=RideSignup.updated_at <= observed_at,
            )
        )

    @staticmethod
    async def clear_snapshot(session: AsyncSession, message_id: str, observed_at: datetime) -> None:
        """Clear old choices before applying a complete snapshot in the same transaction."""
        await session.execute(
            update(RideSignup)
            .where(RideSignup.message_id == message_id, RideSignup.updated_at <= observed_at)
            .values(active=False, updated_at=observed_at)
        )

    @staticmethod
    async def begin_snapshot(session: AsyncSession, message_id: str, observed_at: datetime) -> bool:
        """Claim snapshot freshness atomically before changing any choices."""
        result = await session.scalar(
            update(RideAnnouncement)
            .where(
                RideAnnouncement.message_id == message_id,
                RideAnnouncement.deleted_at.is_(None),
                or_(
                    RideAnnouncement.state_changed_at.is_(None),
                    RideAnnouncement.state_changed_at <= observed_at,
                ),
                or_(
                    RideAnnouncement.last_reconciled_at.is_(None),
                    RideAnnouncement.last_reconciled_at <= observed_at,
                ),
            )
            .values(last_reconciled_at=observed_at, last_checked_at=observed_at, sync_error=None)
            .returning(RideAnnouncement.message_id)
        )
        return result is not None

    @staticmethod
    async def list_events(
        session: AsyncSession, *, date_from: date, date_to: date, guild_id: str | None = None
    ) -> list[RideEvent]:
        """Return events in a bounded date range."""
        stmt = select(RideEvent).where(
            RideEvent.event_date >= date_from, RideEvent.event_date <= date_to
        )
        if guild_id is not None:
            stmt = stmt.where(RideEvent.guild_id == guild_id)
        return list(
            (await session.scalars(stmt.order_by(RideEvent.event_date, RideEvent.id))).all()
        )

    @staticmethod
    async def announcements(session: AsyncSession, event_id: int) -> list[RideAnnouncement]:
        """Return all message projections, including their reconciliation freshness."""
        return list(
            (
                await session.scalars(
                    select(RideAnnouncement)
                    .where(RideAnnouncement.event_id == event_id)
                    .order_by(RideAnnouncement.message_id)
                )
            ).all()
        )

    @staticmethod
    async def active_signups(session: AsyncSession, event_id: int):
        """Join current choices to the roster only by immutable Discord ID."""
        result = await session.execute(
            select(RideSignup, Locations)
            .join(RideAnnouncement, RideSignup.message_id == RideAnnouncement.message_id)
            .outerjoin(Locations, Locations.discord_user_id == RideSignup.discord_user_id)
            .where(
                RideAnnouncement.event_id == event_id,
                RideSignup.active.is_(True),
                RideAnnouncement.kind == "rider",
                RideAnnouncement.deleted_at.is_(None),
            )
            .order_by(RideSignup.discord_user_id, RideSignup.message_id, RideSignup.emoji)
        )
        return result.all()

    @staticmethod
    async def current_announcement(session, message_type, channel_id, cycle_start, *, kind="rider"):
        """Select an explicitly dated event for the current cycle, scoped to its channel."""
        from datetime import timedelta

        return await session.scalar(
            select(RideAnnouncement)
            .join(RideEvent)
            .where(
                RideEvent.message_type == message_type,
                RideEvent.event_date >= cycle_start,
                RideEvent.event_date < cycle_start + timedelta(days=7),
                RideAnnouncement.channel_id == str(channel_id),
                RideAnnouncement.kind == kind,
                RideAnnouncement.deleted_at.is_(None),
            )
            .order_by(RideAnnouncement.created_at.desc(), RideAnnouncement.message_id.desc())
            .limit(1)
        )

    @staticmethod
    async def current_event(session, message_type, channel_id, cycle_start, guild_id):
        """Resolve dated events even when their Discord projection was deleted or never existed."""
        from datetime import timedelta

        return await session.scalar(
            select(RideEvent)
            .outerjoin(RideAnnouncement)
            .where(
                RideEvent.message_type == message_type,
                RideEvent.event_date >= cycle_start,
                RideEvent.event_date < cycle_start + timedelta(days=7),
                or_(
                    RideAnnouncement.channel_id == str(channel_id),
                    (RideAnnouncement.message_id.is_(None) & (RideEvent.guild_id == str(guild_id))),
                ),
            )
            .order_by(RideEvent.event_date.desc(), RideEvent.id.desc())
            .limit(1)
        )

    @staticmethod
    async def sync_targets(session, since):
        """Return recent source messages for independent reconciliation."""
        return list(
            (
                await session.scalars(
                    select(RideAnnouncement)
                    .join(RideEvent)
                    .where(RideEvent.event_date >= since, RideAnnouncement.deleted_at.is_(None))
                    .order_by(RideEvent.event_date, RideAnnouncement.message_id)
                )
            ).all()
        )

    @staticmethod
    async def clear_reactions(session, message_id, observed_at, *, emoji=None, deleted=False):
        """Fence old snapshots and retire cleared choices without deleting the event."""
        row = await session.get(RideAnnouncement, message_id)
        if row is not None:
            await RideEventsRepository.lock_event(session, row.event_id)
            await session.refresh(row)
        if row is None or (row.state_changed_at and row.state_changed_at > observed_at):
            return None
        row.state_changed_at = observed_at
        row.last_checked_at = observed_at
        if deleted:
            row.deleted_at = observed_at
            row.sync_error = "Source message deleted"
        stmt = update(RideSignup).where(
            RideSignup.message_id == message_id, RideSignup.updated_at <= observed_at
        )
        if emoji is not None:
            stmt = stmt.where(RideSignup.emoji == emoji)
        await session.execute(stmt.values(active=False, updated_at=observed_at))
        return row

    @staticmethod
    async def source_choices(session, event_id, kind="rider"):
        """Read all current selections for one event/interface role."""
        return list(
            (
                await session.scalars(
                    select(RideSignup)
                    .join(RideAnnouncement)
                    .where(
                        RideAnnouncement.event_id == event_id,
                        RideAnnouncement.kind == kind,
                        RideAnnouncement.deleted_at.is_(None),
                        RideSignup.active.is_(True),
                    )
                    .order_by(RideSignup.updated_at, RideSignup.discord_user_id)
                )
            ).all()
        )

    @staticmethod
    async def requests(session, event_id, *, active_only=True):
        """Read unified participants, including manual/custom requests."""
        stmt = select(RideRequest).where(RideRequest.event_id == event_id)
        if active_only:
            stmt = stmt.where(RideRequest.active.is_(True))
        return list((await session.scalars(stmt.order_by(RideRequest.id))).all())

    @staticmethod
    async def offers(session, event_id):
        """Read confirmed driver capacity and observed availability."""
        return list(
            (
                await session.scalars(
                    select(RideDriverOffer)
                    .where(RideDriverOffer.event_id == event_id)
                    .order_by(RideDriverOffer.id)
                )
            ).all()
        )

    @staticmethod
    async def assignments(session, event_id):
        """Read confirmed assignments for both legs."""
        return list(
            (
                await session.scalars(
                    select(RideAssignment)
                    .where(RideAssignment.event_id == event_id)
                    .order_by(RideAssignment.id)
                )
            ).all()
        )

    @staticmethod
    async def replace_assignments(session, event_id, entries):
        """Replace the event plan within the caller's validated transaction."""
        await session.execute(delete(RideAssignment).where(RideAssignment.event_id == event_id))
        session.add_all(entries)

    @staticmethod
    async def lock_event(session, event_id):
        """Serialize plan/capacity changes before checking cross-row constraints."""
        return await session.scalar(
            update(RideEvent)
            .where(RideEvent.id == event_id)
            .values(guild_id=RideEvent.guild_id)
            .returning(RideEvent.id)
        )

    @staticmethod
    async def roster(session):
        """Index registered riders by stable Discord user ID."""
        return {
            row.discord_user_id: row
            for row in (
                await session.scalars(
                    select(Locations).where(Locations.discord_user_id.is_not(None))
                )
            ).all()
        }
