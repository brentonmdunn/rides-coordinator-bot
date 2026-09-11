"""Unit tests for ridebot/services/ride_request_service.py."""

from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from ridebot.services.ride_request_service import RideRequestService
from ridebot.views.registration import RegistrationView
from shared.core.enums import CategoryIds


def _make_guild_and_category(existing_channel=None):
    category = MagicMock(spec=discord.CategoryChannel)
    category.id = int(CategoryIds.NEW_RIDES)
    category.channels = [existing_channel] if existing_channel else []

    guild = MagicMock(spec=discord.Guild)
    guild.categories = [category]
    guild.roles = []
    guild.default_role = MagicMock()
    guild.get_role.return_value = None
    return guild, category


def _make_user(name="alice"):
    user = MagicMock(spec=discord.Member)
    user.name = name
    user.mention = f"<@{name}>"
    return user


def _make_new_channel():
    channel = MagicMock(spec=discord.TextChannel)
    channel.name = "alice"
    channel.mention = "#alice"
    channel.send = AsyncMock()
    return channel


@pytest.mark.asyncio
async def test_welcome_message_attaches_view_and_pins():
    guild, _ = _make_guild_and_category()
    guild.create_text_channel = AsyncMock()
    new_channel = _make_new_channel()
    guild.create_text_channel.return_value = new_channel
    sent_message = MagicMock()
    sent_message.pin = AsyncMock()
    new_channel.send.return_value = sent_message

    bot = MagicMock()
    bot.get_channel.return_value = None
    service = RideRequestService(bot)

    result = await service.handle_new_rider_reaction(_make_user(), guild)

    assert result is True
    new_channel.send.assert_awaited_once()
    _, kwargs = new_channel.send.call_args
    assert isinstance(kwargs["view"], RegistrationView)
    sent_message.pin.assert_awaited_once()


@pytest.mark.asyncio
async def test_flow_continues_when_pin_fails():
    guild, _ = _make_guild_and_category()
    guild.create_text_channel = AsyncMock()
    new_channel = _make_new_channel()
    guild.create_text_channel.return_value = new_channel
    sent_message = MagicMock()
    sent_message.pin = AsyncMock(side_effect=discord.Forbidden(MagicMock(status=403), "no perms"))
    new_channel.send.return_value = sent_message

    bot = MagicMock()
    bot.get_channel.return_value = None
    service = RideRequestService(bot)

    result = await service.handle_new_rider_reaction(_make_user(), guild)

    assert result is True
    sent_message.pin.assert_awaited_once()
