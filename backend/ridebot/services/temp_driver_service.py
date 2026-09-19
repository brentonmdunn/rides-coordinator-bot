"""Service for temporary Driver role grants: grant, revoke, list, and expire."""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

import discord
from discord.ext import commands

from ridebot.repositories.temp_driver_grants_repository import TempDriverGrantsRepository
from ridebot.services.role_management_service import RoleManagementService
from ridebot.utils.constants import GUILD_ID
from ridebot.utils.duration_parsing import parse_expiry
from ridebot.utils.parsing import parse_discord_username
from shared.core.bot_instance import get_bot
from shared.core.database import AsyncSessionLocal
from shared.core.enums import BotName, ChannelIds, RoleIds
from shared.core.error_reporter import send_error_to_discord
from shared.utils.channels import resolve_channel_id
from shared.utils.constants import LA_TZ

logger = logging.getLogger(__name__)


class TempDriverEvent(StrEnum):
    """What happened to a temporary grant."""

    GRANTED = "granted"
    EXTENDED = "extended"
    REVOKED = "revoked"
    EXPIRED = "expired"


@dataclass(frozen=True)
class TempDriverGrantInfo:
    """A temporary grant as returned to cogs and API routes."""

    discord_user_id: str
    discord_username: str
    display_name: str
    expires_at: datetime  # timezone-aware UTC
    granted_by: str


@dataclass(frozen=True)
class TempDriverResult:
    """Outcome of grant/revoke. ``announcement`` is always populated."""

    grant: TempDriverGrantInfo
    event: TempDriverEvent
    previous_expires_at: datetime | None  # timezone-aware UTC; set only for EXTENDED
    announcement: str


def _as_aware_utc(dt: datetime) -> datetime:
    """Attach UTC tzinfo to a naive datetime read from the DB."""
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def format_expiry(expires_at: datetime) -> tuple[str, str]:
    """Return (LA-formatted absolute time, Discord relative-time markdown)."""
    la_dt = expires_at.astimezone(LA_TZ)
    when = la_dt.strftime("%a, %b %-d, %-I:%M %p")
    rel = f"<t:{int(expires_at.timestamp())}:R>"
    return when, rel


def build_announcement(
    event: TempDriverEvent,
    display_name: str,
    expires_at: datetime,
    actor: str | None,
    previous_expires_at: datetime | None = None,
) -> str:
    """Build the coordinators-channel message for a grant event. Pure function."""
    name = f"**@{display_name}**"
    when, rel = format_expiry(expires_at)

    if event == TempDriverEvent.GRANTED:
        return f"🚗 {name} is a temporary driver until **{when}** ({rel}) — added by {actor}"
    if event == TempDriverEvent.EXTENDED:
        prev_when = format_expiry(previous_expires_at)[0] if previous_expires_at else "unknown"
        return (
            f"🚗 {name}'s temporary driver role now ends **{when}** ({rel}), "
            f"was {prev_when} — updated by {actor}"
        )
    if event == TempDriverEvent.REVOKED:
        return f"🚗 {name}'s temporary Driver role was removed early by {actor}"
    if event == TempDriverEvent.EXPIRED:
        return f"🚗 {name}'s temporary Driver role expired (granted by {actor})"
    raise ValueError(f"Unknown temp driver event: {event}")  # pragma: no cover - exhaustive enum


