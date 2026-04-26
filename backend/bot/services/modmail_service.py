"""Service for the modmail feature (DM relay via per-user channels)."""

from __future__ import annotations

import contextlib
import logging
import os
import re
from typing import NamedTuple

import discord

from bot.core.database import AsyncSessionLocal
from bot.core.enums import RoleIds
from bot.core.error_reporter import send_error_to_discord
from bot.core.models import ModmailChannels
from bot.repositories.modmail_repository import ModmailRepository

logger = logging.getLogger(__name__)


# Discord channel names must be <= 100 chars, lowercase, dash-separated.
_INVALID_CHANNEL_CHARS = re.compile(r"[^a-z0-9_-]+")
_CHANNEL_NAME_PREFIX = "dm-"
_CHANNEL_NAME_MAX_LEN = 90

# A Discord user ID is an 17-20 digit integer; accept anything that fits.
_USER_ID_RE = re.compile(r"^\d{15,25}$")


class ModmailError(Exception):
    """Base exception for the modmail service."""


class ModmailConfigError(ModmailError):
    """Raised when modmail is not correctly configured (e.g. missing category)."""


class ModmailDMForbiddenError(ModmailError):
    """Raised when the bot cannot DM a user (privacy settings, no shared guild, etc)."""


class ModmailUserNotFoundError(ModmailError):
    """Raised when a username/ID cannot be resolved to a Discord user."""


class ModmailAmbiguousUserError(ModmailError):
    """Raised when a username matches multiple users across the bot's guilds."""


UserLike = discord.abc.User | str | int


class DMResult(NamedTuple):
    """Result of a ``dm_user`` call."""

    channel: discord.TextChannel
    delivered: bool


def _sanitize_username(username: str) -> str:
    """Sanitize a Discord username for use as a channel-name suffix."""
    lowered = username.lower()
    cleaned = _INVALID_CHANNEL_CHARS.sub("-", lowered).strip("-")
    return cleaned or "user"


def _channel_name_for(user: discord.abc.User) -> str:
    """Build the modmail channel name for a given user."""
    suffix = _sanitize_username(user.name)
    name = f"{_CHANNEL_NAME_PREFIX}{suffix}-{user.id}"
    return name[:_CHANNEL_NAME_MAX_LEN]


