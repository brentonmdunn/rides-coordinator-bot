"""Service for temporary Driver role grants: grant, revoke, list, and expire."""

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

import discord
from discord.ext import commands

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


def build_announcement(
    event: TempDriverEvent,
    display_name: str,
    expires_at: datetime,
    actor: str | None,
    previous_expires_at: datetime | None = None,
) -> str:
    """Build the coordinators-channel message for a grant event. Pure function."""
    raise NotImplementedError


class TempDriverService:
    """Temporary Driver role grants. Instantiate with the RideBot instance."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def resolve_member(self, username: str) -> discord.Member:
        """Find a guild member by username. Raises ValueError if not found."""
        raise NotImplementedError

    async def grant(
        self,
        member: discord.Member,
        duration_text: str | None,
        granted_by: str,
        *,
        announce: bool = True,
    ) -> TempDriverResult:
        """Grant (or extend) a temporary Driver role."""
        raise NotImplementedError

    async def revoke(
        self, discord_user_id: str, actor: str, *, announce: bool = True
    ) -> TempDriverResult:
        """Remove a temporary driver's role and grant early."""
        raise NotImplementedError

    async def add_permanent_driver(self, username: str) -> dict:
        """Add the Driver role permanently, converting an existing temp grant."""
        raise NotImplementedError

    async def remove_driver(self, discord_user_id: str, actor: str) -> dict:
        """Remove the Driver role; temp drivers go through ``revoke`` (announced)."""
        raise NotImplementedError

    async def expire_due(self) -> int:
        """Remove every expired grant's role. Returns the number of rows processed."""
        raise NotImplementedError

    async def announce(self, text: str) -> None:
        """Post ``text`` to the ride coordinators channel (via resolve_channel_id), no pings."""
        raise NotImplementedError

    @staticmethod
    async def clear_grant(discord_user_id: str) -> bool:
        """Delete a grant row without touching the role. Returns True if a row existed."""
        raise NotImplementedError

    @staticmethod
    async def list_grants() -> list[TempDriverGrantInfo]:
        """All grants, soonest expiry first."""
        raise NotImplementedError

    @staticmethod
    async def get_expiry_map() -> dict[str, datetime]:
        """discord_user_id -> expires_at (timezone-aware UTC) for every grant."""
        raise NotImplementedError
