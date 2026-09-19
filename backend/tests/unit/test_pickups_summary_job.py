"""Smoke unit tests for ridebot.jobs.pickups_summary."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ridebot.jobs.pickups_summary import run_friday_pickups_summary, run_sunday_pickups_summary
from shared.core.bot_context import current_bot_var
from shared.core.enums import BotName, FeatureFlagNames, PickupSummarySlot


@pytest.fixture(autouse=True)
def _set_current_bot():
    """bot_enabled fails closed without a current bot set — RideBot owns these jobs."""
    token = current_bot_var.set(BotName.RIDEBOT)
    yield
    current_bot_var.reset(token)


class TestFeatureFlagGate:
    @pytest.mark.asyncio
    async def test_friday_job_blocked_when_flag_disabled(self):
        bot = MagicMock()

        with (
            patch(
                "shared.repositories.feature_flags_repository.FeatureFlagsRepository._cache",
                {FeatureFlagNames.FRIDAY_PICKUPS_SUMMARY_JOB: False},
            ),
            patch(
                "ridebot.jobs.pickups_summary.PickupSummaryService.send_summary", new=AsyncMock()
            ) as mock_send,
        ):
            await run_friday_pickups_summary(bot)

        mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_sunday_job_blocked_when_flag_disabled(self):
        bot = MagicMock()

        with (
            patch(
                "shared.repositories.feature_flags_repository.FeatureFlagsRepository._cache",
                {FeatureFlagNames.SUNDAY_PICKUPS_SUMMARY_JOB: False},
            ),
            patch(
                "ridebot.jobs.pickups_summary.PickupSummaryService.send_summary", new=AsyncMock()
            ) as mock_send,
        ):
            await run_sunday_pickups_summary(bot)

        mock_send.assert_not_called()


class TestFeatureFlagAllows:
    @pytest.mark.asyncio
    async def test_friday_job_calls_send_summary_when_flag_enabled(self):
        bot = MagicMock()

        with (
            patch(
                "shared.repositories.feature_flags_repository.FeatureFlagsRepository._cache",
                {FeatureFlagNames.RIDEBOT: True, FeatureFlagNames.FRIDAY_PICKUPS_SUMMARY_JOB: True},
            ),
            patch(
                "ridebot.jobs.pickups_summary.PickupSummaryService.send_summary", new=AsyncMock()
            ) as mock_send,
        ):
            await run_friday_pickups_summary(bot)

        mock_send.assert_awaited_once_with(PickupSummarySlot.FRIDAY)

    @pytest.mark.asyncio
    async def test_sunday_job_calls_send_summary_when_flag_enabled(self):
        bot = MagicMock()

        with (
            patch(
                "shared.repositories.feature_flags_repository.FeatureFlagsRepository._cache",
                {FeatureFlagNames.RIDEBOT: True, FeatureFlagNames.SUNDAY_PICKUPS_SUMMARY_JOB: True},
            ),
            patch(
                "ridebot.jobs.pickups_summary.PickupSummaryService.send_summary", new=AsyncMock()
            ) as mock_send,
        ):
            await run_sunday_pickups_summary(bot)

        mock_send.assert_awaited_once_with(PickupSummarySlot.SUNDAY)
