"""Unit tests for the roster-related bits of ridebot/cogs/reactions.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from ridebot.cogs.reactions import Reactions
from ridebot.views.pickup_info import PickupInfoView
from shared.core.enums import AskRidesMessage, FeatureFlagNames
from shared.repositories.feature_flags_repository import FeatureFlagsRepository


@pytest.fixture(autouse=True)
def _enable_new_rides_msg():
    """Enable NEW_RIDES_MSG via the cache so the decorator lets calls through."""
    FeatureFlagsRepository._cache[FeatureFlagNames.NEW_RIDES_MSG] = True
    yield
    FeatureFlagsRepository._cache.pop(FeatureFlagNames.NEW_RIDES_MSG, None)


def _make_cog(locations_cog=None):
    bot = MagicMock()
    bot.get_cog.return_value = locations_cog
    bot.add_view = MagicMock()
    logging_service = AsyncMock()
    ride_request_service = AsyncMock()
    cog = Reactions(bot, logging_service, ride_request_service)
    return cog, bot, ride_request_service


@pytest.mark.asyncio
async def test_cog_load_registers_persistent_view():
    cog, bot, _ = _make_cog()

    await cog.cog_load()

    bot.add_view.assert_called_once()
    registered_view = bot.add_view.call_args.args[0]
    assert isinstance(registered_view, PickupInfoView)


@pytest.mark.asyncio
async def test_new_rides_helper_skips_registered_members():
    locations_cog = MagicMock()
    locations_cog.service.find_correct_message = AsyncMock(return_value=42)
    cog, _, ride_request_service = _make_cog(locations_cog=locations_cog)
    cog.locations_cog = locations_cog
    user = MagicMock(spec=discord.Member)
    user.id = 1
    user.name = "alice"
    guild = MagicMock(spec=discord.Guild)

    with patch(
        "ridebot.cogs.reactions.RosterService.find_member",
        new=AsyncMock(return_value=MagicMock()),
    ):
        await cog._new_rides_helper(user, guild, 42)

    ride_request_service.handle_new_rider_reaction.assert_not_called()


@pytest.mark.asyncio
async def test_new_rides_helper_continues_for_unregistered_members():
    locations_cog = MagicMock()

    async def find_correct_message(event, channel_id):
        return 42 if event == AskRidesMessage.FRIDAY_FELLOWSHIP else 99

    locations_cog.service.find_correct_message = AsyncMock(side_effect=find_correct_message)
    cog, _, ride_request_service = _make_cog(locations_cog=locations_cog)
    cog.locations_cog = locations_cog
    user = MagicMock(spec=discord.Member)
    user.id = 1
    user.name = "alice"
    guild = MagicMock(spec=discord.Guild)

    with patch(
        "ridebot.cogs.reactions.RosterService.find_member",
        new=AsyncMock(return_value=None),
    ):
        await cog._new_rides_helper(user, guild, 42)

    ride_request_service.handle_new_rider_reaction.assert_awaited_once_with(user, guild)
