"""Service for driver-related operations."""
from app.core.enums import (
    DaysOfWeek,
    RoleIds,
)
from app.utils.format_message import ping_role_with_message


class DriverService:
    """Service for handling driver-related logic."""
    def get_emojis(self, day: DaysOfWeek) -> list[str]:
        """Lists emoji reactions for driver availability.

        Args:
            day (DaysOfWeek): The day of the week.

        Returns:
            list[str]: A list of emojis.
        """
        if day == DaysOfWeek.SUNDAY:
            return ["🍔", "🏠", "🔄", "❌", "➡️", "⬅️", "✳️"]
        else:  # Friday
            return ["👍", "❌", "➡️", "⬅️", "✳️"]

    def format_message(self, message: str) -> str:
        """Adds @driver ping before message.

        Args:
            message (str): The message to ping.

        Returns:
            str: The formatted message.
        """
        return ping_role_with_message(RoleIds.DRIVER, message)
