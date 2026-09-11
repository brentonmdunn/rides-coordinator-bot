"""utils/custom_exceptions.py"""

from discord.ext import commands


class NotAllowedInChannelError(commands.CommandError):
    """Exception raised when a command is used in a non-whitelisted channel."""

    pass


class NoMatchingMessageFoundError(commands.CommandError):
    """Exception raised when a specific message cannot be found."""

    pass


class RoleServiceError(Exception):
    """Base exception for the role service."""

    pass


class GuildNotFoundError(RoleServiceError):
    """Raised when a guild cannot be found."""

    pass


class ChannelNotFoundError(RoleServiceError):
    """Raised when a text channel cannot be found."""

    pass


class MessageNotFoundError(RoleServiceError):
    """Raised when a message cannot be found."""

    pass


class RoleNotFoundError(RoleServiceError):
    """Raised when a role cannot be found by name."""

    pass
