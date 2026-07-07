"""Send-time fellowship season gate — Wed and Fri jobs must be mutually exclusive.

The season toggle syncs feature flags, but flags can drift (feature flag editor,
local-env startup disabling, /feature command). These tests verify the jobs also
check the fellowship season at send time, so an off-season job never sends even
when its feature flag is enabled.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.core.enums import FeatureFlagNames, FellowshipSeason
from bot.repositories.feature_flags_repository import FeatureFlagsRepository


def _patch_season(module: str, season: FellowshipSeason):
    """Patch the fellowship season lookup in the given job module."""
    return patch(
        f"{module}.FellowshipSeasonService.get_season",
        new=AsyncMock(return_value=season),
    )


def _patch_session(module: str):
    """Patch AsyncSessionLocal in the given module with a working async context manager."""
    ctx = patch(f"{module}.AsyncSessionLocal")
    return ctx


class TestFridayRidesSeasonGate:
    """run_ask_rides_fri only sends during the Friday season."""

    @pytest.mark.asyncio
    async def test_blocked_when_season_is_wednesday(self):
        bot = MagicMock()

        with (
            _patch_season("bot.jobs.ask_rides", FellowshipSeason.WEDNESDAY),
            patch("bot.jobs.ask_rides._ask_rides_template", new=AsyncMock()) as mock_send,
        ):
            from bot.jobs.ask_rides import run_ask_rides_fri

            await run_ask_rides_fri.__wrapped__(bot)

        mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_sends_when_season_is_friday(self):
        bot = MagicMock()
        fake_message = MagicMock()
        fake_message.add_reaction = AsyncMock()

        with (
            _patch_season("bot.jobs.ask_rides", FellowshipSeason.FRIDAY),
            patch(
                "bot.jobs.ask_rides.MessageScheduleRepository.is_job_paused",
                new=AsyncMock(return_value=False),
            ),
            _patch_session("bot.jobs.ask_rides") as mock_session_ctx,
            patch(
                "bot.jobs.ask_rides._ask_rides_template", new=AsyncMock(return_value=fake_message)
            ) as mock_send,
        ):
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            from bot.jobs.ask_rides import run_ask_rides_fri

            await run_ask_rides_fri.__wrapped__(bot)

        mock_send.assert_called_once()


class TestWednesdayRidesSeasonGate:
    """run_ask_rides_wed only sends during the Wednesday season."""

    @pytest.mark.asyncio
    async def test_blocked_when_season_is_friday(self):
        bot = MagicMock()

        with (
            _patch_season("bot.jobs.ask_rides", FellowshipSeason.FRIDAY),
            patch("bot.jobs.ask_rides._ask_rides_template", new=AsyncMock()) as mock_send,
            patch("bot.jobs.ask_rides.run_ask_drivers_wed", new=AsyncMock()) as mock_driver,
        ):
            from bot.jobs.ask_rides import run_ask_rides_wed

            await run_ask_rides_wed.__wrapped__(bot)

        mock_send.assert_not_called()
        mock_driver.assert_not_called()


class TestDriverJobsSeasonGate:
    """Driver ask jobs respect the season at send time."""

    @pytest.mark.asyncio
    async def test_friday_drivers_blocked_when_season_is_wednesday(self):
        bot = MagicMock()

        with (
            _patch_season("bot.jobs.ask_drivers", FellowshipSeason.WEDNESDAY),
            patch("bot.jobs.ask_drivers._ask_drivers_template", new=AsyncMock()) as mock_send,
            patch.dict(
                FeatureFlagsRepository._cache,
                {FeatureFlagNames.ASK_FRIDAY_DRIVERS_JOB: True},
            ),
        ):
            from bot.jobs.ask_drivers import run_ask_drivers_fri

            await run_ask_drivers_fri.__wrapped__(bot)

        mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_wednesday_drivers_blocked_when_season_is_friday(self):
        bot = MagicMock()

        with (
            _patch_season("bot.jobs.ask_drivers", FellowshipSeason.FRIDAY),
            patch("bot.jobs.ask_drivers._ask_drivers_template", new=AsyncMock()) as mock_send,
            patch.dict(
                FeatureFlagsRepository._cache,
                {FeatureFlagNames.ASK_WEDNESDAY_DRIVERS_JOB: True},
            ),
        ):
            from bot.jobs.ask_drivers import run_ask_drivers_wed

            await run_ask_drivers_wed.__wrapped__(bot)

        mock_send.assert_not_called()
