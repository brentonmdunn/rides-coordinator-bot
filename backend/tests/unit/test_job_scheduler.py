"""Unit tests for bot.cogs.job_scheduler — DB-configured schedule wiring at startup."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.core.enums import AskRidesScheduleSlot
from bot.services.ask_rides_schedule_service import EffectiveSchedule
from bot.utils.ask_rides_schedule_defaults import DEFAULT_SCHEDULE


class TestJobSchedulerTimezone:
    """AsyncIOScheduler must be pinned to LA_TZ (latent-timezone-bug fix)."""

    def test_scheduler_constructed_with_la_timezone(self):
        from bot.cogs.job_scheduler import JobScheduler
        from bot.utils.time_helpers import LA_TZ

        wed_schedule = EffectiveSchedule(day_of_week=0, hour=11, minute=0, is_customized=False)
        fri_sun_schedule = EffectiveSchedule(day_of_week=2, hour=12, minute=0, is_customized=False)

        with patch("bot.cogs.job_scheduler.AsyncIOScheduler") as mock_scheduler_cls:
            mock_scheduler = MagicMock()
            mock_scheduler_cls.return_value = mock_scheduler

            JobScheduler(MagicMock(), wed_schedule, fri_sun_schedule)

            mock_scheduler_cls.assert_called_once_with(timezone=LA_TZ)
            mock_scheduler.start.assert_called_once()


class TestJobSchedulerUsesConfiguredSchedule:
    """__init__ builds CronTriggers from the resolved EffectiveSchedule values."""

    def test_uses_customized_wed_and_fri_sun_schedules(self):
        from bot.cogs.job_scheduler import JobScheduler
        from bot.utils.time_helpers import LA_TZ

        wed_schedule = EffectiveSchedule(day_of_week=1, hour=9, minute=30, is_customized=True)
        fri_sun_schedule = EffectiveSchedule(day_of_week=3, hour=14, minute=0, is_customized=True)

        with (
            patch("bot.cogs.job_scheduler.AsyncIOScheduler") as mock_scheduler_cls,
            patch("bot.cogs.job_scheduler.CronTrigger") as mock_cron,
        ):
            mock_scheduler = MagicMock()
            mock_scheduler_cls.return_value = mock_scheduler

            JobScheduler(MagicMock(), wed_schedule, fri_sun_schedule)

        cron_calls = mock_cron.call_args_list
        wed_call = next(c for c in cron_calls if c.kwargs.get("hour") == 9)
        fri_sun_call = next(c for c in cron_calls if c.kwargs.get("hour") == 14)

        assert wed_call.kwargs == {
            "day_of_week": 1,
            "hour": 9,
            "minute": 30,
            "timezone": LA_TZ,
        }
        assert fri_sun_call.kwargs == {
            "day_of_week": 3,
            "hour": 14,
            "minute": 0,
            "timezone": LA_TZ,
        }

        add_job_ids = [call.kwargs.get("id") for call in mock_scheduler.add_job.call_args_list]
        assert "run_ask_rides_wed" in add_job_ids
        assert "run_ask_rides_all" in add_job_ids

    def test_uses_default_schedule_when_not_customized(self):
        from bot.cogs.job_scheduler import JobScheduler
        from bot.utils.time_helpers import LA_TZ

        wed_default = DEFAULT_SCHEDULE[AskRidesScheduleSlot.WEDNESDAY_REMINDER]
        fri_sun_default = DEFAULT_SCHEDULE[AskRidesScheduleSlot.FRI_SUN_GROUP]
        wed_schedule = EffectiveSchedule(
            day_of_week=wed_default.day_of_week,
            hour=wed_default.hour,
            minute=wed_default.minute,
            is_customized=False,
        )
        fri_sun_schedule = EffectiveSchedule(
            day_of_week=fri_sun_default.day_of_week,
            hour=fri_sun_default.hour,
            minute=fri_sun_default.minute,
            is_customized=False,
        )

        with (
            patch("bot.cogs.job_scheduler.AsyncIOScheduler") as mock_scheduler_cls,
            patch("bot.cogs.job_scheduler.CronTrigger") as mock_cron,
        ):
            mock_scheduler_cls.return_value = MagicMock()

            JobScheduler(MagicMock(), wed_schedule, fri_sun_schedule)

        cron_calls = mock_cron.call_args_list
        wed_call = next(c for c in cron_calls if c.kwargs.get("hour") == wed_default.hour)
        fri_sun_call = next(c for c in cron_calls if c.kwargs.get("hour") == fri_sun_default.hour)

        assert wed_call.kwargs["day_of_week"] == wed_default.day_of_week
        assert wed_call.kwargs["minute"] == wed_default.minute
        assert fri_sun_call.kwargs["day_of_week"] == fri_sun_default.day_of_week
        assert fri_sun_call.kwargs["minute"] == fri_sun_default.minute
        assert wed_call.kwargs["timezone"] == LA_TZ


class TestSetupResolvesEffectiveSchedule:
    """setup() reads DB-configured schedules before constructing the cog."""

    @pytest.mark.asyncio
    async def test_setup_uses_db_configured_schedule(self):
        from bot.cogs.job_scheduler import setup

        bot = MagicMock()
        bot.add_cog = AsyncMock()

        customized_wed = EffectiveSchedule(day_of_week=1, hour=9, minute=0, is_customized=True)
        customized_fri_sun = EffectiveSchedule(day_of_week=3, hour=15, minute=0, is_customized=True)

        async def fake_get_effective_schedule(slot):
            if slot == AskRidesScheduleSlot.WEDNESDAY_REMINDER:
                return customized_wed
            return customized_fri_sun

        with (
            patch(
                "bot.cogs.job_scheduler.AskRidesScheduleService.get_effective_schedule",
                new=AsyncMock(side_effect=fake_get_effective_schedule),
            ),
            patch("bot.cogs.job_scheduler.JobScheduler") as mock_job_scheduler_cls,
        ):
            await setup(bot)

        mock_job_scheduler_cls.assert_called_once_with(bot, customized_wed, customized_fri_sun)
        bot.add_cog.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_setup_falls_back_to_defaults_when_service_raises(self):
        """
        Even though get_effective_schedule never raises in practice (it has its
        own fallback), setup() defends against it anyway so a schedule-config
        problem can never block bot startup.
        """
        from bot.cogs.job_scheduler import setup

        bot = MagicMock()
        bot.add_cog = AsyncMock()

        with (
            patch(
                "bot.cogs.job_scheduler.AskRidesScheduleService.get_effective_schedule",
                new=AsyncMock(side_effect=RuntimeError("boom")),
            ),
            patch("bot.cogs.job_scheduler.JobScheduler") as mock_job_scheduler_cls,
        ):
            await setup(bot)

        wed_default = DEFAULT_SCHEDULE[AskRidesScheduleSlot.WEDNESDAY_REMINDER]
        fri_sun_default = DEFAULT_SCHEDULE[AskRidesScheduleSlot.FRI_SUN_GROUP]

        mock_job_scheduler_cls.assert_called_once()
        call_args = mock_job_scheduler_cls.call_args
        wed_schedule_arg = call_args.args[1]
        fri_sun_schedule_arg = call_args.args[2]

        assert wed_schedule_arg.day_of_week == wed_default.day_of_week
        assert wed_schedule_arg.hour == wed_default.hour
        assert wed_schedule_arg.is_customized is False
        assert fri_sun_schedule_arg.day_of_week == fri_sun_default.day_of_week
        assert fri_sun_schedule_arg.is_customized is False
        bot.add_cog.assert_awaited_once()
