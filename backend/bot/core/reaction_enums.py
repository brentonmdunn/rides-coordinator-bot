"""Enumerations for reaction emojis."""

from enum import StrEnum


class ReactionAction(StrEnum):
    """Enum representing the type of reaction action.

    Attributes:
        ADD: Represents adding a reaction to a message.
        REMOVE: Represents removing a reaction from a message.
    """

    ADD = "add"
    REMOVE = "remove"
