"""Unit tests for the /send-pickups-summary cog command."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ridebot.cogs.locations import Locations
from shared.core.enums import ChannelIds, PickupSummarySlot


@pytest.fixture
def locations_cog():
    return Locations(MagicMock())


def _interaction(channel_id: int | None = ChannelIds.SERVING__RIDE_COORDINATORS):
    interaction = AsyncMock()
    interaction.data = {"name": "send-pickups-summary", "options": []}
    interaction.user = MagicMock()
    interaction.channel_id = channel_id
    return interaction


@pytest.mark.asyncio
@pytest.mark.parametrize(("sent", "reply"), [(True, "Sent."), (False, "Nothing sent")])
async def test_sends_summary_to_current_channel(locations_cog, sent, reply):
    interaction = _interaction()

    with patch(
        "ridebot.cogs.locations.PickupSummaryService.send_summary", new_callable=AsyncMock
    ) as mock_send:
        mock_send.return_value = sent

        await locations_cog.send_pickups_summary.callback(
            locations_cog, interaction, PickupSummarySlot.SUNDAY
        )

    mock_send.assert_awaited_once_with(
        PickupSummarySlot.SUNDAY,
        channel_id=ChannelIds.SERVING__RIDE_COORDINATORS,
        respect_toggle=False,
    )
    interaction.response.defer.assert_awaited_once_with(ephemeral=True)
    args, kwargs = interaction.followup.send.call_args
    assert args[0].startswith(reply)
    assert kwargs["ephemeral"] is True


@pytest.mark.asyncio
async def test_refuses_non_whitelisted_channel(locations_cog):
    interaction = _interaction(channel_id=123)

    with patch(
        "ridebot.cogs.locations.PickupSummaryService.send_summary", new_callable=AsyncMock
    ) as mock_send:
        await locations_cog.send_pickups_summary.callback(
            locations_cog, interaction, PickupSummarySlot.FRIDAY
        )

    mock_send.assert_not_awaited()
