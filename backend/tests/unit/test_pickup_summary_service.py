"""Unit tests for PickupSummaryService."""

from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest
from sqlalchemy.exc import OperationalError

from ridebot.services.pickup_summary_service import (
    EffectivePickupSummarySetting,
    PickupSummaryService,
)
from ridebot.utils.custom_exceptions import NoMatchingMessageFoundError
from ridebot.utils.pickup_summary_defaults import DEFAULT_SUMMARY_SCHEDULE
from shared.core.enums import FellowshipSeason, JobName, PickupSummarySlot


def _mock_session_local(mock_session_local):
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session_local.return_value = mock_session
    return mock_session


class TestGetEffectiveSetting:
    @pytest.mark.asyncio
    @patch(
        "ridebot.services.pickup_summary_service.PickupSummarySettingsRepository.get",
        new_callable=AsyncMock,
    )
    @patch("ridebot.services.pickup_summary_service.AsyncSessionLocal")
    async def test_returns_default_when_row_missing(self, mock_session_local, mock_get):
        _mock_session_local(mock_session_local)
        mock_get.return_value = None

        result = await PickupSummaryService.get_effective_setting(PickupSummarySlot.FRIDAY)

        default = DEFAULT_SUMMARY_SCHEDULE[PickupSummarySlot.FRIDAY]
        assert result.enabled is True
        assert result.day_of_week == default.day_of_week
        assert result.hour == default.hour
        assert result.minute == default.minute
        assert result.is_customized is False

    @pytest.mark.asyncio
    @patch(
        "ridebot.services.pickup_summary_service.PickupSummarySettingsRepository.get",
        new_callable=AsyncMock,
    )
    @patch("ridebot.services.pickup_summary_service.AsyncSessionLocal")
    async def test_returns_db_row_when_present(self, mock_session_local, mock_get):
        _mock_session_local(mock_session_local)
        fake_row = MagicMock(enabled=False, day_of_week=3, hour=14, minute=30)
        mock_get.return_value = fake_row

        result = await PickupSummaryService.get_effective_setting(PickupSummarySlot.SUNDAY)

        assert result == EffectivePickupSummarySetting(
            enabled=False, day_of_week=3, hour=14, minute=30, is_customized=True
        )

    @pytest.mark.asyncio
    @patch("ridebot.services.pickup_summary_service.AsyncSessionLocal")
    async def test_falls_back_to_default_on_operational_error(self, mock_session_local):
        mock_session_local.side_effect = OperationalError("stmt", {}, Exception("no such table"))

        result = await PickupSummaryService.get_effective_setting(PickupSummarySlot.FRIDAY)

        default = DEFAULT_SUMMARY_SCHEDULE[PickupSummarySlot.FRIDAY]
        assert result.hour == default.hour
        assert result.enabled is True
        assert result.is_customized is False

    @pytest.mark.asyncio
    @patch("ridebot.services.pickup_summary_service.AsyncSessionLocal")
    async def test_never_raises_on_unexpected_error(self, mock_session_local):
        mock_session_local.side_effect = RuntimeError("boom")

        result = await PickupSummaryService.get_effective_setting(PickupSummarySlot.SUNDAY)

        default = DEFAULT_SUMMARY_SCHEDULE[PickupSummarySlot.SUNDAY]
        assert result.hour == default.hour
        assert result.is_customized is False


class TestGetEffectiveSettings:
    @pytest.mark.asyncio
    @patch(
        "ridebot.services.pickup_summary_service.PickupSummarySettingsRepository.get_all",
        new_callable=AsyncMock,
    )
    @patch("ridebot.services.pickup_summary_service.AsyncSessionLocal")
    async def test_merges_db_rows_over_defaults(self, mock_session_local, mock_get_all):
        _mock_session_local(mock_session_local)
        fake_row = MagicMock(
            slot=PickupSummarySlot.SUNDAY.value, enabled=False, day_of_week=1, hour=13, minute=15
        )
        mock_get_all.return_value = [fake_row]

        result = await PickupSummaryService.get_effective_settings()

        assert result[PickupSummarySlot.SUNDAY].hour == 13
        assert result[PickupSummarySlot.SUNDAY].enabled is False
        assert result[PickupSummarySlot.SUNDAY].is_customized is True
        assert result[PickupSummarySlot.FRIDAY].is_customized is False

    @pytest.mark.asyncio
    @patch("ridebot.services.pickup_summary_service.AsyncSessionLocal")
    async def test_falls_back_to_all_defaults_on_db_error(self, mock_session_local):
        mock_session_local.side_effect = OperationalError("stmt", {}, Exception("no such table"))

        result = await PickupSummaryService.get_effective_settings()

        assert len(result) == len(DEFAULT_SUMMARY_SCHEDULE)
        assert all(not s.is_customized for s in result.values())
        assert all(s.enabled for s in result.values())