class TempDriverService:
    """Temporary Driver role grants. Instantiate with the RideBot instance."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @property
    def guild(self) -> discord.Guild:
        """The configured guild, resolved at call time. Raises if unavailable."""
        guild = self.bot.get_guild(GUILD_ID)
        if guild is None:
            raise ValueError("Guild not available")
        return guild

    def _driver_role(self) -> discord.Role:
        role = self.guild.get_role(int(RoleIds.DRIVER))
        if role is None:
            raise ValueError("Driver role not found in server")
        return role

    def resolve_member(self, username: str) -> discord.Member:
        """Find a guild member by username. Raises ValueError if not found."""
        username = parse_discord_username(username)
        member = self.guild.get_member_named(username)
        if member is None:
            raise ValueError(f"Member '{username}' not found in server")
        return member

    async def grant(
        self,
        member: discord.Member,
        duration_text: str | None,
        granted_by: str,
        *,
        announce: bool = True,
    ) -> TempDriverResult:
        """Grant (or extend) a temporary Driver role."""
        now = datetime.now(UTC)
        expires_at = parse_expiry(duration_text, now)

        role = self._driver_role()
        has_role = role in member.roles

        async with AsyncSessionLocal() as session:
            existing = await TempDriverGrantsRepository.get(session, str(member.id))

        if has_role and existing is None:
            raise ValueError(f"@{member.name} already has the Driver role permanently.")

        role_added = False
        if not has_role:
            try:
                await member.add_roles(
                    role, reason=f"Temporary driver until {format_expiry(expires_at)[0]}"
                )
                role_added = True
            except discord.Forbidden:
                raise PermissionError("Bot lacks permission to assign roles")  # noqa: B904
            except discord.HTTPException as e:
                raise ValueError(f"Discord error adding role: {e}")  # noqa: B904

        try:
            async with AsyncSessionLocal() as session:
                await TempDriverGrantsRepository.upsert(
                    session, str(member.id), str(member.name), expires_at, granted_by
                )
                await session.commit()
        except Exception:
            if role_added:
                try:
                    await member.remove_roles(
                        role, reason="Rollback: temporary driver DB write failed"
                    )
                except Exception:
                    logger.exception(
                        "Failed to roll back Driver role for %s after DB write failure",
                        member.id,
                    )
            raise

        event = TempDriverEvent.EXTENDED if existing is not None else TempDriverEvent.GRANTED
        previous_expires_at = _as_aware_utc(existing.expires_at) if existing is not None else None

        grant_info = TempDriverGrantInfo(
            discord_user_id=str(member.id),
            discord_username=str(member.name),
            display_name=member.display_name,
            expires_at=expires_at,
            granted_by=granted_by,
        )
        announcement = build_announcement(
            event, member.display_name, expires_at, granted_by, previous_expires_at
        )

        if announce:
            await self.announce(announcement)

        logger.info(
            "%s temporary Driver role for %s (%s) until %s, granted by %s",
            "Extended" if event == TempDriverEvent.EXTENDED else "Granted",
            member.name,
            member.id,
            expires_at.isoformat(),
            granted_by,
        )

        return TempDriverResult(
            grant=grant_info,
            event=event,
            previous_expires_at=previous_expires_at,
            announcement=announcement,
        )

    async def revoke(
        self, discord_user_id: str, actor: str, *, announce: bool = True
    ) -> TempDriverResult:
        """Remove a temporary driver's role and grant early."""
        async with AsyncSessionLocal() as session:
            existing = await TempDriverGrantsRepository.get(session, discord_user_id)

        member = self.guild.get_member(int(discord_user_id))

        if existing is None:
            name = member.name if member is not None else discord_user_id
            raise ValueError(
                f"@{name} isn't a temporary driver. "
                "Use the Drivers tab to remove a permanent driver."
            )

        role = self._driver_role()
        if member is not None and role in member.roles:
            try:
                await member.remove_roles(role, reason="Temporary driver removed early")
            except discord.Forbidden:
                raise PermissionError("Bot lacks permission to remove roles")  # noqa: B904
            except discord.HTTPException as e:
                raise ValueError(f"Discord error removing role: {e}")  # noqa: B904

        async with AsyncSessionLocal() as session:
            await TempDriverGrantsRepository.delete(session, discord_user_id)
            await session.commit()

        display_name = member.display_name if member is not None else existing.discord_username
        previous_expires_at = _as_aware_utc(existing.expires_at)
        announcement = build_announcement(
            TempDriverEvent.REVOKED, display_name, previous_expires_at, actor
        )

        if announce:
            await self.announce(announcement)

        logger.info(
            "Revoked temporary Driver role for %s (%s), by %s",
            display_name,
            discord_user_id,
            actor,
        )

        grant_info = TempDriverGrantInfo(
            discord_user_id=discord_user_id,
            discord_username=existing.discord_username,
            display_name=display_name,
            expires_at=previous_expires_at,
            granted_by=existing.granted_by,
        )

        return TempDriverResult(
            grant=grant_info,
            event=TempDriverEvent.REVOKED,
            previous_expires_at=None,
            announcement=announcement,
        )

    async def add_permanent_driver(self, username: str) -> dict:
        """Add the Driver role permanently, converting an existing temp grant."""
        member = self.resolve_member(username)

        async with AsyncSessionLocal() as session:
            existing = await TempDriverGrantsRepository.get(session, str(member.id))

        if existing is not None:
            await TempDriverService.clear_grant(str(member.id))
            return {
                "discord_user_id": str(member.id),
                "discord_username": str(member.name),
                "display_name": member.display_name,
            }

        return await RoleManagementService.add_member(username, self.guild, RoleIds.DRIVER)

    async def remove_driver(self, discord_user_id: str, actor: str) -> dict:
        """Remove the Driver role; temp drivers go through ``revoke`` (announced)."""
        async with AsyncSessionLocal() as session:
            existing = await TempDriverGrantsRepository.get(session, discord_user_id)

        if existing is not None:
            result = await self.revoke(discord_user_id, actor, announce=True)
            return {
                "discord_user_id": result.grant.discord_user_id,
                "discord_username": result.grant.discord_username,
                "display_name": result.grant.display_name,
            }

        return await RoleManagementService.remove_member(
            discord_user_id, self.guild, RoleIds.DRIVER
        )

    async def expire_due(self) -> int:
        """Remove every expired grant's role. Returns the number of rows processed."""
        now = datetime.now(UTC)
        async with AsyncSessionLocal() as session:
            expired = await TempDriverGrantsRepository.list_expired(session, now)

        if not expired:
            logger.debug("Temp driver expiry sweep: nothing to do")
            return 0

        guild = self.bot.get_guild(GUILD_ID)
        if guild is None:
            logger.warning(
                "Guild not available; skipping temp driver expiry sweep (%d due)", len(expired)
            )
            return 0

        processed = 0
        for row in expired:
            try:
                member = guild.get_member(int(row.discord_user_id))
                role = guild.get_role(int(RoleIds.DRIVER))

                if member is None or role is None or role not in member.roles:
                    async with AsyncSessionLocal() as session:
                        await TempDriverGrantsRepository.delete(session, row.discord_user_id)
                        await session.commit()
                    logger.info(
                        "Cleaned up stale temp driver grant for %s (%s) - "
                        "member left or role already gone",
                        row.discord_username,
                        row.discord_user_id,
                    )
                    processed += 1
                    continue

                await member.remove_roles(role, reason="Temporary driver expired")
                async with AsyncSessionLocal() as session:
                    await TempDriverGrantsRepository.delete(session, row.discord_user_id)
                    await session.commit()

                logger.info(
                    "Temporary Driver role expired for %s (%s), granted by %s",
                    member.name,
                    row.discord_user_id,
                    row.granted_by,
                )
                announcement = build_announcement(
                    TempDriverEvent.EXPIRED,
                    member.display_name,
                    _as_aware_utc(row.expires_at),
                    row.granted_by,
                )
                await self.announce(announcement)
                processed += 1
            except Exception:
                logger.exception(
                    "Failed to process expired temp driver grant for %s", row.discord_user_id
                )
                await send_error_to_discord(
                    "**Unexpected Error** processing expired temp driver grant for "
                    f"{row.discord_username} ({row.discord_user_id})"
                )
                continue

        logger.info("Temp driver expiry sweep processed %d grant(s)", processed)
        return processed

    async def announce(self, text: str) -> None:
        """Post ``text`` to the ride coordinators channel (via resolve_channel_id), no pings."""
        try:
            channel = self.bot.get_channel(
                resolve_channel_id(ChannelIds.SERVING__RIDE_COORDINATORS)
            )
            if channel is None or not isinstance(channel, (discord.TextChannel, discord.Thread)):
                logger.warning("Temp driver announcement channel not available; skipping")
                return
            await channel.send(text, allowed_mentions=discord.AllowedMentions.none())
        except Exception:
            logger.exception("Failed to send temp driver announcement")
            await send_error_to_discord("**Unexpected Error** sending temp driver announcement")

    @staticmethod
    async def clear_grant(discord_user_id: str) -> bool:
        """Delete a grant row without touching the role. Returns True if a row existed."""
        async with AsyncSessionLocal() as session:
            existed = await TempDriverGrantsRepository.delete(session, discord_user_id)
            await session.commit()
        return existed

    @staticmethod
    async def list_grants() -> list[TempDriverGrantInfo]:
        """All grants, soonest expiry first."""
        async with AsyncSessionLocal() as session:
            rows = await TempDriverGrantsRepository.list_all(session)

        guild = None
        bot = get_bot(BotName.RIDEBOT)
        if bot is not None:
            guild = bot.get_guild(GUILD_ID)

        infos = []
        for row in rows:
            display_name = row.discord_username
            if guild is not None:
                member = guild.get_member(int(row.discord_user_id))
                if member is not None:
                    display_name = member.display_name
            infos.append(
                TempDriverGrantInfo(
                    discord_user_id=row.discord_user_id,
                    discord_username=row.discord_username,
                    display_name=display_name,
                    expires_at=_as_aware_utc(row.expires_at),
                    granted_by=row.granted_by,
                )
            )
        return infos

    @staticmethod
    async def get_expiry_map() -> dict[str, datetime]:
        """discord_user_id -> expires_at (timezone-aware UTC) for every grant."""
        async with AsyncSessionLocal() as session:
            rows = await TempDriverGrantsRepository.list_all(session)
        return {row.discord_user_id: _as_aware_utc(row.expires_at) for row in rows}
