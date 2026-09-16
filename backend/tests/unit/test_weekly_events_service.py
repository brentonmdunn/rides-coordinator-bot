"""Unit tests for WeeklyEventsService."""

import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from stonesbot.services.weekly_events_service import NO_EVENTS_TEXT, WeeklyEventsService

MODULE = "stonesbot.services.weekly_events_service"

# Sunday, Sep 20 2026 -> announces Mon Sep 21 through Sun Sep 27.
SUNDAY = datetime.date(2026, 9, 20)
WEEK_START = datetime.date(2026, 9, 21)
WEEK_END = datetime.date(2026, 9, 27)


# ---------------------------------------------------------------------------
# get_announcement_week
# ---------------------------------------------------------------------------


def test_get_announcement_week_from_sunday_starts_tomorrow():
    """Run on Sunday, the week is tomorrow (Monday) through the following Sunday."""
    assert WeeklyEventsService.get_announcement_week(SUNDAY) == (WEEK_START, WEEK_END)


def test_get_announcement_week_from_monday_skips_current_week():
    """Run on a Monday, the announced week is the *next* Monday, not today."""
    start, end = WeeklyEventsService.get_announcement_week(datetime.date(2026, 9, 21))
    assert start == datetime.date(2026, 9, 28)
    assert end == datetime.date(2026, 10, 4)


def test_get_announcement_week_is_always_seven_days():
    """Every start date produces an inclusive 7-day Monday-to-Sunday span."""
    for offset in range(14):
        day = SUNDAY + datetime.timedelta(days=offset)
        start, end = WeeklyEventsService.get_announcement_week(day)
        assert start.weekday() == 0
        assert end.weekday() == 6
        assert (end - start).days == 6
        assert start > day


# ---------------------------------------------------------------------------
# build_embed
# ---------------------------------------------------------------------------


def test_build_embed_groups_events_by_day():
    """Should add one field per day of the week, with bulleted summaries."""
    summaries = {WEEK_START: ["Prayer Night"], WEEK_END: ["Sunday Service", "Potluck"]}
    embed = WeeklyEventsService.build_embed(WEEK_START, WEEK_END, summaries)

    assert len(embed.fields) == 7
    assert embed.description is None
    assert embed.fields[0].value == "• Prayer Night"
    assert embed.fields[6].value == "• Sunday Service\n• Potluck"
    assert "Monday" in str(embed.fields[0].name)


def test_build_embed_with_no_events_says_so():
    """An empty week posts a single embed stating there is nothing scheduled."""
    summaries = {WEEK_START + datetime.timedelta(days=i): [] for i in range(7)}
    embed = WeeklyEventsService.build_embed(WEEK_START, WEEK_END, summaries)

    assert embed.description == NO_EVENTS_TEXT
    assert len(embed.fields) == 0


def test_build_embed_truncates_overlong_day():
    """A day with more text than Discord allows is truncated, not rejected."""
    summaries = {WEEK_START: [f"Event {i} " + "x" * 50 for i in range(40)]}
    embed = WeeklyEventsService.build_embed(WEEK_START, WEEK_END, summaries)

    assert len(str(embed.fields[0].value)) <= 1024
    assert str(embed.fields[0].value).endswith("…")


# ---------------------------------------------------------------------------
# post_weekly_announcement
# ---------------------------------------------------------------------------


def _make_channel(channel_id: int = 999) -> MagicMock:
    channel = MagicMock(spec=discord.TextChannel)
    channel.id = channel_id
    channel.send = AsyncMock()
    channel.fetch_message = AsyncMock()
    return channel


def _make_bot(channel) -> MagicMock:
    bot = MagicMock()
    bot.get_channel.return_value = channel
    return bot


def _patch_session():
    """Patch AsyncSessionLocal with a no-op async context manager."""
    session = MagicMock()
    session.commit = AsyncMock()
    session.expunge_all = MagicMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return patch(f"{MODULE}.AsyncSessionLocal", return_value=ctx), session


@pytest.mark.asyncio
async def test_post_weekly_announcement_sends_and_records():
    """Posts the embed, then records the new message id."""
    channel = _make_channel()
    sent = MagicMock()
    sent.id = 12345
    channel.send.return_value = sent
    bot = _make_bot(channel)

    session_patch, _session = _patch_session()

    with (
        session_patch,
        patch(f"{MODULE}.resolve_channel_id", side_effect=lambda cid: int(cid)),
        patch(
            f"{MODULE}.CalendarRepository.get_event_summaries_by_date",
            AsyncMock(return_value={WEEK_START: ["Prayer Night"]}),
        ),
        patch(f"{MODULE}.WeeklyEventsAnnouncementRepository.get_all", AsyncMock(return_value=[])),
        patch(f"{MODULE}.WeeklyEventsAnnouncementRepository.create", AsyncMock()) as mock_create,
    ):
        result = await WeeklyEventsService.post_weekly_announcement(bot, 999, today=SUNDAY)

    assert result is sent
    channel.send.assert_awaited_once()
    assert channel.send.await_args.kwargs["embed"].title.startswith("Events for")
    assert mock_create.await_args.kwargs["message_id"] == "12345"
    assert mock_create.await_args.kwargs["week_start"] == WEEK_START
    assert mock_create.await_args.kwargs["week_end"] == WEEK_END


