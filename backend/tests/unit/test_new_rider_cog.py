"""Unit tests for the /prompt-new-rider cog command."""

from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from ridebot.cogs.new_rider import NewRider
from ridebot.services.pickup_info_service import Person
from shared.core.enums import FeatureFlagNames


@pytest.fixture(autouse=True)
def _ridebot_enabled():
    """@bot_enabled reads RideBot's kill switch; seed it so tests don't hit the DB."""
    with patch(
        "shared.repositories.feature_flags_repository.FeatureFlagsRepository._cache",
        {FeatureFlagNames.RIDEBOT: True},
    ):
        yield


@pytest.fixture
def cog():
    return NewRider(MagicMock())


_UNSET = object()


def _make_interaction(guild=_UNSET) -> AsyncMock:
    interaction = AsyncMock()
    interaction.data = {"name": "prompt-new-rider", "options": []}
    interaction.guild = MagicMock() if guild is _UNSET else guild
    interaction.user = MagicMock()
    return interaction


def _make_member(user_id: int = 555, name: str = "shane9910199") -> MagicMock:
    member = MagicMock(spec=discord.Member)
    member.id = user_id
    member.name = name
    member.mention = f"<@{user_id}>"
    return member


def _person(location: str | None = "La Jolla") -> Person:
    return Person(
        id=1,
        name="Shane",
        discord_username="shane9910199",
        discord_user_id="555",
        year=None,
        location=location,
        phone=None,
        updated_at=None,
    )


@pytest.mark.asyncio
async def test_dm_is_rejected(cog):
    interaction = _make_interaction(guild=None)
    await cog.prompt_new_rider.callback(cog, interaction, _make_member())
    interaction.response.send_message.assert_awaited_once()
    assert "server" in interaction.response.send_message.await_args.args[0].lower()


@pytest.mark.asyncio
@patch("ridebot.cogs.new_rider.RideRequestService")
@patch("ridebot.cogs.new_rider.PickupInfoService.find_member", new_callable=AsyncMock)
async def test_already_registered_skips(find_member, ride_request_service, cog):
    find_member.return_value = _person()
    interaction = _make_interaction()

    await cog.prompt_new_rider.callback(cog, interaction, _make_member())

    ride_request_service.assert_not_called()
    msg = interaction.followup.send.await_args.args[0]
    assert "already registered" in msg
    assert "La Jolla" in msg


@pytest.mark.asyncio
@patch("ridebot.cogs.new_rider.RideRequestService")
@patch("ridebot.cogs.new_rider.PickupInfoService.find_member", new_callable=AsyncMock)
async def test_unregistered_posts_prompt(find_member, ride_request_service, cog):
    find_member.return_value = None
    ride_request_service.return_value.handle_new_rider_reaction = AsyncMock(return_value=True)
    interaction = _make_interaction()
    member = _make_member()

    await cog.prompt_new_rider.callback(cog, interaction, member)

    ride_request_service.return_value.handle_new_rider_reaction.assert_awaited_once_with(
        member, interaction.guild
    )
    assert "Posted" in interaction.followup.send.await_args.args[0]


@pytest.mark.asyncio
@patch("ridebot.cogs.new_rider.RideRequestService")
@patch("ridebot.cogs.new_rider.PickupInfoService.find_member", new_callable=AsyncMock)
async def test_unregistered_nothing_posted(find_member, ride_request_service, cog):
    find_member.return_value = None
    ride_request_service.return_value.handle_new_rider_reaction = AsyncMock(return_value=False)
    interaction = _make_interaction()

    await cog.prompt_new_rider.callback(cog, interaction, _make_member())

    assert "Nothing posted" in interaction.followup.send.await_args.args[0]


@pytest.mark.asyncio
@patch("ridebot.cogs.new_rider.send_error_to_discord", new_callable=AsyncMock)
@patch("ridebot.cogs.new_rider.RideRequestService")
@patch("ridebot.cogs.new_rider.PickupInfoService.find_member", new_callable=AsyncMock)
async def test_unexpected_error_is_reported(find_member, ride_request_service, send_error, cog):
    find_member.return_value = None
    ride_request_service.return_value.handle_new_rider_reaction = AsyncMock(
        side_effect=RuntimeError("boom")
    )
    interaction = _make_interaction()

    await cog.prompt_new_rider.callback(cog, interaction, _make_member())

    send_error.assert_awaited_once()
    assert "went wrong" in interaction.followup.send.await_args.args[0]
