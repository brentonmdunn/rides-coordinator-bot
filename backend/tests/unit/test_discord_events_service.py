"""Unit tests for DiscordEventsService."""

import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from shared.utils.constants import LA_TZ
from stonesbot.services.discord_events_service import (
    WORSHIP_SERVICE_LOCATION,
    WORSHIP_SERVICE_SUMMARY,
    DiscordEventsService,
    ScheduledEventSpec,
)

SERVICE_DATE = datetime.date(2026, 9, 27)
BEFORE = LA_TZ.localize(datetime.datetime(2026, 9, 20, 18, 0))
AFTER = LA_TZ.localize(datetime.datetime(2026, 10, 1, 9, 0))


def _expected_start(day: datetime.date = SERVICE_DATE) -> datetime.datetime:
    return LA_TZ.localize(datetime.datetime.combine(day, datetime.time(10, 30)))


def _expected_end(day: datetime.date = SERVICE_DATE) -> datetime.datetime:
    return LA_TZ.localize(datetime.datetime.combine(day, datetime.time(12, 0)))


# ---------------------------------------------------------------------------
# build_specs
# ---------------------------------------------------------------------------


def test_build_specs_uses_fixed_time_and_location():
    """A worship service becomes a 10:30a-12p event at the school, on its calendar date."""
    specs = DiscordEventsService.build_specs({SERVICE_DATE: [WORSHIP_SERVICE_SUMMARY]})

    assert specs == [
        ScheduledEventSpec(
            name=WORSHIP_SERVICE_SUMMARY,
            start=_expected_start(),
            end=_expected_end(),
            location=WORSHIP_SERVICE_LOCATION,
        )
    ]


def test_build_specs_puts_extras_in_the_description():
    """A day's other calendar entries become the event's description."""
    specs = DiscordEventsService.build_specs(
        {SERVICE_DATE: [WORSHIP_SERVICE_SUMMARY]},
        {SERVICE_DATE: ["Child Dedication", "Potluck"]},
    )

    assert specs[0].description == "Also today: Child Dedication, Potluck"


def test_build_specs_without_extras_has_no_description():
    """A plain service day gets no description rather than an empty one."""
    specs = DiscordEventsService.build_specs(
        {SERVICE_DATE: [WORSHIP_SERVICE_SUMMARY]}, {SERVICE_DATE: []}
    )

    assert specs[0].description is None


def test_build_specs_ignores_extras_without_a_recognized_event():
    """Extras on a day with no worship service produce no event of their own."""
    specs = DiscordEventsService.build_specs(
        {SERVICE_DATE: []}, {SERVICE_DATE: ["Child Dedication"]}
    )

    assert specs == []


def test_build_specs_ignores_other_events():
    """Events that are not worship services produce no Discord event."""
    specs = DiscordEventsService.build_specs(
        {SERVICE_DATE: ["Wildcard Sunday brunch", "Prayer Night", "Potluck"]}
    )
    assert specs == []


def test_build_specs_matches_case_insensitively():
    """Summary matching tolerates casing and stray whitespace from the feed."""
    specs = DiscordEventsService.build_specs({SERVICE_DATE: ["  regular WORSHIP service "]})
    assert len(specs) == 1
    assert specs[0].name == WORSHIP_SERVICE_SUMMARY


def test_build_specs_collapses_duplicates_on_same_day():
    """A feed that lists the service twice on one day yields one event."""
    specs = DiscordEventsService.build_specs(
        {SERVICE_DATE: [WORSHIP_SERVICE_SUMMARY, WORSHIP_SERVICE_SUMMARY]}
    )
    assert len(specs) == 1


def test_build_specs_returns_multiple_days_sorted():
    """Several service dates produce one spec each, in chronological order."""
    earlier = datetime.date(2026, 9, 20)
    specs = DiscordEventsService.build_specs(
        {SERVICE_DATE: [WORSHIP_SERVICE_SUMMARY], earlier: [WORSHIP_SERVICE_SUMMARY]}
    )
    assert [s.start for s in specs] == [_expected_start(earlier), _expected_start()]


# ---------------------------------------------------------------------------
# create_events
# ---------------------------------------------------------------------------


def _make_guild(existing=()) -> MagicMock:
    guild = MagicMock(spec=discord.Guild)
    guild.id = 42
    guild.scheduled_events = list(existing)
    guild.create_scheduled_event = AsyncMock(return_value=MagicMock())
    return guild


@pytest.mark.asyncio
async def test_create_events_passes_external_event_details():
    """Creates an external event with the pinned location, time window, and privacy level."""
    guild = _make_guild()

    created = await DiscordEventsService.create_events(
        guild, {SERVICE_DATE: [WORSHIP_SERVICE_SUMMARY]}, now=BEFORE
    )

    assert len(created) == 1
    kwargs = guild.create_scheduled_event.await_args.kwargs
    assert kwargs["name"] == WORSHIP_SERVICE_SUMMARY
    assert kwargs["start_time"] == _expected_start()
    assert kwargs["end_time"] == _expected_end()
    assert kwargs["location"] == WORSHIP_SERVICE_LOCATION
    assert kwargs["entity_type"] == discord.EntityType.external
    assert kwargs["privacy_level"] == discord.PrivacyLevel.guild_only


