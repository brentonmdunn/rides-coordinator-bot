"""Unit tests for ridebot.cogs.job_scheduler — DB-configured schedule wiring at startup."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ridebot.services.ask_rides_schedule_service import EffectiveSchedule
from ridebot.services.pickup_summary_service import EffectivePickupSummarySetting
from ridebot.utils.ask_rides_schedule_defaults import DEFAULT_SCHEDULE
from ridebot.utils.pickup_summary_defaults import DEFAULT_SUMMARY_SCHEDULE, SUMMARY_SLOT_TO_JOB_ID
from shared.core.enums import AskRidesScheduleSlot, PickupSummarySlot


def _default_summary_settings() -> dict[PickupSummarySlot, EffectivePickupSummarySetting]:
    return {
        slot: EffectivePickupSummarySetting(
            enabled=True,
            day_of_week=default.day_of_week,
            hour=default.hour,
            minute=default.minute,
            is_customized=False,
        )
        for slot, default in DEFAULT_SUMMARY_SCHEDULE.items()
    }


class TestJobSchedulerTimezone:
    """AsyncIOScheduler must be pinned to LA_TZ (latent-timezone-bug fix)."""

    def test_scheduler_constructed_with_la_timezone(self):
        from ridebot.cogs.job_scheduler import JobScheduler
        from ridebot.utils.time_helpers import LA_TZ

        wed_schedule = EffectiveSchedule(day_of_week=0, hour=11, minute=0, is_customized=False)
        fri_sun_schedule = EffectiveSchedule(day_of_week=2, hour=12, minute=0, is_customized=False)

        with patch("ridebot.cogs.job_scheduler.AsyncIOScheduler") as mock_scheduler_cls:
            mock_scheduler = MagicMock()
            mock_scheduler_cls.return_value = mock_scheduler

            JobScheduler(MagicMock(), wed_schedule, fri_sun_schedule, _default_summary_settings())

            mock_scheduler_cls.assert_called_once_with(timezone=LA_TZ)
            mock_scheduler.start.assert_called_once()


class TestJobSchedulerUsesConfiguredSchedule:
    """__init__ builds CronTriggers from the resolved EffectiveSchedule values."""

    def test_uses_customized_wed_and_fri_sun_schedules(self):
        from ridebot.cogs.job_scheduler import JobScheduler
        from ridebot.utils.time_helpers import LA_TZ

        wed_schedule = EffectiveSchedule(day_of_week=1, hour=9, minute=30, is_customized=True)
        fri_sun_schedule = EffectiveSchedule(day_of_week=3, hour=14, minute=0, is_customized=True)

        with (
            patch("ridebot.cogs.job_scheduler.AsyncIOScheduler") as mock_scheduler_cls,
            patch("ridebot.cogs.job_scheduler.CronTrigger") as mock_cron,
        ):
            mock_scheduler = MagicMock()
            mock_scheduler_cls.return_value = mock_scheduler

            JobScheduler(MagicMock(), wed_schedule, fri_sun_schedule, _default_summary_settings())

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
        from ridebot.cogs.job_scheduler import JobScheduler
        from ridebot.utils.time_helpers import LA_TZ

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
            patch("ridebot.cogs.job_scheduler.AsyncIOScheduler") as mock_scheduler_cls,
            patch("ridebot.cogs.job_scheduler.CronTrigger") as mock_cron,
        ):
            mock_scheduler_cls.return_value = MagicMock()

            JobScheduler(MagicMock(), wed_schedule, fri_sun_schedule, _default_summary_settings())

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
        from ridebot.cogs.job_scheduler import setup

        bot = MagicMock()
        bot.add_cog = AsyncMock()

        customized_wed = EffectiveSchedule(day_of_week=1, hour=9, minute=0, is_customized=True)
        customized_fri_sun = EffectiveSchedule(day_of_week=3, hour=15, minute=0, is_customized=True)

        async def fake_get_effective_schedule(slot):
            if slot == AskRidesScheduleSlot.WEDNESDAY_REMINDER:
                return customized_wed
            return customized_fri_sun

        summary_settings = _default_summary_settings()

        with (
            patch(
                "ridebot.cogs.job_scheduler.AskRidesScheduleService.get_effective_schedule",
                new=AsyncMock(side_effect=fake_get_effective_schedule),
            ),
            patch(
                "ridebot.cogs.job_scheduler.PickupSummaryService.get_effective_settings",
                new=AsyncMock(return_value=summary_settings),
            ),
            patch("ridebot.cogs.job_scheduler.JobScheduler") as mock_job_scheduler_cls,
        ):
            await setup(bot)

        mock_job_scheduler_cls.assert_called_once_with(
            bot, customized_wed, customized_fri_sun, summary_settings
        )
        bot.add_cog.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_setup_falls_back_to_defaults_when_service_raises(self):
        """
        Even though get_effective_schedule never raises in practice (it has its
        own fallback), setup() defends against it anyway so a schedule-config
        problem can never block bot startup.
        """
        from ridebot.cogs.job_scheduler import setup

        bot = MagicMock()
        bot.add_cog = AsyncMock()

        with (
            patch(
                "ridebot.cogs.job_scheduler.AskRidesScheduleService.get_effective_schedule",
                new=AsyncMock(side_effect=RuntimeError("boom")),
            ),
            patch(
                "ridebot.cogs.job_scheduler.PickupSummaryService.get_effective_settings",
                new=AsyncMock(side_effect=RuntimeError("boom")),
            ),
            patch("ridebot.cogs.job_scheduler.JobScheduler") as mock_job_scheduler_cls,
        ):
            await setup(bot)

        wed_default = DEFAULT_SCHEDULE[AskRidesScheduleSlot.WEDNESDAY_REMINDER]
        fri_sun_default = DEFAULT_SCHEDULE[AskRidesScheduleSlot.FRI_SUN_GROUP]

        mock_job_scheduler_cls.assert_called_once()
        call_args = mock_job_scheduler_cls.call_args
        wed_schedule_arg = call_args.args[1]
        fri_sun_schedule_arg = call_args.args[2]
        summary_settings_arg = call_args.args[3]

        assert wed_schedule_arg.day_of_week == wed_default.day_of_week
        assert wed_schedule_arg.hour == wed_default.hour
        assert wed_schedule_arg.is_customized is False
        assert fri_sun_schedule_arg.day_of_week == fri_sun_default.day_of_week
        assert fri_sun_schedule_arg.is_customized is False
        for slot, default in DEFAULT_SUMMARY_SCHEDULE.items():
            assert summary_settings_arg[slot].day_of_week == default.day_of_week
            assert summary_settings_arg[slot].hour == default.hour
            assert summary_settings_arg[slot].enabled is True
            assert summary_settings_arg[slot].is_customized is False
        bot.add_cog.assert_awaited_once()


class TestJobSchedulerRegistersSummaryJobs:
    """__init__ registers both pickup-summary jobs with their configured schedules."""

    def test_registers_friday_and_sunday_summary_jobs(self):
        from ridebot.cogs.job_scheduler import JobScheduler
        from ridebot.utils.time_helpers import LA_TZ

        wed_schedule = EffectiveSchedule(day_of_week=0, hour=11, minute=0, is_customized=False)
        fri_sun_schedule = EffectiveSchedule(day_of_week=2, hour=12, minute=0, is_customized=False)
        summary_settings = {
            PickupSummarySlot.FRIDAY: EffectivePickupSummarySetting(
                enabled=True, day_of_week=4, hour=11, minute=0, is_customized=False
            ),
            PickupSummarySlot.SUNDAY: EffectivePickupSummarySetting(
                enabled=False, day_of_week=5, hour=16, minute=0, is_customized=True
            ),
        }

        with (
            patch("ridebot.cogs.job_scheduler.AsyncIOScheduler") as mock_scheduler_cls,
            patch("ridebot.cogs.job_scheduler.CronTrigger") as mock_cron,
        ):
            mock_scheduler = MagicMock()
            mock_scheduler_cls.return_value = mock_scheduler

            JobScheduler(MagicMock(), wed_schedule, fri_sun_schedule, summary_settings)

        add_job_calls = mock_scheduler.add_job.call_args_list
        add_job_ids = [call.kwargs.get("id") for call in add_job_calls]
        assert SUMMARY_SLOT_TO_JOB_ID[PickupSummarySlot.FRIDAY] in add_job_ids
        assert SUMMARY_SLOT_TO_JOB_ID[PickupSummarySlot.SUNDAY] in add_job_ids

        cron_calls = mock_cron.call_args_list
        friday_call = next(c for c in cron_calls if c.kwargs.get("day_of_week") == 4)
        sunday_call = next(c for c in cron_calls if c.kwargs.get("day_of_week") == 5)
        assert friday_call.kwargs == {
            "day_of_week": 4,
            "hour": 11,
            "minute": 0,
            "timezone": LA_TZ,
        }
        assert sunday_call.kwargs == {
            "day_of_week": 5,
            "hour": 16,
            "minute": 0,
            "timezone": LA_TZ,
        }
