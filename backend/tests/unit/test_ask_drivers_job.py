"""Smoke unit tests for bot.jobs.ask_drivers — Wednesday driver message."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.core.enums import Emoji, FeatureFlagNames, JobName


class TestRunAskDriversWedEnum:
    """Enum guards — the feature flag and job name must exist."""

    def test_wednesday_drivers_feature_flag_exists(self):
        assert hasattr(FeatureFlagNames, "ASK_WEDNESDAY_DRIVERS_JOB")
        assert FeatureFlagNames.ASK_WEDNESDAY_DRIVERS_JOB == "ask_wednesday_drivers_job"

    def test_wednesday_job_name_exists(self):
        assert hasattr(JobName, "WEDNESDAY")
        assert JobName.WEDNESDAY == "wednesday"


class TestRunAskDriversWedPaused:
    """run_ask_drivers_wed exits early when the Wednesday job is paused."""

    @pytest.mark.asyncio
    async def test_skips_when_paused(self):
        bot = MagicMock()

        with (
            patch(
                "bot.jobs.ask_drivers.MessageScheduleRepository.is_job_paused",
                new=AsyncMock(return_value=True),
            ),
            patch("bot.jobs.ask_drivers.AsyncSessionLocal") as mock_session_ctx,
            patch("bot.jobs.ask_drivers._ask_drivers_template", new=AsyncMock()) as mock_send,
        ):
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            from bot.jobs.ask_drivers import run_ask_drivers_wed

            await run_ask_drivers_wed.__wrapped__(bot)

        mock_send.assert_not_called()


class TestRunAskDriversWedSends:
    """run_ask_drivers_wed sends the correct message when not paused."""

    @pytest.mark.asyncio
    async def test_sends_when_not_paused(self):
        bot = MagicMock()

        from bot.repositories.feature_flags_repository import FeatureFlagsRepository

        with (
            patch(
                "bot.jobs.ask_drivers.MessageScheduleRepository.is_job_paused",
                new=AsyncMock(return_value=False),
            ),
            patch("bot.jobs.ask_drivers.AsyncSessionLocal") as mock_session_ctx,
            patch("bot.jobs.ask_drivers._ask_drivers_template", new=AsyncMock()) as mock_send,
            patch.dict(
                FeatureFlagsRepository._cache,
                {FeatureFlagNames.ASK_WEDNESDAY_DRIVERS_JOB: True},
            ),
        ):
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            from bot.jobs.ask_drivers import run_ask_drivers_wed

            await run_ask_drivers_wed.__wrapped__(bot)

        mock_send.assert_called_once()
        call_args = mock_send.call_args
        message: str = call_args.args[1]
        emojis: list = call_args.args[2]

        assert "Wednesday felly" in message
        assert Emoji.CAN_DRIVE in emojis
        assert Emoji.CANNOT_DRIVE in emojis
        # Wednesday fellowship uses the Friday emoji set (no lunch emojis)
        assert Emoji.LUNCH not in emojis
        assert Emoji.NO_LUNCH not in emojis

    @pytest.mark.asyncio
    async def test_uses_friday_emoji_set(self):
        """Wednesday fellowship uses the same 5-emoji set as Friday, not Sunday's 7."""
        bot = MagicMock()

        from bot.repositories.feature_flags_repository import FeatureFlagsRepository

        with (
            patch(
                "bot.jobs.ask_drivers.MessageScheduleRepository.is_job_paused",
                new=AsyncMock(return_value=False),
            ),
            patch("bot.jobs.ask_drivers.AsyncSessionLocal") as mock_session_ctx,
            patch("bot.jobs.ask_drivers._ask_drivers_template", new=AsyncMock()) as mock_send,
            patch.dict(
                FeatureFlagsRepository._cache,
                {FeatureFlagNames.ASK_WEDNESDAY_DRIVERS_JOB: True},
            ),
        ):
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            from bot.jobs.ask_drivers import run_ask_drivers_wed

            await run_ask_drivers_wed.__wrapped__(bot)

        emojis: list = mock_send.call_args.args[2]
        assert len(emojis) == 5


class TestRunAskRidesWedCallsDriverJob:
    """run_ask_rides_wed calls run_ask_drivers_wed after sending the rides embed."""

    @pytest.mark.asyncio
    async def test_driver_job_called_after_rides_embed(self):
        bot = MagicMock()
        fake_message = MagicMock()
        fake_message.add_reaction = AsyncMock()

        fake_channel = AsyncMock(spec=["send"])
        fake_channel.send = AsyncMock()
        bot.get_channel = MagicMock(return_value=fake_channel)

        with (
            patch(
                "bot.jobs.ask_rides.MessageScheduleRepository.is_job_paused",
                new=AsyncMock(return_value=False),
            ),
            patch("bot.jobs.ask_rides.AsyncSessionLocal") as mock_session_ctx,
            patch(
                "bot.jobs.ask_rides._ask_rides_template", new=AsyncMock(return_value=fake_message)
            ),
            patch("bot.jobs.ask_rides.run_ask_drivers_wed", new=AsyncMock()) as mock_driver,
        ):
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            import discord

            with patch("bot.jobs.ask_rides.discord.TextChannel", discord.TextChannel):
                fake_channel.__class__ = discord.TextChannel

                from bot.jobs.ask_rides import run_ask_rides_wed

                await run_ask_rides_wed.__wrapped__(bot)

        mock_driver.assert_called_once_with(bot)

    @pytest.mark.asyncio
    async def test_driver_job_not_called_when_paused(self):
        bot = MagicMock()

        with (
            patch(
                "bot.jobs.ask_rides.MessageScheduleRepository.is_job_paused",
                new=AsyncMock(return_value=True),
            ),
            patch("bot.jobs.ask_rides.AsyncSessionLocal") as mock_session_ctx,
            patch("bot.jobs.ask_rides.run_ask_drivers_wed", new=AsyncMock()) as mock_driver,
        ):
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            from bot.jobs.ask_rides import run_ask_rides_wed

            await run_ask_rides_wed.__wrapped__(bot)

        mock_driver.assert_not_called()