class ModmailService:
    """Business logic for relaying DMs through per-user Discord channels."""

    def __init__(self, bot: discord.Client):
        """
        Initialize the service.

        Args:
            bot: The Discord client instance.
        """
        self.bot = bot

    # ------------------------------------------------------------------
    # Configuration helpers
    # ------------------------------------------------------------------
    def _get_category_id(self) -> int:
        """Read the modmail category ID from the env."""
        raw = os.getenv("MODMAIL_CATEGORY_ID")
        if not raw:
            raise ModmailConfigError(
                "MODMAIL_CATEGORY_ID is not set. Please configure the Discord "
                "category ID where modmail channels should be created.",
            )
        try:
            return int(raw)
        except ValueError as exc:
            raise ModmailConfigError(
                f"MODMAIL_CATEGORY_ID='{raw}' is not a valid integer.",
            ) from exc

    def _get_category(self, guild: discord.Guild) -> discord.CategoryChannel:
        """Fetch the configured modmail category, raising if missing."""
        category_id = self._get_category_id()
        category = guild.get_channel(category_id)
        if not isinstance(category, discord.CategoryChannel):
            raise ModmailConfigError(
                f"MODMAIL_CATEGORY_ID={category_id} is not a category in guild '{guild.name}'.",
            )
        return category

    def _build_permissions(
        self,
        guild: discord.Guild,
    ) -> dict[discord.Role | discord.Member, discord.PermissionOverwrite]:
        """
        Build permission overwrites for a modmail channel.

        Only admins and ride coordinators can see/reply; the DM'd user does NOT
        get access (the channel is staff-only).

        Args:
            guild: The Discord guild.

        Returns:
            Dictionary of permission overwrites.
        """
        overwrites: dict[discord.Role | discord.Member, discord.PermissionOverwrite] = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
        }

        ride_coordinator_role = guild.get_role(RoleIds.RIDE_COORDINATOR)
        if ride_coordinator_role:
            overwrites[ride_coordinator_role] = discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
            )

        for role in guild.roles:
            if role.permissions.administrator:
                overwrites[role] = discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                )

        return overwrites

    def _primary_guild(self) -> discord.Guild | None:
        """Return the single guild the bot is in, or None if ambiguous."""
        guilds = list(self.bot.guilds)
        if len(guilds) == 1:
            return guilds[0]
        return None

    # ------------------------------------------------------------------
    # User resolution
    # ------------------------------------------------------------------
    async def resolve_user(self, who: UserLike) -> discord.abc.User:
        """
        Resolve a user-like value into a Discord user object.

        Args:
            who: A ``discord.User``/``Member``, a user ID (``int`` or numeric
                ``str``), or a username string. Usernames are matched against
                members in every guild the bot is in.

        Returns:
            A Discord user object.

        Raises:
            ModmailUserNotFoundError: If no user can be resolved.
            ModmailAmbiguousUserError: If a username matches multiple users.
        """
        if isinstance(who, discord.abc.User):
            return who

        if isinstance(who, int) or (isinstance(who, str) and _USER_ID_RE.match(who)):
            user_id = int(who)
            user = self.bot.get_user(user_id)
            if user is not None:
                return user
            try:
                return await self.bot.fetch_user(user_id)
            except discord.NotFound as exc:
                raise ModmailUserNotFoundError(
                    f"No Discord user found for id={user_id}.",
                ) from exc

        if not isinstance(who, str):
            raise ModmailUserNotFoundError(f"Cannot resolve user from {who!r}.")

        # Username lookup across all guilds the bot is in.
        needle = who.lstrip("@").lower()
        matches: dict[int, discord.Member] = {}
        for guild in self.bot.guilds:
            for member in guild.members:
                if member.name.lower() == needle or str(member).lower() == needle:
                    matches[member.id] = member

        if len(matches) == 1:
            return next(iter(matches.values()))
        if len(matches) > 1:
            raise ModmailAmbiguousUserError(
                f"Username '{who}' matches {len(matches)} users. Pass a user ID instead.",
            )
        raise ModmailUserNotFoundError(f"No Discord user found for username '{who}'.")

    # ------------------------------------------------------------------
    # Channel lifecycle
    # ------------------------------------------------------------------
    async def get_or_create_channel(
        self,
        user: discord.abc.User,
        *,
        guild: discord.Guild | None = None,
    ) -> discord.TextChannel:
        """
        Get the modmail channel for a user, creating one if it does not exist.

        Args:
            user: The Discord user whose modmail channel we need.
            guild: The guild to create the channel in. If None, falls back to the
                bot's only guild (fails if the bot is in multiple guilds).

        Returns:
            The Discord text channel used for modmail with this user.

        Raises:
            ModmailConfigError: If category is missing or guild cannot be chosen.
        """
        if guild is None:
            guild = self._primary_guild()
        if guild is None:
            raise ModmailConfigError(
                "Modmail requires a single-guild bot or an explicit guild; "
                "none provided and bot is in 0 or 2+ guilds.",
            )

        async with AsyncSessionLocal() as session:
            existing = await ModmailRepository.get_by_user_id(session, str(user.id))
            if existing:
                channel = guild.get_channel(int(existing.channel_id))
                if isinstance(channel, discord.TextChannel):
                    return channel
                # DB row points at a channel that no longer exists; drop it so
                # we can re-create.
                await ModmailRepository.delete(session, existing)
                await session.commit()

        category = self._get_category(guild)
        overwrites = self._build_permissions(guild)
        name = _channel_name_for(user)

        channel = await guild.create_text_channel(
            name=name,
            category=category,
            overwrites=overwrites,
            topic=f"Modmail with {user} ({user.id}). Messages here are relayed as DMs.",
            reason=f"Modmail channel for {user} ({user.id}).",
        )

        async with AsyncSessionLocal() as session:
            await ModmailRepository.create(
                session,
                user_id=str(user.id),
                channel_id=str(channel.id),
                username=str(user),
            )
            await session.commit()

        try:
            await channel.send(
                embed=discord.Embed(
                    title="📬 Modmail with this user",
                    description=(
                        f"This channel relays messages between staff and "
                        f"{user.mention} (`{user}` · `{user.id}`).\n\n"
                        "• Any non-bot message posted here is DM'd to the user.\n"
                        "• Their DMs to the bot are mirrored here as embeds."
                    ),
                    color=discord.Color.blurple(),
                ),
            )
        except Exception:
            logger.exception("Failed to send modmail intro message")

        return channel

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def dm_user(
        self,
        who: UserLike,
        message: str,
        *,
        initiator: discord.abc.User | None = None,
        guild: discord.Guild | None = None,
    ) -> DMResult:
        """
        DM a user and mirror the outgoing message in their modmail channel.

        Accepts a ``discord.User``/``Member``, a user ID, or a username string.
        Creates the modmail channel if one doesn't exist yet.

        If the DM cannot be delivered (user has DMs closed, blocked the bot,
        etc.), this method does NOT raise — it posts a ⚠️ delivery-failed embed
        in the mirror channel and returns ``DMResult(channel, delivered=False)``
        so callers can decide what to do.

        Args:
            who: The target user (object, ID, or username).
            message: The message content to send.
            initiator: Optional staff member who triggered this DM (shown in the
                channel mirror). Defaults to the bot itself.
            guild: The guild to use when creating a new channel.

        Returns:
            A ``DMResult`` with the mirror channel and whether delivery succeeded.

        Raises:
            ModmailUserNotFoundError: If the user cannot be resolved.
            ModmailAmbiguousUserError: If a username matches multiple users.
            ModmailConfigError: If modmail is not configured.
        """
        user = await self.resolve_user(who)
        channel = await self.get_or_create_channel(user, guild=guild)

        sender = initiator if initiator is not None else self.bot.user
        sender_label = str(sender) if sender is not None else "Bot"
        sender_icon = (
            sender.display_avatar.url if sender is not None and sender.display_avatar else None
        )

        # Post the outgoing-message embed first so staff have a trail regardless
        # of whether delivery succeeds.
        attempt_embed = discord.Embed(
            description=message or "*(no text)*",
            color=discord.Color.blurple(),
        )
        attempt_embed.set_author(name=f"{sender_label} → {user}", icon_url=sender_icon)
        attempt_embed.set_footer(text=f"User ID: {user.id}")
        await channel.send(embed=attempt_embed)

        try:
            await self._send_dm(user, message, attachments=None)
        except ModmailDMForbiddenError as exc:
            logger.info("dm_user: delivery failed for user %s: %s", user.id, exc)
            await channel.send(
                embed=discord.Embed(
                    title="⚠️ Not delivered",
                    description=(
                        f"{user.mention} has DMs closed or does not share a "
                        "server with the bot. The message above was not delivered."
                    ),
                    color=discord.Color.red(),
                ),
            )
            return DMResult(channel=channel, delivered=False)

        return DMResult(channel=channel, delivered=True)

    # ------------------------------------------------------------------
    # Message relay (listener-driven)
    # ------------------------------------------------------------------
    async def relay_dm_to_channel(self, message: discord.Message) -> None:
        """
        Mirror an inbound DM into the matching modmail channel.

        Args:
            message: The DM message received by the bot.
        """
        user = message.author
        try:
            channel = await self.get_or_create_channel(user)
        except ModmailConfigError:
            logger.exception("relay_dm_to_channel: modmail is not configured")
            await send_error_to_discord(
                "**Modmail config error**: received a DM but `MODMAIL_CATEGORY_ID` "
                "is not set or invalid.",
            )
            return

        embed = discord.Embed(
            description=message.content or "*(no text)*",
            color=discord.Color.green(),
            timestamp=message.created_at,
        )
        embed.set_author(
            name=f"{user} → Bot",
            icon_url=user.display_avatar.url if user.display_avatar else None,
        )
        embed.set_footer(text=f"User ID: {user.id}")

        attachments = [a.url for a in message.attachments]
        if attachments:
            embed.add_field(
                name="Attachments",
                value="\n".join(attachments),
                inline=False,
            )

        await channel.send(embed=embed)

    async def relay_channel_to_dm(self, message: discord.Message) -> None:
        """
        Relay a staff message in a modmail channel to the user as a DM.

        Args:
            message: The staff message posted in the modmail channel.
        """
        channel = message.channel
        if not isinstance(channel, discord.TextChannel):
            return

        # Fast-path: skip DB lookup if the channel isn't in the modmail category.
        try:
            category_id = self._get_category_id()
        except ModmailConfigError:
            return
        if channel.category_id != category_id:
            return

        async with AsyncSessionLocal() as session:
            row = await ModmailRepository.get_by_channel_id(session, str(channel.id))
        if row is None:
            return

        user = await self._resolve_user_row(row)
        if user is None:
            await channel.send(
                embed=discord.Embed(
                    title="⚠️ Could not deliver message",
                    description=(
                        f"Unable to resolve user `{row.user_id}` — they may have "
                        "left the server. Message was not sent."
                    ),
                    color=discord.Color.red(),
                ),
            )
            return

        try:
            await self._send_dm(user, message.content, message.attachments)
        except ModmailDMForbiddenError:
            await channel.send(
                embed=discord.Embed(
                    title="⚠️ Could not DM user",
                    description=(
                        f"{user.mention} has DMs closed or does not share a "
                        "server with the bot. Message was not delivered."
                    ),
                    color=discord.Color.red(),
                ),
            )
            return

        confirm = discord.Embed(
            description=message.content or "*(no text)*",
            color=discord.Color.blurple(),
            timestamp=message.created_at,
        )
        confirm.set_author(
            name=f"{message.author} → {user}",
            icon_url=message.author.display_avatar.url if message.author.display_avatar else None,
        )
        confirm.set_footer(text=f"Delivered via DM · User ID: {user.id}")
        if message.attachments:
            confirm.add_field(
                name="Attachments",
                value="\n".join(a.url for a in message.attachments),
                inline=False,
            )

        await channel.send(embed=confirm)
        with contextlib.suppress(discord.Forbidden, discord.NotFound):
            await message.delete()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    async def _resolve_user_row(self, row: ModmailChannels) -> discord.User | None:
        """Best-effort fetch of a Discord user for a modmail row."""
        user_id = int(row.user_id)
        user = self.bot.get_user(user_id)
        if user is not None:
            return user
        try:
            return await self.bot.fetch_user(user_id)
        except discord.NotFound:
            return None

    async def _send_dm(
        self,
        user: discord.abc.User,
        content: str | None,
        attachments: list[discord.Attachment] | None,
    ) -> None:
        """Send a DM to a user, raising ModmailDMForbiddenError if refused."""
        files: list[discord.File] = []
        try:
            if attachments:
                for att in attachments:
                    try:
                        files.append(await att.to_file())
                    except Exception:
                        logger.exception("Failed to fetch attachment %s", att.url)

            try:
                await user.send(content=content or None, files=files or None)
            except discord.Forbidden as exc:
                raise ModmailDMForbiddenError(str(exc)) from exc
        finally:
            for f in files:
                with contextlib.suppress(Exception):
                    f.close()
