"""Unit tests for bot/utils/checks.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from bot.utils.checks import feature_flag_enabled, is_admin

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_predicate(check_decorator):
    """Apply the check decorator to a dummy function and return the predicate."""

    async def _dummy():
        pass

    decorated = check_decorator(_dummy)
    return decorated.__discord_app_commands_checks__[0]


def _make_interaction(is_admin_member: bool | None = None) -> MagicMock:
    """Build a minimal Discord interaction mock."""
    interaction = MagicMock(spec=discord.Interaction)
    interaction.guild = MagicMock()
    if is_admin_member is None:
        interaction.user = None
    else:
        member = MagicMock(spec=discord.Member)
        member.guild_permissions.administrator = is_admin_member
        interaction.user = member
    return interaction


# ---------------------------------------------------------------------------
# is_admin
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_is_admin_returns_false_in_dm():
    """DM interactions (no guild) always return False."""
    interaction = MagicMock(spec=discord.Interaction)
    interaction.guild = None
    interaction.user = MagicMock()

    predicate = _extract_predicate(is_admin())
    result = await predicate(interaction)
    assert result is False


@pytest.mark.asyncio
async def test_is_admin_returns_false_when_no_user():
    interaction = MagicMock(spec=discord.Interaction)
    interaction.guild = MagicMock()
    interaction.user = None

    predicate = _extract_predicate(is_admin())
    result = await predicate(interaction)
    assert result is False


@pytest.mark.asyncio
async def test_is_admin_returns_true_for_admin_member():
    interaction = _make_interaction(is_admin_member=True)
    predicate = _extract_predicate(is_admin())
    result = await predicate(interaction)
    assert result is True


@pytest.mark.asyncio
async def test_is_admin_returns_false_for_non_admin_member():
    interaction = _make_interaction(is_admin_member=False)
    predicate = _extract_predicate(is_admin())
    result = await predicate(interaction)
    assert result is False


@pytest.mark.asyncio
async def test_is_admin_returns_false_for_non_member_user():
    """A plain discord.User (not discord.Member) always returns False."""
    user = MagicMock(spec=discord.User)
    interaction = MagicMock(spec=discord.Interaction)
    interaction.guild = MagicMock()
    interaction.user = user

    predicate = _extract_predicate(is_admin())
    result = await predicate(interaction)
    assert result is False


# ---------------------------------------------------------------------------
# feature_flag_enabled
# ---------------------------------------------------------------------------


async def _dummy_func(*args, **kwargs):
    return "called"


def _make_async_interaction() -> MagicMock:
    """Build a spec'd Interaction mock so isinstance checks pass in checks.py."""
    interaction = MagicMock(spec=discord.Interaction)
    interaction.user = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    return interaction


@pytest.mark.asyncio
async def test_feature_flag_enabled_from_cache_allows_execution():
    """Feature flag in cache (True) allows the wrapped function to run."""
    with patch("bot.utils.checks.FeatureFlagsRepository") as MockRepo:
        MockRepo._cache = {"my_feature": True}

        wrapped = feature_flag_enabled("my_feature")(_dummy_func)
        result = await wrapped()

    assert result == "called"


@pytest.mark.asyncio
async def test_feature_flag_disabled_in_cache_blocks_with_interaction():
    """Feature flag cached False sends ephemeral message and returns None."""
    interaction = _make_async_interaction()

    with patch("bot.utils.checks.FeatureFlagsRepository") as MockRepo:
        MockRepo._cache = {"my_feature": False}

        wrapped = feature_flag_enabled("my_feature")(_dummy_func)
        result = await wrapped(interaction)

    assert result is None
    interaction.response.send_message.assert_awaited_once()
    call_kwargs = interaction.response.send_message.call_args[1]
    assert call_kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_feature_flag_disabled_in_cache_blocks_job_no_interaction():
    """Feature flag cached False with no interaction simply returns None."""
    with patch("bot.utils.checks.FeatureFlagsRepository") as MockRepo:
        MockRepo._cache = {"my_feature": False}

        wrapped = feature_flag_enabled("my_feature")(_dummy_func)
        result = await wrapped()

    assert result is None


@pytest.mark.asyncio
async def test_feature_flag_fetched_from_db_when_not_in_cache():
    """When flag is absent from cache, a DB lookup is performed."""
    mock_session = AsyncMock()
    mock_session_cm = MagicMock()
    mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_cm.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("bot.utils.checks.FeatureFlagsRepository") as MockRepo,
        patch("bot.utils.checks.AsyncSessionLocal", return_value=mock_session_cm),
    ):
        MockRepo._cache = {}
        MockRepo.get_feature_flag_status = AsyncMock(return_value=True)

        wrapped = feature_flag_enabled("my_feature")(_dummy_func)
        result = await wrapped()

    assert result == "called"


@pytest.mark.asyncio
async def test_feature_flag_db_returns_none_blocks_execution():
    """When DB returns None for a flag, feature is treated as disabled."""
    mock_session = AsyncMock()
    mock_session_cm = MagicMock()
    mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_cm.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("bot.utils.checks.FeatureFlagsRepository") as MockRepo,
        patch("bot.utils.checks.AsyncSessionLocal", return_value=mock_session_cm),
    ):
        MockRepo._cache = {}
        MockRepo.get_feature_flag_status = AsyncMock(return_value=None)

        wrapped = feature_flag_enabled("my_feature")(_dummy_func)
        result = await wrapped()

    assert result is None


@pytest.mark.asyncio
async def test_feature_flag_db_exception_with_interaction_sends_error():
    """DB exception sends error message via the interaction and returns None."""
    interaction = _make_async_interaction()

    with (
        patch("bot.utils.checks.FeatureFlagsRepository") as MockRepo,
        patch("bot.utils.checks.AsyncSessionLocal", side_effect=RuntimeError("db gone")),
    ):
        MockRepo._cache = {}

        wrapped = feature_flag_enabled("my_feature")(_dummy_func)
        result = await wrapped(interaction)

    assert result is None
    interaction.response.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_feature_flag_db_exception_no_interaction_returns_none():
    """DB exception without an interaction just returns None silently."""
    with (
        patch("bot.utils.checks.FeatureFlagsRepository") as MockRepo,
        patch("bot.utils.checks.AsyncSessionLocal", side_effect=RuntimeError("db gone")),
    ):
        MockRepo._cache = {}

        wrapped = feature_flag_enabled("my_feature", enable_logs=False)(_dummy_func)
        result = await wrapped()

    assert result is None


@pytest.mark.asyncio
async def test_feature_flag_found_via_kwargs():
    """Interaction passed as a keyword argument is found correctly."""
    interaction = _make_async_interaction()

    with patch("bot.utils.checks.FeatureFlagsRepository") as MockRepo:
        MockRepo._cache = {"my_feature": False}

        wrapped = feature_flag_enabled("my_feature")(_dummy_func)
        result = await wrapped(interaction=interaction)

    assert result is None
    interaction.response.send_message.assert_awaited_once()