class TestValidate:
    def test_rejects_day_outside_allowed_set(self):
        with pytest.raises(ValueError, match="day_of_week must be one of"):
            PickupSummaryService._validate(
                PickupSummarySlot.FRIDAY, day_of_week=5, hour=11, minute=0
            )  # Saturday not allowed for FRIDAY slot

    def test_rejects_sunday_for_sunday_slot(self):
        with pytest.raises(ValueError, match="day_of_week must be one of"):
            PickupSummaryService._validate(
                PickupSummarySlot.SUNDAY, day_of_week=6, hour=11, minute=0
            )

    def test_rejects_out_of_range_hour(self):
        with pytest.raises(ValueError, match="hour must be between"):
            PickupSummaryService._validate(
                PickupSummarySlot.FRIDAY, day_of_week=0, hour=24, minute=0
            )

    def test_rejects_out_of_range_minute(self):
        with pytest.raises(ValueError, match="minute must be between"):
            PickupSummaryService._validate(
                PickupSummarySlot.FRIDAY, day_of_week=0, hour=11, minute=60
            )

    def test_rejects_time_before_window(self):
        with pytest.raises(ValueError, match="time must be between"):
            PickupSummaryService._validate(
                PickupSummarySlot.FRIDAY, day_of_week=0, hour=3, minute=0
            )

    def test_rejects_time_after_window(self):
        with pytest.raises(ValueError, match="time must be between"):
            PickupSummaryService._validate(
                PickupSummarySlot.FRIDAY, day_of_week=0, hour=22, minute=30
            )

    def test_accepts_boundary_2200(self):
        PickupSummaryService._validate(PickupSummarySlot.FRIDAY, day_of_week=0, hour=22, minute=0)

    def test_accepts_boundary_0600(self):
        PickupSummaryService._validate(PickupSummarySlot.FRIDAY, day_of_week=0, hour=6, minute=0)


class TestUpdateSetting:
    @pytest.mark.asyncio
    @patch("ridebot.services.pickup_summary_service.reschedule_job")
    @patch(
        "ridebot.services.pickup_summary_service.PickupSummarySettingsRepository.upsert",
        new_callable=AsyncMock,
    )
    @patch("ridebot.services.pickup_summary_service.AsyncSessionLocal")
    async def test_validates_then_upserts_and_reschedules(
        self, mock_session_local, mock_upsert, mock_reschedule
    ):
        _mock_session_local(mock_session_local)
        mock_upsert.return_value = MagicMock(enabled=True, day_of_week=1, hour=10, minute=0)
        mock_reschedule.return_value = True

        result, applied = await PickupSummaryService.update_setting(
            PickupSummarySlot.FRIDAY,
            enabled=True,
            day_of_week=1,
            hour=10,
            minute=0,
            updated_by="editor@example.com",
        )

        assert result.is_customized is True
        assert applied is True
        mock_upsert.assert_awaited_once()
        mock_reschedule.assert_called_once_with(
            "run_friday_pickups_summary", day_of_week=1, hour=10, minute=0
        )

    @pytest.mark.asyncio
    async def test_raises_on_invalid_input_without_touching_db(self):
        with pytest.raises(ValueError):
            await PickupSummaryService.update_setting(
                PickupSummarySlot.FRIDAY,
                enabled=True,
                day_of_week=5,  # Saturday not allowed
                hour=12,
                minute=0,
                updated_by="editor@example.com",
            )

    @pytest.mark.asyncio
    @patch("ridebot.services.pickup_summary_service.reschedule_job")
    @patch(
        "ridebot.services.pickup_summary_service.PickupSummarySettingsRepository.upsert",
        new_callable=AsyncMock,
    )
    @patch("ridebot.services.pickup_summary_service.AsyncSessionLocal")
    async def test_reschedule_failure_does_not_raise_and_is_returned(
        self, mock_session_local, mock_upsert, mock_reschedule
    ):
        _mock_session_local(mock_session_local)
        mock_upsert.return_value = MagicMock(enabled=True, day_of_week=1, hour=10, minute=0)
        mock_reschedule.return_value = False

        _, applied = await PickupSummaryService.update_setting(
            PickupSummarySlot.FRIDAY,
            enabled=True,
            day_of_week=1,
            hour=10,
            minute=0,
            updated_by="editor@example.com",
        )

        assert applied is False


