"""Unit tests for bot.utils.custom_exceptions."""

from discord.ext import commands

from bot.utils.custom_exceptions import (
    ChannelNotFoundError,
    GuildNotFoundError,
    MessageNotFoundError,
    NoMatchingMessageFoundError,
    NotAllowedInChannelError,
    RoleNotFoundError,
    RoleServiceError,
)


class TestExceptionHierarchy:
    """Verify exception inheritance chains."""

    def test_not_allowed_is_command_error(self):
        assert issubclass(NotAllowedInChannelError, commands.CommandError)

    def test_no_matching_message_is_command_error(self):
        assert issubclass(NoMatchingMessageFoundError, commands.CommandError)

    def test_role_service_error_is_base(self):
        assert issubclass(RoleServiceError, Exception)

    def test_guild_not_found_is_role_service_error(self):
        assert issubclass(GuildNotFoundError, RoleServiceError)

    def test_channel_not_found_is_role_service_error(self):
        assert issubclass(ChannelNotFoundError, RoleServiceError)

    def test_message_not_found_is_role_service_error(self):
        assert issubclass(MessageNotFoundError, RoleServiceError)

    def test_role_not_found_is_role_service_error(self):
        assert issubclass(RoleNotFoundError, RoleServiceError)


class TestExceptionInstantiation:
    """Verify exceptions can be raised and caught."""

    def test_raise_not_allowed(self):
        try:
            raise NotAllowedInChannelError("cannot use here")
        except commands.CommandError:
            pass

    def test_raise_guild_not_found(self):
        try:
            raise GuildNotFoundError("guild 123 not found")
        except RoleServiceError as e:
            assert "guild 123" in str(e)

    def test_raise_role_not_found(self):
        try:
            raise RoleNotFoundError("Admin")
        except RoleServiceError:
            pass
