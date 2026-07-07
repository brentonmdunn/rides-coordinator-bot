"""Unit tests for bot.services.late_reaction_windows_service."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from bot.core.enums import DaysOfWeek
from bot.services.late_reaction_windows_service import (
    DEFAULT_LATE_REACTION_WINDOWS,
    LateReactionWindowsService,
)

VALID_PAYLOAD = {
    "wednesday": {
        "start_day": "Tuesday",
        "start_time": "19:00",
        "end_day": "Wednesday",
        "end_time": "19:00",
    },
    "friday": {
        "start_day": "Thursday",
        "start_time": "19:00",
        "end_day": "Friday",
        "end_time": "19:00",
    },
    "sunday": {
        "start_day": "Saturday",
        "start_time": "10:00",
        "end_day": "Sunday",
        "end_time": "10:00",
    },
}


@pytest.fixture(autouse=True)
def _reset_cache():
    """Ensure the class-level cache doesn't leak between tests."""
    LateReactionWindowsService.invalidate_cache()
    yield
    LateReactionWindowsService.invalidate_cache()


def _mock_session_local(mock_session_local):
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session_local.return_value = mock_session
    return mock_session


@pytest.mark.asyncio
@patch(
    "bot.services.late_reaction_windows_service.GlobalSettingsRepository.get",
    new_callable=AsyncMock,
)
@patch("bot.services.late_reaction_windows_service.AsyncSessionLocal")
async def test_get_windows_missing_key_returns_defaults(mock_session_local, mock_get):
    _mock_session_local(mock_session_local)
    mock_get.return_value = None

    windows = await LateReactionWindowsService.get_windows()

    assert windows == DEFAULT_LATE_REACTION_WINDOWS


@pytest.mark.asyncio
@patch(
    "bot.services.late_reaction_windows_service.GlobalSettingsRepository.get",
    new_callable=AsyncMock,
)
@patch("bot.services.late_reaction_windows_service.AsyncSessionLocal")
async def test_get_windows_malformed_json_returns_defaults(mock_session_local, mock_get):
    _mock_session_local(mock_session_local)
    mock_get.return_value = "not valid json{{{"

    windows = await LateReactionWindowsService.get_windows()

    assert windows == DEFAULT_LATE_REACTION_WINDOWS


@pytest.mark.asyncio
@patch(
    "bot.services.late_reaction_windows_service.GlobalSettingsRepository.get",
    new_callable=AsyncMock,
)
@patch("bot.services.late_reaction_windows_service.AsyncSessionLocal")
async def test_get_windows_one_bad_day_falls_back_only_for_that_day(mock_session_local, mock_get):
    _mock_session_local(mock_session_local)
    bad_payload = json.loads(json.dumps(VALID_PAYLOAD))
    bad_payload["friday"]["start_time"] = "not-a-time"
    mock_get.return_value = json.dumps(bad_payload)

    windows = await LateReactionWindowsService.get_windows()

    assert windows[DaysOfWeek.FRIDAY] == DEFAULT_LATE_REACTION_WINDOWS[DaysOfWeek.FRIDAY]
    assert windows[DaysOfWeek.WEDNESDAY].start_day == DaysOfWeek.TUESDAY
    assert windows[DaysOfWeek.WEDNESDAY].start_hour == 19
    assert windows[DaysOfWeek.SUNDAY].start_hour == 10


@pytest.mark.asyncio
@patch(
    "bot.services.late_reaction_windows_service.GlobalSettingsRepository.get",
    new_callable=AsyncMock,
)
@patch("bot.services.late_reaction_windows_service.AsyncSessionLocal")
async def test_get_windows_round_trip_custom_values(mock_session_local, mock_get):
    _mock_session_local(mock_session_local)
    custom = json.loads(json.dumps(VALID_PAYLOAD))
    custom["sunday"]["start_time"] = "09:30"
    mock_get.return_value = json.dumps(custom)

    windows = await LateReactionWindowsService.get_windows()

    assert windows[DaysOfWeek.SUNDAY].start_hour == 9
    assert windows[DaysOfWeek.SUNDAY].start_minute == 30


@pytest.mark.asyncio
@patch(
    "bot.services.late_reaction_windows_service.GlobalSettingsRepository.set",
    new_callable=AsyncMock,
)
@patch("bot.services.late_reaction_windows_service.AsyncSessionLocal")
async def test_set_windows_persists_json(mock_session_local, mock_set):
    _mock_session_local(mock_session_local)

    await LateReactionWindowsService.set_windows(VALID_PAYLOAD)

    mock_set.assert_awaited_once()
    args, _kwargs = mock_set.call_args
    assert args[1] == "late_reaction_windows"
    assert json.loads(args[2]) == VALID_PAYLOAD


@pytest.mark.asyncio
@patch(
    "bot.services.late_reaction_windows_service.GlobalSettingsRepository.set",
    new_callable=AsyncMock,
)
@patch("bot.services.late_reaction_windows_service.AsyncSessionLocal")
async def test_set_windows_invalidates_cache(mock_session_local, mock_set):
    _mock_session_local(mock_session_local)
    # Prime the cache.
    LateReactionWindowsService._cache = DEFAULT_LATE_REACTION_WINDOWS
    LateReactionWindowsService._fetched_at = __import__("time").monotonic()

    await LateReactionWindowsService.set_windows(VALID_PAYLOAD)

    assert LateReactionWindowsService._cache is None


@pytest.mark.asyncio
async def test_set_windows_rejects_bad_day_name():
    bad_payload = json.loads(json.dumps(VALID_PAYLOAD))
    bad_payload["wednesday"]["start_day"] = "Notaday"

    with pytest.raises(ValueError, match="Invalid day"):
        await LateReactionWindowsService.set_windows(bad_payload)


@pytest.mark.asyncio
async def test_set_windows_rejects_bad_time_format():
    bad_payload = json.loads(json.dumps(VALID_PAYLOAD))
    bad_payload["friday"]["start_time"] = "25:99"

    with pytest.raises(ValueError, match="Invalid time"):
        await LateReactionWindowsService.set_windows(bad_payload)


@pytest.mark.asyncio
async def test_set_windows_rejects_same_day_inverted_window():
    bad_payload = json.loads(json.dumps(VALID_PAYLOAD))
    bad_payload["sunday"]["start_day"] = "Sunday"
    bad_payload["sunday"]["start_time"] = "12:00"
    bad_payload["sunday"]["end_day"] = "Sunday"
    bad_payload["sunday"]["end_time"] = "10:00"

    with pytest.raises(ValueError, match="Invalid window"):
        await LateReactionWindowsService.set_windows(bad_payload)


@pytest.mark.asyncio
async def test_set_windows_rejects_missing_day_key():
    bad_payload = json.loads(json.dumps(VALID_PAYLOAD))
    del bad_payload["sunday"]

    with pytest.raises(ValueError, match="sunday"):
        await LateReactionWindowsService.set_windows(bad_payload)
