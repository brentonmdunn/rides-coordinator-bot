"""Best-effort attribution of new members to invite creators in the server admin bot spam channel."""

import asyncio
import logging
from dataclasses import dataclass

import discord
from discord.ext import commands

from shared.core.enums import ChannelIds
from shared.core.error_reporter import send_error_to_discord
from shared.utils.channels import resolve_channel_id

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class InviteSnapshot:
    """Copy invite metadata so later Discord updates cannot mutate the baseline."""

    uses: int
    creator_id: int | None


class InviteTracking(commands.Cog):
    """Track invites in the destination guild; loaded by exactly one bot."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._invites: dict[str, InviteSnapshot] | None = None
        self._lock = asyncio.Lock()
        self._generation = 0

    def _channel(self) -> discord.TextChannel | None:
        channel = self.bot.get_channel(
            resolve_channel_id(ChannelIds.SERVING__SERVER_ADMIN_BOT_SPAM)
        )
        return channel if isinstance(channel, discord.TextChannel) else None

    async def _fetch(self, guild: discord.Guild) -> dict[str, InviteSnapshot] | None:
        try:
            invites = await guild.invites()
            return {
                invite.code: InviteSnapshot(
                    uses=invite.uses or 0,
                    creator_id=invite.inviter.id if invite.inviter else None,
                )
                for invite in invites
            }
        except discord.Forbidden:
            logger.warning("Invite tracking needs Manage Server permission in guild %s", guild.id)
        except discord.HTTPException as error:
            logger.exception("Failed to fetch invites for guild %s", guild.id)
            await send_error_to_discord("Failed to fetch invites for join tracking", error)
        return None

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Seed a fresh baseline on startup or a new gateway session."""
        async with self._lock:
            self._invites = None
            channel = self._channel()
            if channel is None:
                logger.warning("Invite tracking destination #server-admin-bot-spam is unavailable")
                return
            generation = self._generation
            snapshot = await self._fetch(channel.guild)
            if generation == self._generation:
                self._invites = snapshot

    @commands.Cog.listener()
    async def on_disconnect(self) -> None:
        """Discard counts across gaps; missed joins must not be attributed later."""
        self._generation += 1
        self._invites = None

    @commands.Cog.listener()
    async def on_resumed(self) -> None:
        """Refresh after reconnecting, including successful session resumes."""
        await self.on_ready()

    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite) -> None:
        """Remember newly created links without refreshing other usage counts."""
        channel = self._channel()
        if channel is None or invite.guild is None or invite.guild.id != channel.guild.id:
            return
        async with self._lock:
            if self._invites is not None and invite.code not in self._invites:
                self._invites[invite.code] = InviteSnapshot(
                    uses=invite.uses or 0,
                    creator_id=invite.inviter.id if invite.inviter else None,
                )

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        """Publish a join, attributing only a single observed invite use."""
        channel = self._channel()
        if channel is None or member.guild.id != channel.guild.id:
            return

        # Serialize comparisons and updates so concurrent handlers cannot reuse a delta.
        async with self._lock:
            previous = self._invites
            generation = self._generation
            current = await self._fetch(member.guild)
            if generation != self._generation:
                current = None
            self._invites = current
            attribution = "Invite creator: **unknown** (no reliable invite match)."
            if current is None:
                attribution = (
                    "Invite creator: **unknown** (invite lookup unavailable; "
                    "check Manage Server permission)."
                )
            elif previous is not None:
                changed = [
                    (code, invite, invite.uses - previous[code].uses)
                    for code, invite in current.items()
                    if code in previous and invite.uses > previous[code].uses
                ]
                # Missing links may have expired or been consumed. New links may
                # already have been used. Both make even a single delta ambiguous.
                uncertain_links = bool(previous.keys() - current.keys()) or any(
                    invite.uses > 0 for code, invite in current.items() if code not in previous
                )
                if len(changed) == 1 and changed[0][2] == 1 and not uncertain_links:
                    code, invite, _ = changed[0]
                    if invite.creator_id is not None:
                        attribution = (
                            f"Likely invite creator: <@{invite.creator_id}> "
                            f"(invite `{discord.utils.escape_markdown(code)}`)."
                        )

            logger.info("Member %s joined guild %s: %s", member.id, member.guild.id, attribution)
            try:
                await channel.send(
                    f"👋 <@{member.id}> joined **{discord.utils.escape_markdown(member.guild.name)}**. "
                    f"{attribution}",
                    allowed_mentions=discord.AllowedMentions.none(),
                )
            except discord.HTTPException as error:
                logger.exception("Failed to publish join for member %s", member.id)
                await send_error_to_discord(
                    "Failed to publish invite tracking event to #server-admin-bot-spam", error
                )


async def setup(bot: commands.Bot) -> None:
    """Install the invite tracking listener."""
    await bot.add_cog(InviteTracking(bot))
