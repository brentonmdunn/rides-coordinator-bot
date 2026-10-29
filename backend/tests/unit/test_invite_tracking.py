"""Invite attribution behavior without connecting to Discord."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from shared.core.bots import single_bot_extensions_for
from shared.core.enums import BotName, ChannelIds
from shared.single_bot_cogs.invite_tracking import InviteTracking


def invite(code="abc", uses=0, creator=42, guild=None):
    return SimpleNamespace(
        code=code,
        uses=uses,
        inviter=SimpleNamespace(id=creator) if creator is not None else None,
        guild=guild,
    )


@pytest.fixture
def tracker(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    guild = SimpleNamespace(id=10, name="Our server", invites=AsyncMock(return_value=[]))
    channel = MagicMock(spec=discord.TextChannel)
    channel.guild = guild
    channel.send = AsyncMock()
    bot = MagicMock()
    bot.get_channel.return_value = channel
    monkeypatch.setattr("shared.single_bot_cogs.invite_tracking.send_error_to_discord", AsyncMock())
    return InviteTracking(bot), channel, guild


def member(guild, user_id=99):
    return SimpleNamespace(id=user_id, guild=guild)


def message(channel, index=-1):
    return channel.send.await_args_list[index].args[0]


@pytest.mark.asyncio
async def test_posts_creator_without_pinging_and_does_not_reuse_delta(tracker):
    cog, channel, guild = tracker
    guild.invites.return_value = [invite(uses=3)]
    await cog.on_ready()
    guild.invites.return_value = [invite(uses=4)]
    await cog.on_member_join(member(guild))
    assert "<@99> joined" in message(channel)
    assert "Likely invite creator: <@42>" in message(channel)
    assert "`abc`" in message(channel)
    mentions = channel.send.await_args.kwargs["allowed_mentions"]
    assert not mentions.users and not mentions.roles and not mentions.everyone
    cog.bot.get_channel.assert_called_with(int(ChannelIds.SERVING__SERVER_ADMIN_BOT_SPAM))
    await cog.on_member_join(member(guild, 100))
    assert "**unknown**" in message(channel)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("before", "after"),
    [
        ([invite()], [invite(uses=2)]),
        ([invite(), invite("def")], [invite(uses=1), invite("def", uses=1)]),
        ([invite()], []),  # A consumed single-use link cannot be proven.
        ([], [invite(uses=1)]),  # No baseline for this link.
        ([invite()], [invite(uses=1, creator=None)]),
        ([invite(), invite("gone")], [invite(uses=1)]),
        ([invite()], [invite(uses=1), invite("new", uses=1)]),
    ],
)
async def test_uncertain_joins_are_unknown(tracker, before, after):
    cog, channel, guild = tracker
    guild.invites.return_value = before
    await cog.on_ready()
    guild.invites.return_value = after
    await cog.on_member_join(member(guild))
    assert "**unknown**" in message(channel)


@pytest.mark.asyncio
async def test_invite_created_after_startup_is_tracked(tracker):
    cog, channel, guild = tracker
    await cog.on_ready()
    await cog.on_invite_create(invite(guild=guild))
    guild.invites.return_value = [invite(uses=1)]
    await cog.on_member_join(member(guild))
    assert "Likely invite creator: <@42>" in message(channel)


@pytest.mark.asyncio
async def test_disconnect_and_resume_discard_missed_uses(tracker):
    cog, channel, guild = tracker
    guild.invites.return_value = [invite()]
    await cog.on_ready()
    await cog.on_disconnect()
    guild.invites.return_value = [invite(uses=5)]
    await cog.on_resumed()
    await cog.on_member_join(member(guild))
    assert "**unknown**" in message(channel)
    guild.invites.return_value = [invite(uses=6)]
    await cog.on_member_join(member(guild))
    assert "Likely invite creator: <@42>" in message(channel)


@pytest.mark.asyncio
async def test_missing_permission_still_posts_join_and_recovers_with_baseline(tracker):
    cog, channel, guild = tracker
    guild.invites.side_effect = discord.Forbidden(
        SimpleNamespace(status=403, reason="Forbidden"), ""
    )
    await cog.on_ready()
    await cog.on_member_join(member(guild))
    assert "<@99> joined" in message(channel)
    assert "Manage Server" in message(channel)
    guild.invites.side_effect = None
    guild.invites.return_value = [invite(uses=3)]
    await cog.on_member_join(member(guild))
    assert "**unknown**" in message(channel)


@pytest.mark.asyncio
async def test_fetch_failure_clears_baseline(tracker):
    cog, channel, guild = tracker
    guild.invites.return_value = [invite()]
    await cog.on_ready()
    guild.invites.side_effect = discord.HTTPException(
        SimpleNamespace(status=500, reason="Error"), ""
    )
    await cog.on_member_join(member(guild))
    assert "**unknown**" in message(channel)
    assert cog._invites is None
    guild.invites.side_effect = None
    guild.invites.return_value = [invite(uses=1)]
    await cog.on_member_join(member(guild))
    assert "**unknown**" in message(channel)


@pytest.mark.asyncio
async def test_other_guild_is_ignored(tracker):
    cog, channel, guild = tracker
    await cog.on_member_join(member(SimpleNamespace(id=123)))
    await cog.on_invite_create(invite(guild=SimpleNamespace(id=123)))
    guild.invites.assert_not_awaited()
    channel.send.assert_not_awaited()


@pytest.mark.asyncio
async def test_concurrent_joins_cannot_claim_same_delta(tracker):
    cog, channel, guild = tracker
    guild.invites.return_value = [invite()]
    await cog.on_ready()
    guild.invites.return_value = [invite(uses=1)]
    await asyncio.gather(cog.on_member_join(member(guild)), cog.on_member_join(member(guild, 100)))
    assert sum("Likely invite creator" in message(channel, i) for i in range(2)) == 1


@pytest.mark.asyncio
async def test_disconnect_during_fetch_cannot_restore_stale_baseline(tracker):
    cog, channel, guild = tracker

    async def interrupted_fetch():
        await cog.on_disconnect()
        return [invite(uses=1)]

    guild.invites.side_effect = interrupted_fetch
    await cog.on_ready()
    assert cog._invites is None
    await cog.on_member_join(member(guild))
    assert cog._invites is None
    assert "**unknown**" in message(channel)


def test_only_stonesbot_owns_invite_tracking():
    extension = "shared.single_bot_cogs.invite_tracking"
    running = {BotName.RIDEBOT, BotName.STONESBOT}
    assert extension in single_bot_extensions_for(BotName.STONESBOT, running)
    assert extension not in single_bot_extensions_for(BotName.RIDEBOT, running)
    assert extension not in single_bot_extensions_for(BotName.RIDEBOT, {BotName.RIDEBOT})
