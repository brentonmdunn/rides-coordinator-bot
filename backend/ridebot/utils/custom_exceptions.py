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


class PickupInfoValidationError(ValueError):
    """Raised when pickup info input is invalid."""

    pass


class PickupInfoNotFoundError(LookupError):
    """Raised when a pickup info entry does not exist."""

    pass


class PickupInfoConflictError(ValueError):
    """Raised when a pickup info write would duplicate a Discord username or user ID."""

    pass
