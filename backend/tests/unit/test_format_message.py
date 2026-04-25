"""Unit tests for bot.utils.format_message."""

from bot.core.enums import ChannelIds, RoleIds
from bot.utils.format_message import (
    message_link,
    ping_channel,
    ping_role,
    ping_role_with_message,
    ping_user,
)


class TestPingRole:
    """Tests for ping_role."""

    def test_basic(self):
        assert ping_role(RoleIds.DRIVER) == f"<@&{RoleIds.DRIVER}> "

    def test_contains_role_id(self):
        result = ping_role(RoleIds.RIDES)
        assert str(RoleIds.RIDES.value) in result

    def test_format(self):
        result = ping_role(RoleIds.DRIVER)
        assert result.startswith("<@&")
        assert result.endswith("> ")


class TestPingRoleWithMessage:
    """Tests for ping_role_with_message."""

    def test_basic(self):
        result = ping_role_with_message(RoleIds.DRIVER, "Hello!")
        assert result == f"<@&{RoleIds.DRIVER}> Hello!"

    def test_empty_message(self):
        result = ping_role_with_message(RoleIds.RIDES, "")
        assert result == f"<@&{RoleIds.RIDES}> "

    def test_contains_message(self):
        msg = "Please check the schedule"
        result = ping_role_with_message(RoleIds.RIDE_COORDINATOR, msg)
        assert msg in result


class TestPingChannel:
    """Tests for ping_channel."""

    def test_basic(self):
        result = ping_channel(ChannelIds.BOT_STUFF__BOTS)
        assert result == f"<#{ChannelIds.BOT_STUFF__BOTS}> "

    def test_format(self):
        result = ping_channel(ChannelIds.SERVING__DRIVER_CHAT_WOOOOO)
        assert result.startswith("<#")
        assert result.endswith("> ")


class TestPingUser:
    """Tests for ping_user."""

    def test_basic(self):
        assert ping_user(123456789) == "<@123456789> "

    def test_format(self):
        result = ping_user(999)
        assert result.startswith("<@")
        assert result.endswith("> ")
        assert "999" in result


class TestMessageLink:
    """Tests for message_link."""

    def test_basic(self):
        result = message_link(111, 222, 333)
        assert result == "https://discord.com/channels/111/222/333"

    def test_real_ids(self):
        result = message_link(916817752918982716, 939950319721406464, 1000000000)
        assert "916817752918982716" in result
        assert "939950319721406464" in result
        assert "1000000000" in result

    def test_returns_string(self):
        assert isinstance(message_link(1, 2, 3), str)