class TestResetSetting:
    @pytest.mark.asyncio
    @patch("ridebot.services.pickup_summary_service.reschedule_job")
    @patch(
        "ridebot.services.pickup_summary_service.PickupSummarySettingsRepository.delete",
        new_callable=AsyncMock,
    )
    @patch("ridebot.services.pickup_summary_service.AsyncSessionLocal")
    async def test_deletes_and_reschedules_to_default(
        self, mock_session_local, mock_delete, mock_reschedule
    ):
        _mock_session_local(mock_session_local)
        mock_reschedule.return_value = True

        result, applied = await PickupSummaryService.reset_setting(PickupSummarySlot.SUNDAY)

        default = DEFAULT_SUMMARY_SCHEDULE[PickupSummarySlot.SUNDAY]
        assert result.is_customized is False
        assert result.enabled is True
        assert result.hour == default.hour
        assert applied is True
        mock_delete.assert_awaited_once()
        mock_reschedule.assert_called_once_with(
            "run_sunday_pickups_summary",
            day_of_week=default.day_of_week,
            hour=default.hour,
            minute=default.minute,
        )


class TestBuildDashboardLink:
    def test_returns_none_when_unset_outside_local(self, monkeypatch):
        monkeypatch.delenv("FRONTEND_BASE_URL", raising=False)
        monkeypatch.setenv("APP_ENV", "prod")

        assert PickupSummaryService.build_dashboard_link(PickupSummarySlot.FRIDAY) is None

    def test_uses_local_default_when_unset_locally(self, monkeypatch):
        monkeypatch.delenv("FRONTEND_BASE_URL", raising=False)
        monkeypatch.setenv("APP_ENV", "local")

        result = PickupSummaryService.build_dashboard_link(PickupSummarySlot.FRIDAY)

        assert result == "http://localhost:5173/?overview=friday#reactions"

    def test_uses_env_var_and_strips_trailing_slash(self, monkeypatch):
        monkeypatch.setenv("FRONTEND_BASE_URL", "https://example.com/")

        result = PickupSummaryService.build_dashboard_link(PickupSummarySlot.SUNDAY)

        assert result == "https://example.com/?overview=sunday#reactions"


def _make_channel():
    channel = MagicMock(spec=discord.TextChannel)
    channel.send = AsyncMock()
    return channel


