"""Unit tests for bot.services.ride_coordinator_service."""

from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest
from sqlalchemy.exc import OperationalError

from bot.services.ride_coordinator_service import (
    FALLBACK_PING_TEXT,
    RideCoordinatorService,
    UserLookupStatus,
)


class TestIsValidSnowflake:
    """Tests for RideCoordinatorService.is_valid_snowflake."""

    @pytest.mark.parametrize(
        "value",
        ["12345678901234567", "123456789012345678901"[:20], "1" * 17, "1" * 20],
    )
    def test_valid_shapes(self, value):
        assert RideCoordinatorService.is_valid_snowflake(value) is True

    @pytest.mark.parametrize(
        "value",
        ["", "abc", "123", "1" * 16, "1" * 21, "12345678901234567a", "123 456789012345"],
    )
    def test_invalid_shapes(self, value):
        assert RideCoordinatorService.is_valid_snowflake(value) is False


class TestGetCoordinatorId:
    """Tests for RideCoordinatorService.get_coordinator_id."""

    @pytest.mark.asyncio
    async def test_returns_value_from_repository(self):
        mock_session = AsyncMock()
        mock_session_cm = MagicMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=False)

        with (
            patch(
                "bot.services.ride_coordinator_service.AsyncSessionLocal",
                return_value=mock_session_cm,
            ),
            patch(
                "bot.services.ride_coordinator_service.GlobalSettingsRepository.get",
                new=AsyncMock(return_value="123456789012345678"),
            ),
        ):
            result = await RideCoordinatorService.get_coordinator_id()

        assert result == "123456789012345678"

    @pytest.mark.asyncio
    async def test_returns_none_on_db_failure(self):
        with patch(
            "bot.services.ride_coordinator_service.AsyncSessionLocal",
            side_effect=OperationalError("stmt", {}, Exception("no such table")),
        ):
            result = await RideCoordinatorService.get_coordinator_id()

        assert result is None


class TestSetCoordinatorId:
    """Tests for RideCoordinatorService.set_coordinator_id."""

    @pytest.mark.asyncio
    async def test_rejects_non_snowflake(self):
        with pytest.raises(ValueError, match="snowflake"):
            await RideCoordinatorService.set_coordinator_id("not-a-snowflake")

    @pytest.mark.asyncio
    async def test_persists_valid_value(self):
        mock_session = AsyncMock()
        mock_session_cm = MagicMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=False)

        with (
            patch(
                "bot.services.ride_coordinator_service.AsyncSessionLocal",
                return_value=mock_session_cm,
            ),
            patch(
                "bot.services.ride_coordinator_service.GlobalSettingsRepository.set",
                new=AsyncMock(),
            ) as mock_set,
        ):
            await RideCoordinatorService.set_coordinator_id("123456789012345678")

        mock_set.assert_awaited_once()


class TestResolvePingText:
    """Tests for RideCoordinatorService.resolve_ping_text."""

    @pytest.mark.asyncio
    async def test_falls_back_when_unset(self):
        with patch(
            "bot.services.ride_coordinator_service.RideCoordinatorService.get_coordinator_id",
            new=AsyncMock(return_value=None),
        ):
            text, configured = await RideCoordinatorService.resolve_ping_text(None)

        assert text == FALLBACK_PING_TEXT
        assert configured is False

    @pytest.mark.asyncio
    async def test_falls_back_when_malformed(self):
        with patch(
            "bot.services.ride_coordinator_service.RideCoordinatorService.get_coordinator_id",
            new=AsyncMock(return_value="not-numeric"),
        ):
            text, configured = await RideCoordinatorService.resolve_ping_text(None)

        assert text == FALLBACK_PING_TEXT
        assert configured is False

    @pytest.mark.asyncio
    async def test_falls_back_when_db_read_fails(self):
        # get_coordinator_id itself never raises; simulate the underlying
        # OperationalError being swallowed and surfaced as None.
        with patch(
            "bot.services.ride_coordinator_service.RideCoordinatorService.get_coordinator_id",
            new=AsyncMock(return_value=None),
        ):
            text, configured = await RideCoordinatorService.resolve_ping_text(None)

        assert text == FALLBACK_PING_TEXT
        assert configured is False

    @pytest.mark.asyncio
    async def test_returns_mention_when_configured(self):
        with patch(
            "bot.services.ride_coordinator_service.RideCoordinatorService.get_coordinator_id",
            new=AsyncMock(return_value="123456789012345678"),
        ):
            text, configured = await RideCoordinatorService.resolve_ping_text(None)

        assert text == "<@123456789012345678> "
        assert configured is True


class TestTryResolveDiscordUser:
    """Tests for RideCoordinatorService.try_resolve_discord_user."""

    @pytest.mark.asyncio
    async def test_verified(self):
        fake_user = MagicMock()
        fake_bot = MagicMock()
        fake_bot.fetch_user = AsyncMock(return_value=fake_user)

        status, user = await RideCoordinatorService.try_resolve_discord_user(
            fake_bot, "123456789012345678"
        )

        assert status == UserLookupStatus.VERIFIED
        assert user is fake_user

    @pytest.mark.asyncio
    async def test_not_found(self):
        fake_bot = MagicMock()
        fake_bot.fetch_user = AsyncMock(side_effect=discord.NotFound(MagicMock(), "gone"))

        status, user = await RideCoordinatorService.try_resolve_discord_user(
            fake_bot, "123456789012345678"
        )

        assert status == UserLookupStatus.NOT_FOUND
        assert user is None

    @pytest.mark.asyncio
    async def test_unavailable_on_other_errors(self):
        fake_bot = MagicMock()
        fake_bot.fetch_user = AsyncMock(side_effect=RuntimeError("network blip"))

        status, user = await RideCoordinatorService.try_resolve_discord_user(
            fake_bot, "123456789012345678"
        )

        assert status == UserLookupStatus.UNAVAILABLE
        assert user is None