@pytest.mark.asyncio
async def test_create_events_passes_extras_as_description():
    """The day's other entries reach Discord as the event description."""
    guild = _make_guild()

    await DiscordEventsService.create_events(
        guild,
        {SERVICE_DATE: [WORSHIP_SERVICE_SUMMARY]},
        {SERVICE_DATE: ["Child Dedication"]},
        now=BEFORE,
    )

    kwargs = guild.create_scheduled_event.await_args.kwargs
    assert kwargs["description"] == "Also today: Child Dedication"


@pytest.mark.asyncio
async def test_create_events_omits_description_without_extras():
    """No extras means no description field is sent at all."""
    guild = _make_guild()

    await DiscordEventsService.create_events(
        guild, {SERVICE_DATE: [WORSHIP_SERVICE_SUMMARY]}, now=BEFORE
    )

    kwargs = guild.create_scheduled_event.await_args.kwargs
    assert kwargs["description"] is discord.utils.MISSING


@pytest.mark.asyncio
async def test_create_events_leaves_existing_event_description_alone():
    """An already-created event is not edited, even when extras were added since."""
    existing = MagicMock()
    existing.name = WORSHIP_SERVICE_SUMMARY
    existing.start_time = _expected_start()
    existing.edit = AsyncMock()
    guild = _make_guild([existing])

    created = await DiscordEventsService.create_events(
        guild,
        {SERVICE_DATE: [WORSHIP_SERVICE_SUMMARY]},
        {SERVICE_DATE: ["Child Dedication"]},
        now=BEFORE,
    )

    assert created == []
    existing.edit.assert_not_awaited()
    guild.create_scheduled_event.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_events_skips_past_start_times():
    """Discord rejects events in the past, so those are skipped before the API call."""
    guild = _make_guild()

    created = await DiscordEventsService.create_events(
        guild, {SERVICE_DATE: [WORSHIP_SERVICE_SUMMARY]}, now=AFTER
    )

    assert created == []
    guild.create_scheduled_event.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_events_skips_existing_duplicate():
    """An event with the same name and start time is not created twice."""
    existing = MagicMock()
    existing.name = WORSHIP_SERVICE_SUMMARY
    existing.start_time = _expected_start()
    guild = _make_guild([existing])

    created = await DiscordEventsService.create_events(
        guild, {SERVICE_DATE: [WORSHIP_SERVICE_SUMMARY]}, now=BEFORE
    )

    assert created == []
    guild.create_scheduled_event.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_events_creates_when_existing_is_a_different_time():
    """A same-named event at another time does not block this week's event."""
    existing = MagicMock()
    existing.name = WORSHIP_SERVICE_SUMMARY
    existing.start_time = _expected_start(datetime.date(2026, 9, 20))
    guild = _make_guild([existing])

    created = await DiscordEventsService.create_events(
        guild, {SERVICE_DATE: [WORSHIP_SERVICE_SUMMARY]}, now=BEFORE
    )

    assert len(created) == 1


@pytest.mark.asyncio
async def test_create_events_survives_missing_permission():
    """A Forbidden response is logged, not raised."""
    guild = _make_guild()
    guild.create_scheduled_event.side_effect = discord.Forbidden(MagicMock(status=403), "nope")

    created = await DiscordEventsService.create_events(
        guild, {SERVICE_DATE: [WORSHIP_SERVICE_SUMMARY]}, now=BEFORE
    )

    assert created == []


@pytest.mark.asyncio
async def test_create_events_continues_after_one_failure():
    """One failed creation does not stop later events in the same run."""
    earlier = datetime.date(2026, 9, 20)
    guild = _make_guild()
    guild.create_scheduled_event.side_effect = [
        discord.HTTPException(MagicMock(status=500), "boom"),
        MagicMock(),
    ]

    created = await DiscordEventsService.create_events(
        guild,
        {earlier: [WORSHIP_SERVICE_SUMMARY], SERVICE_DATE: [WORSHIP_SERVICE_SUMMARY]},
        now=LA_TZ.localize(datetime.datetime(2026, 9, 19, 12, 0)),
    )

    assert len(created) == 1
    assert guild.create_scheduled_event.await_count == 2


@pytest.mark.asyncio
async def test_create_events_defaults_now_to_la_time():
    """Omitting `now` falls back to the current LA time rather than naive local time."""
    guild = _make_guild()
    fixed = LA_TZ.localize(datetime.datetime(2026, 9, 20, 12, 0))

    with patch("stonesbot.services.discord_events_service.datetime") as mock_dt:
        mock_dt.datetime.now.return_value = fixed
        mock_dt.datetime.combine = datetime.datetime.combine
        mock_dt.time = datetime.time
        await DiscordEventsService.create_events(guild, {SERVICE_DATE: [WORSHIP_SERVICE_SUMMARY]})

    mock_dt.datetime.now.assert_called_once_with(tz=LA_TZ)
    guild.create_scheduled_event.assert_awaited_once()
