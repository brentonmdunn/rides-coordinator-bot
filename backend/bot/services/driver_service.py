"""Service for driver-related operations."""

from bot.core.enums import (
    DaysOfWeek,
    Emoji,
    RoleIds,
)
from bot.utils.format_message import ping_role_with_message


class DriverService:
    """Service for handling driver-related logic."""

    def get_emojis(self, day: DaysOfWeek) -> list[str]:
        """
        Lists emoji reactions for driver availability.

        Args:
            day (DaysOfWeek): The day of the week.

        Returns:
            list[str]: A list of emojis.
        """
        if day == DaysOfWeek.SUNDAY:
            return [
                Emoji.LUNCH,
                Emoji.NO_LUNCH,
                Emoji.EITHER_NO_PREFERENCE,
                Emoji.CANNOT_DRIVE,
                Emoji.DRIVE_THERE,
                Emoji.DRIVE_BACK,
                Emoji.SOMETHING_ELSE,
            ]
        else:  # Friday
            return [
                Emoji.CAN_DRIVE,
                Emoji.CANNOT_DRIVE,
                Emoji.DRIVE_THERE,
                Emoji.DRIVE_BACK,
                Emoji.SOMETHING_ELSE,
            ]

    def format_message(self, message: str) -> str:
        """
        Adds @driver ping before message.

        Args:
            message (str): The message to ping.

        Returns:
            str: The formatted message.
        """
        return ping_role_with_message(RoleIds.DRIVER, message)
