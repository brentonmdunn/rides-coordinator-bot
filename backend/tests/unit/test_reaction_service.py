"""Unit tests for ReactionService."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.core.enums import AskRidesMessage, Emoji, RideOption
from bot.services.reaction_service import ReactionService


def _make_bot(channel=None):
    bot = MagicMock()
    bot.get_channel.return_value = channel
    return bot


def _make_user(name: str, is_bot: bool = False):
    user = MagicMock()
    user.name = name
    user.bot = is_bot
    return user


async def _async_iter(items):
    for item in items:
        yield item


def _make_reaction(emoji: str, users: list):
    reaction = MagicMock()
    reaction.emoji = emoji
    reaction.users.return_value = _async_iter(users)
    return reaction


@pytest.mark.asyncio
async def test_get_usernames_who_reacted_returns_human_users():
    human = _make_user("alice")
    bot_user = _make_user("BotUser", is_bot=True)
    reaction = _make_reaction("👍", [human, bot_user])

    message = AsyncMock()
    message.reactions = [reaction]

    channel = MagicMock()
    channel.fetch_message = AsyncMock(return_value=message)

    svc = ReactionService(_make_bot(channel))
    result = await svc.get_usernames_who_reacted.__wrapped__(svc, 123, 456)

    assert "alice" in result
    assert "BotUser" not in result


@pytest.mark.asyncio
async def test_get_usernames_filters_sunday_dropoff_back():
    """SUNDAY_DROPOFF_BACK skips LUNCH and SOMETHING_ELSE emoji reactions."""
    alice = _make_user("alice")
    bob = _make_user("bob")
    reaction_lunch = _make_reaction(Emoji.LUNCH, [alice])
    reaction_ok = _make_reaction("✅", [bob])

    message = AsyncMock()
    message.reactions = [reaction_lunch, reaction_ok]

    channel = MagicMock()
    channel.fetch_message = AsyncMock(return_value=message)

    svc = ReactionService(_make_bot(channel))
    result = await svc.get_usernames_who_reacted.__wrapped__(
        svc, 123, 456, RideOption.SUNDAY_DROPOFF_BACK
    )

    assert "alice" not in result
    assert "bob" in result


@pytest.mark.asyncio
async def test_get_usernames_filters_sunday_dropoff_lunch():
    """SUNDAY_DROPOFF_LUNCH skips NO_LUNCH and SOMETHING_ELSE emoji reactions."""
    alice = _make_user("alice")
    bob = _make_user("bob")
    reaction_no_lunch = _make_reaction(Emoji.NO_LUNCH, [alice])
    reaction_ok = _make_reaction("✅", [bob])

    message = AsyncMock()
    message.reactions = [reaction_no_lunch, reaction_ok]

    channel = MagicMock()
    channel.fetch_message = AsyncMock(return_value=message)

    svc = ReactionService(_make_bot(channel))
    result = await svc.get_usernames_who_reacted.__wrapped__(
        svc, 123, 456, RideOption.SUNDAY_DROPOFF_LUNCH
    )

    assert "alice" not in result
    assert "bob" in result


@pytest.mark.asyncio
async def test_find_all_messages_returns_none_for_missing_channel():
    """When bot.get_channel returns None, all keys map to None."""
    svc = ReactionService(_make_bot(channel=None))
    results = await svc._find_all_messages(999)

    assert all(v is None for v in results.values())
    assert set(results.keys()) == set(AskRidesMessage)


@pytest.mark.asyncio
async def test_find_all_driver_messages_returns_none_for_missing_channel():
    """When bot.get_channel returns None, all driver keys map to None."""
    svc = ReactionService(_make_bot(channel=None))
    results = await svc._find_all_driver_messages(999)

    assert all(v is None for v in results.values())


@pytest.mark.asyncio
async def test_get_driver_reactions_invalid_event_raises():
    svc = ReactionService(_make_bot())
    with pytest.raises(ValueError, match="Invalid event"):
        await svc.get_driver_reactions.__wrapped__(svc, AskRidesMessage.SUNDAY_CLASS)


@pytest.mark.asyncio
async def test_get_ask_rides_reactions_returns_none_when_no_message():
    svc = ReactionService(_make_bot())
    svc.find_correct_message = AsyncMock(return_value=None)

    result = await svc.get_ask_rides_reactions.__wrapped__(svc, AskRidesMessage.FRIDAY_FELLOWSHIP)

    assert result is None


@pytest.mark.asyncio
async def test_get_driver_reactions_returns_none_when_no_message():
    svc = ReactionService(_make_bot())
    svc.find_driver_message = AsyncMock(return_value=None)

    result = await svc.get_driver_reactions.__wrapped__(svc, AskRidesMessage.FRIDAY_FELLOWSHIP)

    assert result is None


@pytest.mark.asyncio
async def test_get_ask_rides_reactions_handles_not_found():
    """discord.NotFound clears the cache and returns None."""
    import discord

    svc = ReactionService(_make_bot())
    svc.find_correct_message = AsyncMock(return_value=42)
    svc.find_correct_message.cache_set = AsyncMock()

    channel = MagicMock()
    channel.fetch_message = AsyncMock(side_effect=discord.NotFound(MagicMock(), "gone"))
    svc.bot.get_channel.return_value = channel

    result = await svc.get_ask_rides_reactions.__wrapped__(svc, AskRidesMessage.FRIDAY_FELLOWSHIP)

    assert result is None
    svc.find_correct_message.cache_set.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_ask_rides_reactions_aggregates_users():
    alice = _make_user("alice")
    bob = _make_user("bob")
    reactions = [
        _make_reaction("👍", [alice]),
        _make_reaction("❤️", [bob]),
    ]

    message = AsyncMock()
    message.reactions = reactions

    channel = MagicMock()
    channel.fetch_message = AsyncMock(return_value=message)

    svc = ReactionService(_make_bot(channel))
    svc.find_correct_message = AsyncMock(return_value=99)

    mock_session = AsyncMock()
    mock_session_cm = MagicMock()
    mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("bot.services.reaction_service.AsyncSessionLocal", return_value=mock_session_cm):
        with patch(
            "bot.services.reaction_service.LocationsRepository.get_names_for_usernames",
            new_callable=AsyncMock,
            return_value={"alice": "Alice Smith", "bob": "Bob Jones"},
        ):
            result = await svc.get_ask_rides_reactions.__wrapped__(
                svc, AskRidesMessage.FRIDAY_FELLOWSHIP
            )

    assert "alice" in result["reactions"].get("👍", [])
    assert result["username_to_name"]["alice"] == "Alice Smith"


# ---------------------------------------------------------------------------
# _find_all_driver_messages — channel exists
# ---------------------------------------------------------------------------


async def _aiter(items):
    for item in items:
        yield item


def _make_driver_message(content: str, msg_id: int):
    """Build a minimal mock Discord message for driver-channel tests."""
    msg = MagicMock()
    msg.content = content
    msg.id = msg_id
    msg.embeds = []
    return msg


def _stub_find_driver_message(svc):
    """
    Replace svc.find_driver_message with an AsyncMock that also has a cache_set stub.

    The real find_driver_message is an alru_cache-wrapped bound method — its cache_set
    lives on the wrapper function object, not on the bound method, so you can't set
    attributes on it directly.  Replacing it with an AsyncMock makes it fully writable.
    """
    stub = AsyncMock()
    stub.cache_set = AsyncMock()
    svc.find_driver_message = stub
    return stub


@pytest.mark.asyncio
async def test_find_all_driver_messages_friday_keyword_matched():
    """Messages containing driver role mention + 'friday' map to FRIDAY_FELLOWSHIP."""
    from bot.core.enums import RoleIds

    driver_mention = f"<@&{RoleIds.DRIVER}>"
    friday_msg = _make_driver_message(f"{driver_mention} Friday rides needed!", 101)
    # A message without the driver mention should be ignored
    noise_msg = _make_driver_message("Just a regular message about friday", 102)

    channel = MagicMock()
    channel.history.return_value = _aiter([friday_msg, noise_msg])

    svc = ReactionService(_make_bot(channel))
    _stub_find_driver_message(svc)

    results = await svc._find_all_driver_messages(999)

    assert results[AskRidesMessage.FRIDAY_FELLOWSHIP] == 101
    # noise message was filtered out, so sunday keys remain None
    assert results[AskRidesMessage.SUNDAY_SERVICE] is None
    assert results[AskRidesMessage.SUNDAY_CLASS] is None


@pytest.mark.asyncio
async def test_find_all_driver_messages_sunday_service_matched():
    """Messages containing driver role mention + 'sunday service' keyword map to SUNDAY_SERVICE."""
    from bot.core.enums import RoleIds

    driver_mention = f"<@&{RoleIds.DRIVER}>"
    sun_msg = _make_driver_message(f"{driver_mention} Sunday service drivers needed!", 201)

    channel = MagicMock()
    channel.history.return_value = _aiter([sun_msg])

    svc = ReactionService(_make_bot(channel))
    _stub_find_driver_message(svc)

    results = await svc._find_all_driver_messages(999)

    assert results[AskRidesMessage.SUNDAY_SERVICE] == 201


@pytest.mark.asyncio
async def test_find_all_driver_messages_sunday_class_matched():
    """Messages with driver mention + 'class' keyword map to SUNDAY_CLASS."""
    from bot.core.enums import RoleIds

    driver_mention = f"<@&{RoleIds.DRIVER}>"
    class_msg = _make_driver_message(f"{driver_mention} Sunday class drivers!", 301)

    channel = MagicMock()
    channel.history.return_value = _aiter([class_msg])

    svc = ReactionService(_make_bot(channel))
    _stub_find_driver_message(svc)

    results = await svc._find_all_driver_messages(999)

    assert results[AskRidesMessage.SUNDAY_CLASS] == 301


@pytest.mark.asyncio
async def test_find_all_driver_messages_only_most_recent_kept():
    """When two matching messages exist, only the later one (last seen) is kept."""
    from bot.core.enums import RoleIds

    driver_mention = f"<@&{RoleIds.DRIVER}>"
    older_msg = _make_driver_message(f"{driver_mention} Friday rides (older)", 10)
    newer_msg = _make_driver_message(f"{driver_mention} Friday rides (newer)", 20)

    channel = MagicMock()
    channel.history.return_value = _aiter([older_msg, newer_msg])

    svc = ReactionService(_make_bot(channel))
    _stub_find_driver_message(svc)

    results = await svc._find_all_driver_messages(999)

    # The last matched message wins
    assert results[AskRidesMessage.FRIDAY_FELLOWSHIP] == 20


# ---------------------------------------------------------------------------
# get_driver_reactions — message exists with reactions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_driver_reactions_aggregates_reactions():
    """get_driver_reactions returns aggregated reactions + name map."""
    alice = _make_user("alice")
    bob = _make_user("bob")
    reactions = [
        _make_reaction("👍", [alice]),
        _make_reaction("❌", [bob]),
    ]

    message = AsyncMock()
    message.reactions = reactions

    channel = MagicMock()
    channel.fetch_message = AsyncMock(return_value=message)

    svc = ReactionService(_make_bot(channel))
    svc.find_driver_message = AsyncMock(return_value=55)

    mock_session = AsyncMock()
    mock_session_cm = MagicMock()
    mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("bot.services.reaction_service.AsyncSessionLocal", return_value=mock_session_cm):
        with patch(
            "bot.services.reaction_service.LocationsRepository.get_names_for_usernames",
            new_callable=AsyncMock,
            return_value={"alice": "Alice Smith", "bob": "Bob Jones"},
        ):
            result = await svc.get_driver_reactions.__wrapped__(
                svc, AskRidesMessage.FRIDAY_FELLOWSHIP
            )

    assert result is not None
    assert "alice" in result["reactions"].get("👍", [])
    assert "bob" in result["reactions"].get("❌", [])
    assert result["username_to_name"]["alice"] == "Alice Smith"
    assert result["username_to_name"]["bob"] == "Bob Jones"


@pytest.mark.asyncio
async def test_get_driver_reactions_filters_bot_users():
    """Bot users are not included in the reaction aggregation."""
    human = _make_user("driver_human")
    bot_user = _make_user("AutoBot", is_bot=True)
    reactions = [_make_reaction("👍", [human, bot_user])]

    message = AsyncMock()
    message.reactions = reactions

    channel = MagicMock()
    channel.fetch_message = AsyncMock(return_value=message)

    svc = ReactionService(_make_bot(channel))
    svc.find_driver_message = AsyncMock(return_value=66)

    mock_session = AsyncMock()
    mock_session_cm = MagicMock()
    mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("bot.services.reaction_service.AsyncSessionLocal", return_value=mock_session_cm):
        with patch(
            "bot.services.reaction_service.LocationsRepository.get_names_for_usernames",
            new_callable=AsyncMock,
            return_value={"driver_human": "Driver Human"},
        ):
            result = await svc.get_driver_reactions.__wrapped__(
                svc, AskRidesMessage.FRIDAY_FELLOWSHIP
            )

    assert "driver_human" in result["reactions"].get("👍", [])
    assert "AutoBot" not in result["reactions"].get("👍", [])


# ---------------------------------------------------------------------------
# get_driver_reactions — discord.NotFound clears cache and returns None
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_driver_reactions_handles_not_found():
    """discord.NotFound clears the driver message cache and returns None."""
    import discord

    svc = ReactionService(_make_bot())
    svc.find_driver_message = AsyncMock(return_value=77)
    svc.find_driver_message.cache_set = AsyncMock()

    channel = MagicMock()
    channel.fetch_message = AsyncMock(side_effect=discord.NotFound(MagicMock(), "gone"))
    svc.bot.get_channel.return_value = channel

    result = await svc.get_driver_reactions.__wrapped__(svc, AskRidesMessage.FRIDAY_FELLOWSHIP)

    assert result is None
    svc.find_driver_message.cache_set.assert_awaited_once()