@pytest.mark.asyncio
async def test_post_weekly_announcement_deletes_previous_message():
    """The previous week's message is fetched and deleted after the new one posts."""
    channel = _make_channel()
    sent = MagicMock()
    sent.id = 12345
    channel.send.return_value = sent
    old_message = MagicMock()
    old_message.delete = AsyncMock()
    channel.fetch_message.return_value = old_message
    bot = _make_bot(channel)

    previous = MagicMock()
    previous.message_id = "111"
    previous.channel_id = "999"

    session_patch, _session = _patch_session()

    with (
        session_patch,
        patch(f"{MODULE}.resolve_channel_id", side_effect=lambda cid: int(cid)),
        patch(
            f"{MODULE}.CalendarRepository.get_event_summaries_by_date",
            AsyncMock(return_value={}),
        ),
        patch(
            f"{MODULE}.WeeklyEventsAnnouncementRepository.get_all",
            AsyncMock(side_effect=[[previous], [previous]]),
        ),
        patch(f"{MODULE}.WeeklyEventsAnnouncementRepository.create", AsyncMock()),
        patch(f"{MODULE}.WeeklyEventsAnnouncementRepository.delete", AsyncMock()) as mock_delete,
    ):
        await WeeklyEventsService.post_weekly_announcement(bot, 999, today=SUNDAY)

    channel.fetch_message.assert_awaited_once_with(111)
    old_message.delete.assert_awaited_once()
    mock_delete.assert_awaited_once()


@pytest.mark.asyncio
async def test_post_weekly_announcement_survives_already_deleted_previous():
    """A previous message that no longer exists does not fail the run."""
    channel = _make_channel()
    sent = MagicMock()
    sent.id = 12345
    channel.send.return_value = sent
    channel.fetch_message.side_effect = discord.NotFound(MagicMock(status=404), "gone")
    bot = _make_bot(channel)

    previous = MagicMock()
    previous.message_id = "111"
    previous.channel_id = "999"

    session_patch, _session = _patch_session()

    with (
        session_patch,
        patch(f"{MODULE}.resolve_channel_id", side_effect=lambda cid: int(cid)),
        patch(
            f"{MODULE}.CalendarRepository.get_event_summaries_by_date",
            AsyncMock(return_value={}),
        ),
        patch(
            f"{MODULE}.WeeklyEventsAnnouncementRepository.get_all",
            AsyncMock(side_effect=[[previous], []]),
        ),
        patch(f"{MODULE}.WeeklyEventsAnnouncementRepository.create", AsyncMock()),
    ):
        result = await WeeklyEventsService.post_weekly_announcement(bot, 999, today=SUNDAY)

    assert result is sent


@pytest.mark.asyncio
async def test_post_weekly_announcement_missing_channel_returns_none():
    """An unavailable channel is a warning, not a crash, and nothing is recorded."""
    bot = MagicMock()
    bot.get_channel.return_value = None

    with (
        patch(f"{MODULE}.resolve_channel_id", side_effect=lambda cid: int(cid)),
        patch(f"{MODULE}.WeeklyEventsAnnouncementRepository.create", AsyncMock()) as mock_create,
    ):
        result = await WeeklyEventsService.post_weekly_announcement(bot, 999, today=SUNDAY)

    assert result is None
    mock_create.assert_not_awaited()


@pytest.mark.asyncio
async def test_post_weekly_announcement_keeps_previous_when_send_fails():
    """If sending fails, the previous announcement is left in place."""
    channel = _make_channel()
    channel.send.side_effect = discord.HTTPException(MagicMock(status=500), "boom")
    old_message = MagicMock()
    old_message.delete = AsyncMock()
    channel.fetch_message.return_value = old_message
    bot = _make_bot(channel)

    previous = MagicMock()
    previous.message_id = "111"
    previous.channel_id = "999"

    session_patch, _session = _patch_session()

    with (
        session_patch,
        patch(f"{MODULE}.resolve_channel_id", side_effect=lambda cid: int(cid)),
        patch(
            f"{MODULE}.CalendarRepository.get_event_summaries_by_date",
            AsyncMock(return_value={}),
        ),
        patch(
            f"{MODULE}.WeeklyEventsAnnouncementRepository.get_all",
            AsyncMock(return_value=[previous]),
        ),
        patch(f"{MODULE}.send_error_to_discord", AsyncMock()) as mock_report,
    ):
        result = await WeeklyEventsService.post_weekly_announcement(bot, 999, today=SUNDAY)

    assert result is None
    old_message.delete.assert_not_awaited()
    mock_report.assert_awaited_once()
