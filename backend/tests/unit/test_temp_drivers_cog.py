"""Unit tests for the temp-driver cog: /add-temp-driver, /remove-temp-driver,
/list-temp-drivers, the is_ride_coordinator check, and the role_monitor hook.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from ridebot.cogs.role_monitor import RoleMonitor
from ridebot.cogs.temp_drivers import TempDrivers
from ridebot.services.temp_driver_service import (
    TempDriverEvent,
    TempDriverGrantInfo,
    TempDriverResult,
)
from shared.core.enums import ChannelIds, FeatureFlagNames, RoleIds
from shared.utils.channels import resolve_channel_id
from shared.utils.checks import UserFacingCheckFailure, is_ride_coordinator

# `resolve_channel_id` reroutes to BOT_STUFF__BOTS when APP_ENV=local (the test
# default), so "in the coordinators channel" must be computed the same way the
# cog computes it, not the raw ChannelIds.SERVING__RIDE_COORDINATORS value.
COORDINATORS_CHANNEL_ID = resolve_channel_id(ChannelIds.SERVING__RIDE_COORDINATORS)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _ridebot_enabled():
    """@bot_enabled reads RideBot's kill switch; seed it so tests don't hit the DB."""
    with patch(
        "shared.repositories.feature_flags_repository.FeatureFlagsRepository._cache",
        {FeatureFlagNames.RIDEBOT: True},
    ):
        yield


@pytest.fixture
def temp_drivers_cog():
    return TempDrivers(MagicMock())


def _make_interaction(channel_id: int, display_name: str = "Coordinator") -> AsyncMock:
    interaction = AsyncMock()
    interaction.data = {"name": "add-temp-driver", "options": []}
    interaction.channel_id = channel_id
    interaction.user = MagicMock()
    interaction.user.display_name = display_name
    return interaction


def _make_member(user_id: int = 555) -> MagicMock:
    member = MagicMock(spec=discord.Member)
    member.id = user_id
    return member


def _make_result(event: TempDriverEvent = TempDriverEvent.GRANTED) -> TempDriverResult:
    grant = TempDriverGrantInfo(
        discord_user_id="555",
        discord_username="alice#0001",
        display_name="Alice",
        expires_at=datetime(2026, 10, 5, 6, 59, 59, tzinfo=UTC),
        granted_by="Coordinator",
    )
    return TempDriverResult(
        grant=grant,
        event=event,
        previous_expires_at=None,
        announcement="🚗 **@Alice** is a temporary driver until **Sat, Oct 5, 11:59 PM** "
        "(<t:1759708799:R>) — added by Coordinator",
    )


# ---------------------------------------------------------------------------
# /add-temp-driver
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_temp_driver_in_coordinators_channel_announces():
    """In the ride-coordinators channel, the announcement is sent non-ephemerally
    and the service is told not to announce itself."""
    cog = TempDrivers(MagicMock())
    interaction = _make_interaction(COORDINATORS_CHANNEL_ID)
    member = _make_member()
    result = _make_result()

    with patch("ridebot.cogs.temp_drivers.TempDriverService", autospec=True) as mock_service_cls:
        mock_service_cls.return_value.grant = AsyncMock(return_value=result)

        await cog.add_temp_driver.callback(cog, interaction, member, "3d")

    mock_service_cls.return_value.grant.assert_awaited_once_with(
        member, "3d", "Coordinator", announce=False
    )
    # Deferred publicly first, so the slow work can't outrun Discord's 3s window.
    interaction.response.defer.assert_awaited_once_with(ephemeral=False, thinking=True)
    interaction.edit_original_response.assert_awaited_once()
    kwargs = interaction.edit_original_response.call_args.kwargs
    assert kwargs["content"] == result.announcement
    assert isinstance(kwargs.get("allowed_mentions"), discord.AllowedMentions)
    interaction.followup.send.assert_not_called()


@pytest.mark.asyncio
async def test_add_temp_driver_elsewhere_replies_ephemeral_and_announces():
    """Outside the coordinators channel, the service announces and the reply is a
    short ephemeral confirmation."""
    cog = TempDrivers(MagicMock())
    interaction = _make_interaction(channel_id=123)
    member = _make_member()
    result = _make_result()

    with patch("ridebot.cogs.temp_drivers.TempDriverService", autospec=True) as mock_service_cls:
        mock_service_cls.return_value.grant = AsyncMock(return_value=result)

        await cog.add_temp_driver.callback(cog, interaction, member, None)

    mock_service_cls.return_value.grant.assert_awaited_once_with(
        member, None, "Coordinator", announce=True
    )
    interaction.response.defer.assert_awaited_once_with(ephemeral=True, thinking=True)
    interaction.followup.send.assert_awaited_once()
    args, kwargs = interaction.followup.send.call_args
    assert "announced in" in args[0]
    assert kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_add_temp_driver_value_error_is_ephemeral():
    cog = TempDrivers(MagicMock())
    interaction = _make_interaction(channel_id=123)
    member = _make_member()

    with patch("ridebot.cogs.temp_drivers.TempDriverService", autospec=True) as mock_service_cls:
        mock_service_cls.return_value.grant = AsyncMock(
            side_effect=ValueError("That time is in the past.")
        )

        await cog.add_temp_driver.callback(cog, interaction, member, "0d")

    interaction.followup.send.assert_awaited_once_with("That time is in the past.", ephemeral=True)
    interaction.delete_original_response.assert_not_called()


@pytest.mark.asyncio
async def test_add_temp_driver_permission_error_is_ephemeral():
    cog = TempDrivers(MagicMock())
    interaction = _make_interaction(channel_id=123)
    member = _make_member()

    with patch("ridebot.cogs.temp_drivers.TempDriverService", autospec=True) as mock_service_cls:
        mock_service_cls.return_value.grant = AsyncMock(
            side_effect=PermissionError("Bot lacks permission to assign roles")
        )

        await cog.add_temp_driver.callback(cog, interaction, member, None)

    interaction.followup.send.assert_awaited_once_with(
        "Bot lacks permission to assign roles", ephemeral=True
    )


@pytest.mark.asyncio
async def test_add_temp_driver_unexpected_error_is_generic_and_reported():
    cog = TempDrivers(MagicMock())
    interaction = _make_interaction(channel_id=123)
    member = _make_member()

    with (
        patch("ridebot.cogs.temp_drivers.TempDriverService", autospec=True) as mock_service_cls,
        patch(
            "ridebot.cogs.temp_drivers.send_error_to_discord", new_callable=AsyncMock
        ) as mock_send_error,
    ):
        mock_service_cls.return_value.grant = AsyncMock(side_effect=RuntimeError("boom"))

        await cog.add_temp_driver.callback(cog, interaction, member, None)

    mock_send_error.assert_awaited_once()
    interaction.followup.send.assert_awaited_once()
    args, kwargs = interaction.followup.send.call_args
    assert kwargs.get("ephemeral") is True
    assert "went wrong" in args[0]


@pytest.mark.asyncio
async def test_add_temp_driver_error_in_coordinators_channel_stays_private():
    """The public "thinking" placeholder is deleted so the error is only shown privately."""
    cog = TempDrivers(MagicMock())
    interaction = _make_interaction(COORDINATORS_CHANNEL_ID)

    with patch("ridebot.cogs.temp_drivers.TempDriverService", autospec=True) as mock_service_cls:
        mock_service_cls.return_value.grant = AsyncMock(side_effect=ValueError("Nope."))

        await cog.add_temp_driver.callback(cog, interaction, _make_member(), None)

    interaction.delete_original_response.assert_awaited_once()
    interaction.followup.send.assert_awaited_once_with("Nope.", ephemeral=True)
    interaction.edit_original_response.assert_not_called()


# ---------------------------------------------------------------------------
# /remove-temp-driver
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_remove_temp_driver_in_coordinators_channel_announces():
    cog = TempDrivers(MagicMock())
    interaction = _make_interaction(COORDINATORS_CHANNEL_ID)
    member = _make_member()
    result = _make_result(event=TempDriverEvent.REVOKED)

    with patch("ridebot.cogs.temp_drivers.TempDriverService", autospec=True) as mock_service_cls:
        mock_service_cls.return_value.revoke = AsyncMock(return_value=result)

        await cog.remove_temp_driver.callback(cog, interaction, member)

    mock_service_cls.return_value.revoke.assert_awaited_once_with(
        str(member.id), "Coordinator", announce=False
    )
    interaction.response.defer.assert_awaited_once_with(ephemeral=False, thinking=True)
    assert interaction.edit_original_response.call_args.kwargs["content"] == result.announcement


@pytest.mark.asyncio
async def test_remove_temp_driver_elsewhere_is_ephemeral():
    cog = TempDrivers(MagicMock())
    interaction = _make_interaction(channel_id=999)
    member = _make_member()
    result = _make_result(event=TempDriverEvent.REVOKED)

    with patch("ridebot.cogs.temp_drivers.TempDriverService", autospec=True) as mock_service_cls:
        mock_service_cls.return_value.revoke = AsyncMock(return_value=result)

        await cog.remove_temp_driver.callback(cog, interaction, member)

    mock_service_cls.return_value.revoke.assert_awaited_once_with(
        str(member.id), "Coordinator", announce=True
    )
    _, kwargs = interaction.followup.send.call_args
    assert kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_remove_temp_driver_value_error_is_ephemeral():
    cog = TempDrivers(MagicMock())
    interaction = _make_interaction(channel_id=123)
    member = _make_member()

    with patch("ridebot.cogs.temp_drivers.TempDriverService", autospec=True) as mock_service_cls:
        mock_service_cls.return_value.revoke = AsyncMock(
            side_effect=ValueError("@bob isn't a temporary driver.")
        )

        await cog.remove_temp_driver.callback(cog, interaction, member)

    interaction.followup.send.assert_awaited_once_with(
        "@bob isn't a temporary driver.", ephemeral=True
    )


# ---------------------------------------------------------------------------
# /list-temp-drivers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_temp_drivers_empty():
    cog = TempDrivers(MagicMock())
    interaction = _make_interaction(channel_id=123)

    with patch("ridebot.cogs.temp_drivers.TempDriverService", autospec=True) as mock_service_cls:
        mock_service_cls.list_grants = AsyncMock(return_value=[])

        await cog.list_temp_drivers.callback(cog, interaction)

    interaction.response.send_message.assert_awaited_once()
    _, kwargs = interaction.response.send_message.call_args
    assert kwargs.get("ephemeral") is True
    embed = kwargs.get("embed")
    assert embed is not None
    assert embed.description == "No temporary drivers."


@pytest.mark.asyncio
async def test_list_temp_drivers_shows_grants():
    cog = TempDrivers(MagicMock())
    interaction = _make_interaction(channel_id=123)
    grant = TempDriverGrantInfo(
        discord_user_id="555",
        discord_username="alice#0001",
        display_name="Alice",
        expires_at=datetime(2026, 10, 5, 6, 59, 59, tzinfo=UTC),
        granted_by="Coordinator",
    )

    with patch("ridebot.cogs.temp_drivers.TempDriverService", autospec=True) as mock_service_cls:
        mock_service_cls.list_grants = AsyncMock(return_value=[grant])

        await cog.list_temp_drivers.callback(cog, interaction)

    _, kwargs = interaction.response.send_message.call_args
    assert kwargs.get("ephemeral") is True
    embed = kwargs.get("embed")
    assert "Alice" in embed.description
    assert "Coordinator" in embed.description
    assert "<t:" in embed.description


@pytest.mark.asyncio
async def test_list_temp_drivers_unexpected_error_is_generic_and_reported():
    cog = TempDrivers(MagicMock())
    interaction = _make_interaction(channel_id=123)

    with (
        patch("ridebot.cogs.temp_drivers.TempDriverService", autospec=True) as mock_service_cls,
        patch(
            "ridebot.cogs.temp_drivers.send_error_to_discord", new_callable=AsyncMock
        ) as mock_send_error,
    ):
        mock_service_cls.list_grants = AsyncMock(side_effect=RuntimeError("boom"))

        await cog.list_temp_drivers.callback(cog, interaction)

    mock_send_error.assert_awaited_once()
    _, kwargs = interaction.response.send_message.call_args
    assert kwargs.get("ephemeral") is True


# ---------------------------------------------------------------------------
# is_ride_coordinator
# ---------------------------------------------------------------------------


def _extract_predicate(check_decorator):
    async def _dummy():
        pass

    decorated = check_decorator(_dummy)
    return decorated.__discord_app_commands_checks__[0]


def _make_check_interaction(
    *, is_admin_member: bool = False, has_coordinator_role: bool = False, no_user: bool = False
) -> MagicMock:
    interaction = MagicMock(spec=discord.Interaction)
    interaction.guild = MagicMock()
    if no_user:
        interaction.user = None
        return interaction

    member = MagicMock(spec=discord.Member)
    member.guild_permissions.administrator = is_admin_member
    role = MagicMock()
    role.id = int(RoleIds.RIDE_COORDINATOR) if has_coordinator_role else 999999
    member.roles = [role]
    interaction.user = member
    return interaction


@pytest.mark.asyncio
async def test_is_ride_coordinator_passes_for_coordinator_role():
    interaction = _make_check_interaction(has_coordinator_role=True)
    predicate = _extract_predicate(is_ride_coordinator())
    assert await predicate(interaction) is True


@pytest.mark.asyncio
async def test_is_ride_coordinator_passes_for_admin():
    interaction = _make_check_interaction(is_admin_member=True)
    predicate = _extract_predicate(is_ride_coordinator())
    assert await predicate(interaction) is True


@pytest.mark.asyncio
async def test_is_ride_coordinator_fails_for_plain_member():
    interaction = _make_check_interaction()
    predicate = _extract_predicate(is_ride_coordinator())
    with pytest.raises(UserFacingCheckFailure, match="Only ride coordinators"):
        await predicate(interaction)


@pytest.mark.asyncio
async def test_is_ride_coordinator_fails_in_dm():
    interaction = MagicMock(spec=discord.Interaction)
    interaction.guild = None
    interaction.user = MagicMock()
    predicate = _extract_predicate(is_ride_coordinator())
    with pytest.raises(UserFacingCheckFailure, match="Only ride coordinators"):
        await predicate(interaction)


@pytest.mark.asyncio
async def test_is_ride_coordinator_fails_without_user():
    interaction = _make_check_interaction(no_user=True)
    predicate = _extract_predicate(is_ride_coordinator())
    with pytest.raises(UserFacingCheckFailure, match="Only ride coordinators"):
        await predicate(interaction)


@pytest.mark.asyncio
async def test_is_ride_coordinator_fails_for_non_member_user():
    interaction = MagicMock(spec=discord.Interaction)
    interaction.guild = MagicMock()
    interaction.user = MagicMock(spec=discord.User)
    predicate = _extract_predicate(is_ride_coordinator())
    with pytest.raises(UserFacingCheckFailure, match="Only ride coordinators"):
        await predicate(interaction)


# ---------------------------------------------------------------------------
# role_monitor clear-grant hook
# ---------------------------------------------------------------------------


def _make_role_member(role_ids: list[int], user_id: int = 555, name: str = "alice") -> MagicMock:
    member = MagicMock(spec=discord.Member)
    member.id = user_id
    member.name = name
    member.roles = [MagicMock(id=rid) for rid in role_ids]
    return member


@pytest.mark.asyncio
async def test_role_monitor_clears_grant_when_driver_removed():
    cog = RoleMonitor(MagicMock())
    before = _make_role_member([int(RoleIds.DRIVER)])
    after = _make_role_member([])

    with patch(
        "ridebot.cogs.role_monitor.TempDriverService.clear_grant", new_callable=AsyncMock
    ) as mock_clear:
        await cog.on_member_update(before, after)

    mock_clear.assert_awaited_once_with(str(after.id))


@pytest.mark.asyncio
async def test_role_monitor_does_not_clear_grant_when_driver_added():
    cog = RoleMonitor(MagicMock())
    before = _make_role_member([])
    after = _make_role_member([int(RoleIds.DRIVER)])

    with patch(
        "ridebot.cogs.role_monitor.TempDriverService.clear_grant", new_callable=AsyncMock
    ) as mock_clear:
        await cog.on_member_update(before, after)

    mock_clear.assert_not_awaited()


@pytest.mark.asyncio
async def test_role_monitor_clear_grant_failure_is_logged_not_raised():
    cog = RoleMonitor(MagicMock())
    before = _make_role_member([int(RoleIds.DRIVER)])
    after = _make_role_member([])

    with patch(
        "ridebot.cogs.role_monitor.TempDriverService.clear_grant",
        new_callable=AsyncMock,
        side_effect=RuntimeError("db down"),
    ):
        await cog.on_member_update(before, after)  # must not raise
