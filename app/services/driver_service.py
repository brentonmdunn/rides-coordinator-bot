from app.core.enums import (
    DaysOfWeek,
    RoleIds,
)
from app.utils.format_message import ping_role_with_message


class DriverService:
    def get_emojis(self, day: DaysOfWeek) -> list[str]:
        """
        Lists emoji reactions for driver availability.

        Args:
            day: Day of week

        Returns:
            List of emojis
        """
        if day == DaysOfWeek.SUNDAY:
            return ["🍔", "🏠", "🔄", "❌", "➡️", "⬅️", "✳️"]
        else:  # Friday
            return ["👍", "❌", "➡️", "⬅️", "✳️"]

    def format_message(self, message: str) -> str:
        """
        Adds @driver ping before message

        Args:
            message: Message to ping

        Returns:
            Formatted message
        """
        return ping_role_with_message(RoleIds.DRIVER, message)
