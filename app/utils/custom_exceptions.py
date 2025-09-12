from discord.ext import commands


class NotAllowedInChannelError(commands.CommandError):
    """Exception raised when a command is used in a non-whitelisted channel."""

    pass


class NoMatchingMessageFoundError(commands.CommandError):
    """Exception raised when a specific message cannot be found."""

    pass
