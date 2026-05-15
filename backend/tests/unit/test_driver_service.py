"""Unit tests for DriverService."""

from bot.core.enums import DaysOfWeek, Emoji, RoleIds
from bot.services.driver_service import DriverService


class TestGetEmojis:
    """Tests for DriverService.get_emojis — covers lines 24-41."""

    def test_sunday_returns_all_seven_emojis(self):
        """Sunday emoji list has exactly 7 items including lunch-specific emojis."""
        service = DriverService()
        result = service.get_emojis(DaysOfWeek.SUNDAY)

        assert isinstance(result, list)
        assert len(result) == 7
        assert Emoji.LUNCH in result
        assert Emoji.NO_LUNCH in result
        assert Emoji.EITHER_NO_PREFERENCE in result
        assert Emoji.CANNOT_DRIVE in result
        assert Emoji.DRIVE_THERE in result
        assert Emoji.DRIVE_BACK in result
        assert Emoji.SOMETHING_ELSE in result

    def test_sunday_does_not_contain_can_drive(self):
        """Sunday list should not include the generic CAN_DRIVE emoji."""
        service = DriverService()
        result = service.get_emojis(DaysOfWeek.SUNDAY)
        assert Emoji.CAN_DRIVE not in result

    def test_friday_returns_five_emojis(self):
        """Friday emoji list has exactly 5 items."""
        service = DriverService()
        result = service.get_emojis(DaysOfWeek.FRIDAY)

        assert isinstance(result, list)
        assert len(result) == 5
        assert Emoji.CAN_DRIVE in result
        assert Emoji.CANNOT_DRIVE in result
        assert Emoji.DRIVE_THERE in result
        assert Emoji.DRIVE_BACK in result
        assert Emoji.SOMETHING_ELSE in result

    def test_friday_does_not_contain_lunch_emojis(self):
        """Friday list should not include Sunday-specific lunch emojis."""
        service = DriverService()
        result = service.get_emojis(DaysOfWeek.FRIDAY)
        assert Emoji.LUNCH not in result
        assert Emoji.NO_LUNCH not in result
        assert Emoji.EITHER_NO_PREFERENCE not in result

    def test_non_sunday_day_returns_friday_set(self):
        """Any day that is not SUNDAY should return the Friday/default emoji set."""
        service = DriverService()
        # SATURDAY is neither SUNDAY nor FRIDAY — should fall through to the else branch
        result = service.get_emojis(DaysOfWeek.SATURDAY)
        assert Emoji.CAN_DRIVE in result
        assert Emoji.LUNCH not in result


class TestFormatMessage:
    """Tests for DriverService.format_message — covers line 53."""

    def test_format_message_prepends_driver_role_ping(self):
        """format_message should prepend the DRIVER role mention to the message."""
        service = DriverService()
        message = "Are you available to drive?"
        result = service.format_message(message)

        expected_ping = f"<@&{RoleIds.DRIVER}>"
        assert expected_ping in result
        assert message in result

    def test_format_message_structure(self):
        """Returned string should be '<@&ROLE_ID> <message>'."""
        service = DriverService()
        result = service.format_message("hello")
        assert result == f"<@&{RoleIds.DRIVER}> hello"

    def test_format_message_empty_string(self):
        """format_message with an empty string should still include the role ping."""
        service = DriverService()
        result = service.format_message("")
        assert f"<@&{RoleIds.DRIVER}>" in result

    def test_format_message_returns_string(self):
        """Return type should always be a str."""
        service = DriverService()
        result = service.format_message("test")
        assert isinstance(result, str)