class TestSendSummary:
    @pytest.mark.asyncio
    @patch.object(
        PickupSummaryService,
        "get_effective_setting",
        new=AsyncMock(
            return_value=EffectivePickupSummarySetting(
                enabled=False, day_of_week=4, hour=11, minute=0, is_customized=False
            )
        ),
    )
    async def test_skips_when_toggle_off(self):
        service = PickupSummaryService(MagicMock())

        result = await service.send_summary(PickupSummarySlot.FRIDAY)

        assert result is False

    @pytest.mark.asyncio
    @patch.object(
        PickupSummaryService,
        "get_effective_setting",
        new=AsyncMock(
            return_value=EffectivePickupSummarySetting(
                enabled=True, day_of_week=4, hour=11, minute=0, is_customized=False
            )
        ),
    )
    @patch("ridebot.services.pickup_summary_service.FellowshipSeasonService.get_season")
    async def test_skips_friday_when_season_is_not_friday(self, mock_get_season):
        mock_get_season.return_value = FellowshipSeason.WEDNESDAY
        service = PickupSummaryService(MagicMock())

        result = await service.send_summary(PickupSummarySlot.FRIDAY)

        assert result is False

    @pytest.mark.asyncio
    @patch("ridebot.services.pickup_summary_service.MessageScheduleRepository.is_job_paused")
    @patch("ridebot.services.pickup_summary_service.AskRidesScheduleService.get_send_day_for_job")
    @patch("ridebot.services.pickup_summary_service.AsyncSessionLocal")
    async def test_skips_when_ask_rides_job_paused(
        self, mock_session_local, mock_get_send_day, mock_is_paused
    ):
        _mock_session_local(mock_session_local)
        mock_get_send_day.return_value = 5
        mock_is_paused.return_value = True
        service = PickupSummaryService(MagicMock())

        result = await service.send_summary(PickupSummarySlot.SUNDAY, respect_toggle=False)

        assert result is False

    @pytest.mark.asyncio
    @patch("ridebot.services.pickup_summary_service.invalidate_namespace", new_callable=AsyncMock)
    @patch("ridebot.services.pickup_summary_service.LocationsService")
    @patch("ridebot.services.pickup_summary_service.MessageScheduleRepository.is_job_paused")
    @patch("ridebot.services.pickup_summary_service.AskRidesScheduleService.get_send_day_for_job")
    @patch("ridebot.services.pickup_summary_service.AsyncSessionLocal")
    async def test_skips_when_no_matching_message_found(
        self,
        mock_session_local,
        mock_get_send_day,
        mock_is_paused,
        mock_locations_cls,
        mock_invalidate,
    ):
        _mock_session_local(mock_session_local)
        mock_get_send_day.return_value = 5
        mock_is_paused.return_value = False
        mock_locations = MagicMock()
        mock_locations.build_pickups_embeds = AsyncMock(side_effect=NoMatchingMessageFoundError())
        mock_locations_cls.return_value = mock_locations

        bot = MagicMock()
        service = PickupSummaryService(bot)

        result = await service.send_summary(PickupSummarySlot.SUNDAY, respect_toggle=False)

        assert result is False

    @pytest.mark.asyncio
    @patch("ridebot.services.pickup_summary_service.invalidate_namespace", new_callable=AsyncMock)
    @patch("ridebot.services.pickup_summary_service.LocationsService")
    @patch("ridebot.services.pickup_summary_service.MessageScheduleRepository.is_job_paused")
    @patch("ridebot.services.pickup_summary_service.AskRidesScheduleService.get_send_day_for_job")
    @patch("ridebot.services.pickup_summary_service.AsyncSessionLocal")
    async def test_happy_path_sends_embeds_with_link(
        self,
        mock_session_local,
        mock_get_send_day,
        mock_is_paused,
        mock_locations_cls,
        mock_invalidate,
        monkeypatch,
    ):
        monkeypatch.setenv("FRONTEND_BASE_URL", "https://example.com")
        _mock_session_local(mock_session_local)
        mock_get_send_day.return_value = 5
        mock_is_paused.return_value = False
        fake_embeds = [MagicMock(spec=discord.Embed)]
        mock_locations = MagicMock()
        mock_locations.build_pickups_embeds = AsyncMock(return_value=fake_embeds)
        mock_locations_cls.return_value = mock_locations

        channel = _make_channel()
        bot = MagicMock()
        bot.get_channel.return_value = channel
        service = PickupSummaryService(bot)

        result = await service.send_summary(PickupSummarySlot.SUNDAY, respect_toggle=False)

        assert result is True
        mock_invalidate.assert_awaited_once()
        channel.send.assert_awaited_once_with(
            content="[Open in dashboard](<https://example.com/?overview=sunday#reactions>)",
            embeds=fake_embeds,
        )

    @pytest.mark.asyncio
    @patch("ridebot.services.pickup_summary_service.invalidate_namespace", new_callable=AsyncMock)
    @patch("ridebot.services.pickup_summary_service.LocationsService")
    @patch("ridebot.services.pickup_summary_service.MessageScheduleRepository.is_job_paused")
    @patch("ridebot.services.pickup_summary_service.AskRidesScheduleService.get_send_day_for_job")
    @patch("ridebot.services.pickup_summary_service.AsyncSessionLocal")
    async def test_omits_link_when_base_url_unset(
        self,
        mock_session_local,
        mock_get_send_day,
        mock_is_paused,
        mock_locations_cls,
        mock_invalidate,
        monkeypatch,
    ):
        monkeypatch.delenv("FRONTEND_BASE_URL", raising=False)
        monkeypatch.setenv("APP_ENV", "prod")
        _mock_session_local(mock_session_local)
        mock_get_send_day.return_value = 5
        mock_is_paused.return_value = False
        fake_embeds = [MagicMock(spec=discord.Embed)]
        mock_locations = MagicMock()
        mock_locations.build_pickups_embeds = AsyncMock(return_value=fake_embeds)
        mock_locations_cls.return_value = mock_locations

        channel = _make_channel()
        bot = MagicMock()
        bot.get_channel.return_value = channel
        service = PickupSummaryService(bot)

        result = await service.send_summary(PickupSummarySlot.SUNDAY, respect_toggle=False)

        assert result is True
        channel.send.assert_awaited_once_with(content=None, embeds=fake_embeds)

    @pytest.mark.asyncio
    async def test_no_bot_returns_false(self):
        service = PickupSummaryService(None)

        with (
            patch(
                "ridebot.services.pickup_summary_service.MessageScheduleRepository.is_job_paused",
                new=AsyncMock(return_value=False),
            ),
            patch(
                "ridebot.services.pickup_summary_service.AskRidesScheduleService.get_send_day_for_job",
                new=AsyncMock(return_value=JobName.SUNDAY),
            ),
            patch("ridebot.services.pickup_summary_service.AsyncSessionLocal"),
        ):
            result = await service.send_summary(PickupSummarySlot.SUNDAY, respect_toggle=False)

        assert result is False

    @pytest.mark.asyncio
    @patch("ridebot.services.pickup_summary_service.send_error_to_discord", new_callable=AsyncMock)
    @patch("ridebot.services.pickup_summary_service.AsyncSessionLocal")
    async def test_unexpected_error_is_caught_and_reported(
        self, mock_session_local, mock_send_error
    ):
        mock_session_local.side_effect = RuntimeError("boom")
        service = PickupSummaryService(MagicMock())

        result = await service.send_summary(PickupSummarySlot.SUNDAY, respect_toggle=False)

        assert result is False
        mock_send_error.assert_awaited_once()
