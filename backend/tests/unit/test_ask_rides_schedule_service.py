"""Unit tests for AskRidesScheduleService."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import OperationalError

from bot.core.enums import AskRidesScheduleSlot, JobName
from bot.services.ask_rides_schedule_service import (
    AskRidesScheduleService,
    EffectiveSchedule,
    get_next_schedule_occurrence,
    has_send_time_passed,
)
from bot.utils.ask_rides_schedule_defaults import DEFAULT_SCHEDULE
from bot.utils.time_helpers import LA_TZ


def _la(year, month, day, hour=0, minute=0):
    """Helper to build a timezone-aware LA datetime."""
    return LA_TZ.localize(datetime(year, month, day, hour, minute))


def _mock_session_local(mock_session_local):
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session_local.return_value = mock_session
    return mock_session


class TestGetEffectiveSchedule:
    @pytest.mark.asyncio
    @patch(
        "bot.services.ask_rides_schedule_service.AskRidesScheduleRepository.get",
        new_callable=AsyncMock,
    )
    @patch("bot.services.ask_rides_schedule_service.AsyncSessionLocal")
    async def test_returns_default_when_row_missing(self, mock_session_local, mock_get):
        _mock_session_local(mock_session_local)
        mock_get.return_value = None

        result = await AskRidesScheduleService.get_effective_schedule(
            AskRidesScheduleSlot.WEDNESDAY_REMINDER
        )

        default = DEFAULT_SCHEDULE[AskRidesScheduleSlot.WEDNESDAY_REMINDER]
        assert result.day_of_week == default.day_of_week
        assert result.hour == default.hour
        assert result.minute == default.minute
        assert result.is_customized is False

    @pytest.mark.asyncio
    @patch(
        "bot.services.ask_rides_schedule_service.AskRidesScheduleRepository.get",
        new_callable=AsyncMock,
    )
    @patch("bot.services.ask_rides_schedule_service.AsyncSessionLocal")
    async def test_returns_db_row_when_present(self, mock_session_local, mock_get):
        _mock_session_local(mock_session_local)
        fake_row = MagicMock(day_of_week=3, hour=14, minute=30)
        mock_get.return_value = fake_row

        result = await AskRidesScheduleService.get_effective_schedule(
            AskRidesScheduleSlot.FRI_SUN_GROUP
        )

        assert result == EffectiveSchedule(day_of_week=3, hour=14, minute=30, is_customized=True)

    @pytest.mark.asyncio
    @patch("bot.services.ask_rides_schedule_service.AsyncSessionLocal")
    async def test_falls_back_to_default_on_operational_error(self, mock_session_local):
        mock_session_local.side_effect = OperationalError("stmt", {}, Exception("no such table"))

        result = await AskRidesScheduleService.get_effective_schedule(
            AskRidesScheduleSlot.WEDNESDAY_REMINDER
        )

        default = DEFAULT_SCHEDULE[AskRidesScheduleSlot.WEDNESDAY_REMINDER]
        assert result.hour == default.hour
        assert result.is_customized is False

    @pytest.mark.asyncio
    @patch("bot.services.ask_rides_schedule_service.AsyncSessionLocal")
    async def test_never_raises_on_unexpected_error(self, mock_session_local):
        mock_session_local.side_effect = RuntimeError("boom")

        result = await AskRidesScheduleService.get_effective_schedule(
            AskRidesScheduleSlot.FRI_SUN_GROUP
        )

        default = DEFAULT_SCHEDULE[AskRidesScheduleSlot.FRI_SUN_GROUP]
        assert result.hour == default.hour
        assert result.is_customized is False


class TestGetEffectiveSchedules:
    @pytest.mark.asyncio
    @patch(
        "bot.services.ask_rides_schedule_service.AskRidesScheduleRepository.get_all",
        new_callable=AsyncMock,
    )
    @patch("bot.services.ask_rides_schedule_service.AsyncSessionLocal")
    async def test_merges_db_rows_over_defaults(self, mock_session_local, mock_get_all):
        _mock_session_local(mock_session_local)
        fake_row = MagicMock(
            slot=AskRidesScheduleSlot.FRI_SUN_GROUP.value, day_of_week=1, hour=13, minute=15
        )
        mock_get_all.return_value = [fake_row]

        result = await AskRidesScheduleService.get_effective_schedules()

        assert result[AskRidesScheduleSlot.FRI_SUN_GROUP].hour == 13
        assert result[AskRidesScheduleSlot.FRI_SUN_GROUP].is_customized is True
        assert result[AskRidesScheduleSlot.WEDNESDAY_REMINDER].is_customized is False

    @pytest.mark.asyncio
    @patch("bot.services.ask_rides_schedule_service.AsyncSessionLocal")
    async def test_falls_back_to_all_defaults_on_db_error(self, mock_session_local):
        mock_session_local.side_effect = OperationalError("stmt", {}, Exception("no such table"))

        result = await AskRidesScheduleService.get_effective_schedules()

        assert len(result) == len(DEFAULT_SCHEDULE)
        assert all(not s.is_customized for s in result.values())


class TestValidate:
    def test_rejects_day_outside_allowed_set(self):
        with pytest.raises(ValueError, match="day_of_week must be one of"):
            AskRidesScheduleService._validate(
                AskRidesScheduleSlot.FRI_SUN_GROUP, day_of_week=4, hour=12, minute=0
            )  # Friday not allowed for FRI_SUN_GROUP

    def test_rejects_sunday_for_wednesday_reminder(self):
        with pytest.raises(ValueError, match="day_of_week must be one of"):
            AskRidesScheduleService._validate(
                AskRidesScheduleSlot.WEDNESDAY_REMINDER, day_of_week=6, hour=11, minute=0
            )

    def test_rejects_out_of_range_hour(self):
        with pytest.raises(ValueError, match="hour must be between"):
            AskRidesScheduleService._validate(
                AskRidesScheduleSlot.WEDNESDAY_REMINDER, day_of_week=0, hour=24, minute=0
            )

    def test_rejects_out_of_range_minute(self):
        with pytest.raises(ValueError, match="minute must be between"):
            AskRidesScheduleService._validate(
                AskRidesScheduleSlot.WEDNESDAY_REMINDER, day_of_week=0, hour=11, minute=60
            )

    def test_rejects_time_before_window(self):
        with pytest.raises(ValueError, match="time must be between"):
            AskRidesScheduleService._validate(
                AskRidesScheduleSlot.WEDNESDAY_REMINDER, day_of_week=0, hour=3, minute=0
            )

    def test_rejects_time_after_window(self):
        with pytest.raises(ValueError, match="time must be between"):
            AskRidesScheduleService._validate(
                AskRidesScheduleSlot.WEDNESDAY_REMINDER, day_of_week=0, hour=22, minute=30
            )

    def test_accepts_boundary_2200(self):
        # Should not raise — 22:00 inclusive.
        AskRidesScheduleService._validate(
            AskRidesScheduleSlot.WEDNESDAY_REMINDER, day_of_week=0, hour=22, minute=0
        )

    def test_accepts_boundary_0600(self):
        AskRidesScheduleService._validate(
            AskRidesScheduleSlot.WEDNESDAY_REMINDER, day_of_week=0, hour=6, minute=0
        )


class TestUpdateSchedule:
    @pytest.mark.asyncio
    @patch("bot.services.ask_rides_schedule_service.publish", new_callable=AsyncMock)
    @patch("bot.services.ask_rides_schedule_service.invalidate_namespace", new_callable=AsyncMock)
    @patch("bot.services.ask_rides_schedule_service.reschedule_job")
    @patch(
        "bot.services.ask_rides_schedule_service.AskRidesScheduleRepository.upsert",
        new_callable=AsyncMock,
    )
    @patch("bot.services.ask_rides_schedule_service.AsyncSessionLocal")
    async def test_validates_then_upserts_reschedules_and_publishes(
        self, mock_session_local, mock_upsert, mock_reschedule, mock_invalidate, mock_publish
    ):
        _mock_session_local(mock_session_local)
        mock_upsert.return_value = MagicMock(day_of_week=1, hour=10, minute=0)
        mock_reschedule.return_value = True

        result, applied = await AskRidesScheduleService.update_schedule(
            AskRidesScheduleSlot.WEDNESDAY_REMINDER,
            day_of_week=1,
            hour=10,
            minute=0,
            updated_by="editor@example.com",
        )

        assert result.is_customized is True
        assert applied is True
        mock_upsert.assert_awaited_once()
        mock_reschedule.assert_called_once_with(
            "run_ask_rides_wed", day_of_week=1, hour=10, minute=0
        )
        mock_invalidate.assert_awaited_once()
        mock_publish.assert_awaited_once_with(
            {"type": "schedule_updated", "slot": "wednesday_reminder"}
        )

    @pytest.mark.asyncio
    @patch("bot.services.ask_rides_schedule_service.publish", new_callable=AsyncMock)
    async def test_raises_on_invalid_input_without_touching_db(self, mock_publish):
        with pytest.raises(ValueError):
            await AskRidesScheduleService.update_schedule(
                AskRidesScheduleSlot.FRI_SUN_GROUP,
                day_of_week=4,  # Friday not allowed
                hour=12,
                minute=0,
                updated_by="editor@example.com",
            )
        mock_publish.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("bot.services.ask_rides_schedule_service.publish", new_callable=AsyncMock)
    @patch("bot.services.ask_rides_schedule_service.invalidate_namespace", new_callable=AsyncMock)
    @patch("bot.services.ask_rides_schedule_service.reschedule_job")
    @patch(
        "bot.services.ask_rides_schedule_service.AskRidesScheduleRepository.upsert",
        new_callable=AsyncMock,
    )
    @patch("bot.services.ask_rides_schedule_service.AsyncSessionLocal")
    async def test_reschedule_failure_does_not_raise_and_is_returned(
        self, mock_session_local, mock_upsert, mock_reschedule, mock_invalidate, mock_publish
    ):
        _mock_session_local(mock_session_local)
        mock_upsert.return_value = MagicMock(day_of_week=1, hour=10, minute=0)
        mock_reschedule.return_value = False

        _, applied = await AskRidesScheduleService.update_schedule(
            AskRidesScheduleSlot.WEDNESDAY_REMINDER,
            day_of_week=1,
            hour=10,
            minute=0,
            updated_by="editor@example.com",
        )

        assert applied is False


class TestResetSchedule:
    @pytest.mark.asyncio
    @patch("bot.services.ask_rides_schedule_service.publish", new_callable=AsyncMock)
    @patch("bot.services.ask_rides_schedule_service.invalidate_namespace", new_callable=AsyncMock)
    @patch("bot.services.ask_rides_schedule_service.reschedule_job")
    @patch(
        "bot.services.ask_rides_schedule_service.AskRidesScheduleRepository.delete",
        new_callable=AsyncMock,
    )
    @patch("bot.services.ask_rides_schedule_service.AsyncSessionLocal")
    async def test_deletes_reschedules_to_default_and_publishes(
        self, mock_session_local, mock_delete, mock_reschedule, mock_invalidate, mock_publish
    ):
        _mock_session_local(mock_session_local)
        mock_reschedule.return_value = True

        result, applied = await AskRidesScheduleService.reset_schedule(
            AskRidesScheduleSlot.FRI_SUN_GROUP
        )

        default = DEFAULT_SCHEDULE[AskRidesScheduleSlot.FRI_SUN_GROUP]
        assert result.is_customized is False
        assert result.hour == default.hour
        assert applied is True
        mock_delete.assert_awaited_once()
        mock_reschedule.assert_called_once_with(
            "run_ask_rides_all",
            day_of_week=default.day_of_week,
            hour=default.hour,
            minute=default.minute,
        )
        mock_publish.assert_awaited_once_with({"type": "schedule_updated", "slot": "fri_sun_group"})


class TestGetNextScheduleOccurrence:
    """Tests for get_next_schedule_occurrence — the single source of truth for 'next run'."""

    @pytest.mark.asyncio
    @patch("bot.services.ask_rides_schedule_service.datetime")
    async def test_rolls_forward_when_today_is_configured_day_but_time_passed(self, mock_dt):
        # Wednesday April 22, 2026 at 3 PM; FRI_SUN_GROUP default is Wed noon —
        # noon has already passed, so this should roll to next Wednesday.
        mock_dt.now.return_value = _la(2026, 4, 22, 15, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        with patch.object(
            AskRidesScheduleService,
            "get_effective_schedule",
            new=AsyncMock(
                return_value=EffectiveSchedule(
                    day_of_week=2, hour=12, minute=0, is_customized=False
                )
            ),
        ):
            result = await get_next_schedule_occurrence(AskRidesScheduleSlot.FRI_SUN_GROUP)

        assert result.date().isoformat() == "2026-04-29"
        assert result.hour == 12

    @pytest.mark.asyncio
    @patch("bot.services.ask_rides_schedule_service.datetime")
    async def test_returns_today_when_time_has_not_passed(self, mock_dt):
        # Wednesday April 22, 2026 at 9 AM — noon hasn't happened yet.
        mock_dt.now.return_value = _la(2026, 4, 22, 9, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        with patch.object(
            AskRidesScheduleService,
            "get_effective_schedule",
            new=AsyncMock(
                return_value=EffectiveSchedule(
                    day_of_week=2, hour=12, minute=0, is_customized=False
                )
            ),
        ):
            result = await get_next_schedule_occurrence(AskRidesScheduleSlot.FRI_SUN_GROUP)

        assert result.date().isoformat() == "2026-04-22"
        assert result.hour == 12

    @pytest.mark.asyncio
    @patch("bot.services.ask_rides_schedule_service.datetime")
    async def test_customized_schedule_computes_from_effective_values(self, mock_dt):
        # Monday April 20, 2026 at 10 AM; a customized Tuesday 9 AM send.
        mock_dt.now.return_value = _la(2026, 4, 20, 10, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        with patch.object(
            AskRidesScheduleService,
            "get_effective_schedule",
            new=AsyncMock(
                return_value=EffectiveSchedule(day_of_week=1, hour=9, minute=0, is_customized=True)
            ),
        ):
            result = await get_next_schedule_occurrence(AskRidesScheduleSlot.FRI_SUN_GROUP)

        assert result.date().isoformat() == "2026-04-21"
        assert result.hour == 9


class TestHasSendTimePassed:
    """Tests for has_send_time_passed — the schedule-aware is_ride_cycle_active replacement."""

    @pytest.mark.asyncio
    @patch("bot.services.ask_rides_schedule_service.datetime")
    async def test_false_before_send_time_on_send_day(self, mock_dt):
        mock_dt.now.return_value = _la(2026, 4, 22, 11, 0)  # Wed 11 AM

        with patch.object(
            AskRidesScheduleService,
            "get_effective_schedule",
            new=AsyncMock(
                return_value=EffectiveSchedule(
                    day_of_week=2, hour=12, minute=0, is_customized=False
                )
            ),
        ):
            result = await has_send_time_passed(AskRidesScheduleSlot.FRI_SUN_GROUP)

        assert result is False

    @pytest.mark.asyncio
    @patch("bot.services.ask_rides_schedule_service.datetime")
    async def test_true_at_send_time(self, mock_dt):
        mock_dt.now.return_value = _la(2026, 4, 22, 12, 0)  # Wed noon

        with patch.object(
            AskRidesScheduleService,
            "get_effective_schedule",
            new=AsyncMock(
                return_value=EffectiveSchedule(
                    day_of_week=2, hour=12, minute=0, is_customized=False
                )
            ),
        ):
            result = await has_send_time_passed(AskRidesScheduleSlot.FRI_SUN_GROUP)

        assert result is True

    @pytest.mark.asyncio
    @patch("bot.services.ask_rides_schedule_service.datetime")
    async def test_true_after_send_day(self, mock_dt):
        mock_dt.now.return_value = _la(2026, 4, 24, 10, 0)  # Fri, after Wed send

        with patch.object(
            AskRidesScheduleService,
            "get_effective_schedule",
            new=AsyncMock(
                return_value=EffectiveSchedule(
                    day_of_week=2, hour=12, minute=0, is_customized=False
                )
            ),
        ):
            result = await has_send_time_passed(AskRidesScheduleSlot.FRI_SUN_GROUP)

        assert result is True

    @pytest.mark.asyncio
    @patch("bot.services.ask_rides_schedule_service.datetime")
    async def test_false_before_send_day(self, mock_dt):
        mock_dt.now.return_value = _la(2026, 4, 20, 10, 0)  # Mon, before Wed send

        with patch.object(
            AskRidesScheduleService,
            "get_effective_schedule",
            new=AsyncMock(
                return_value=EffectiveSchedule(
                    day_of_week=2, hour=12, minute=0, is_customized=False
                )
            ),
        ):
            result = await has_send_time_passed(AskRidesScheduleSlot.FRI_SUN_GROUP)

        assert result is False

    @pytest.mark.asyncio
    @patch("bot.services.ask_rides_schedule_service.datetime")
    async def test_customized_send_day_used_instead_of_default(self, mock_dt):
        # Customized send day is Monday; by Tuesday it should already be "passed"
        # even though the default FRI_SUN_GROUP send day (Wednesday) hasn't arrived.
        mock_dt.now.return_value = _la(2026, 4, 21, 10, 0)  # Tuesday

        with patch.object(
            AskRidesScheduleService,
            "get_effective_schedule",
            new=AsyncMock(
                return_value=EffectiveSchedule(day_of_week=0, hour=11, minute=0, is_customized=True)
            ),
        ):
            result = await has_send_time_passed(AskRidesScheduleSlot.FRI_SUN_GROUP)

        assert result is True


class TestGetSendDayForJob:
    """Tests for AskRidesScheduleService.get_send_day_for_job."""

    @pytest.mark.asyncio
    async def test_wednesday_job_maps_to_wednesday_reminder_slot(self):
        with patch.object(
            AskRidesScheduleService,
            "get_effective_schedule",
            new=AsyncMock(
                return_value=EffectiveSchedule(
                    day_of_week=0, hour=11, minute=0, is_customized=False
                )
            ),
        ) as mock_get:
            result = await AskRidesScheduleService.get_send_day_for_job(JobName.WEDNESDAY)

        mock_get.assert_awaited_once_with(AskRidesScheduleSlot.WEDNESDAY_REMINDER)
        assert result == 0

    @pytest.mark.asyncio
    async def test_friday_sunday_and_sunday_class_all_map_to_fri_sun_group_slot(self):
        with patch.object(
            AskRidesScheduleService,
            "get_effective_schedule",
            new=AsyncMock(
                return_value=EffectiveSchedule(
                    day_of_week=2, hour=12, minute=0, is_customized=False
                )
            ),
        ) as mock_get:
            for job_name in (JobName.FRIDAY, JobName.SUNDAY, JobName.SUNDAY_CLASS):
                result = await AskRidesScheduleService.get_send_day_for_job(job_name)
                assert result == 2

        assert mock_get.await_args_list[-1].args == (AskRidesScheduleSlot.FRI_SUN_GROUP,)
