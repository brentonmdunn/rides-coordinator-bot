"""Unit tests for bot.core.enums — ensure enum values are consistent and complete."""

from enum import IntEnum, StrEnum

from bot.core.enums import (
    AccountRoles,
    CacheNamespace,
    CampusLivingLocations,
    ChannelIds,
    DaysOfWeek,
    DaysOfWeekNumber,
    FeatureFlagNames,
    JobName,
    PickupLocations,
    ReactionAction,
    RideOption,
    RoleIds,
)


class TestDaysOfWeek:
    """Tests for DaysOfWeek enum."""

    def test_has_seven_days(self):
        assert len(DaysOfWeek) == 7

    def test_is_str_enum(self):
        assert issubclass(DaysOfWeek, StrEnum)

    def test_capitalized_values(self):
        for day in DaysOfWeek:
            assert day.value[0].isupper()

    def test_specific_values(self):
        assert DaysOfWeek.MONDAY == "Monday"
        assert DaysOfWeek.SUNDAY == "Sunday"


class TestDaysOfWeekNumber:
    """Tests for DaysOfWeekNumber enum."""

    def test_has_seven_days(self):
        assert len(DaysOfWeekNumber) == 7

    def test_is_int_enum(self):
        assert issubclass(DaysOfWeekNumber, IntEnum)

    def test_monday_is_zero(self):
        assert DaysOfWeekNumber.MONDAY == 0

    def test_sunday_is_six(self):
        assert DaysOfWeekNumber.SUNDAY == 6

    def test_consecutive(self):
        values = [d.value for d in DaysOfWeekNumber]
        assert values == list(range(7))


class TestDaysOfWeekConsistency:
    """Verify DaysOfWeek and DaysOfWeekNumber have the same members."""

    def test_same_member_names(self):
        str_names = {d.name for d in DaysOfWeek}
        num_names = {d.name for d in DaysOfWeekNumber}
        assert str_names == num_names


class TestChannelIds:
    """Tests for ChannelIds enum."""

    def test_is_int_enum(self):
        assert issubclass(ChannelIds, IntEnum)

    def test_all_positive(self):
        for ch in ChannelIds:
            assert ch.value > 0

    def test_no_duplicates(self):
        values = [ch.value for ch in ChannelIds]
        assert len(values) == len(set(values))


class TestRoleIds:
    """Tests for RoleIds enum."""

    def test_has_driver(self):
        assert hasattr(RoleIds, "DRIVER")

    def test_has_rides(self):
        assert hasattr(RoleIds, "RIDES")

    def test_all_positive(self):
        for r in RoleIds:
            assert r.value > 0


class TestPickupLocations:
    """Tests for PickupLocations enum."""

    def test_is_str_enum(self):
        assert issubclass(PickupLocations, StrEnum)

    def test_revelle_same_as_eighth(self):
        assert PickupLocations.REVELLE == PickupLocations.EIGHTH

    def test_has_key_locations(self):
        expected = {"MUIR", "SIXTH", "MARSHALL", "ERC", "SEVENTH", "WARREN_EQL", "RITA"}
        actual = {loc.name for loc in PickupLocations}
        assert expected.issubset(actual)


class TestCampusLivingLocations:
    """Tests for CampusLivingLocations enum."""

    def test_is_str_enum(self):
        assert issubclass(CampusLivingLocations, StrEnum)

    def test_has_key_colleges(self):
        expected = {"SEVENTH", "ERC", "MARSHALL", "SIXTH", "MUIR", "WARREN", "REVELLE"}
        actual = {loc.name for loc in CampusLivingLocations}
        assert expected.issubset(actual)


class TestReactionAction:
    """Tests for ReactionAction enum."""

    def test_add_value(self):
        assert ReactionAction.ADD == "add"

    def test_remove_value(self):
        assert ReactionAction.REMOVE == "remove"

    def test_only_two_members(self):
        assert len(ReactionAction) == 2


class TestJobName:
    """Tests for JobName enum."""

    def test_values(self):
        assert JobName.FRIDAY == "friday"
        assert JobName.SUNDAY == "sunday"
        assert JobName.SUNDAY_CLASS == "sunday_class"


class TestFeatureFlagNames:
    """Tests for FeatureFlagNames enum."""

    def test_is_str_enum(self):
        assert issubclass(FeatureFlagNames, StrEnum)

    def test_has_bot_flag(self):
        assert FeatureFlagNames.BOT == "bot"

    def test_no_duplicate_values(self):
        values = [f.value for f in FeatureFlagNames]
        assert len(values) == len(set(values))


class TestCacheNamespace:
    """Tests for CacheNamespace enum."""

    def test_has_default(self):
        assert CacheNamespace.DEFAULT == "default"

    def test_no_duplicate_values(self):
        values = [c.value for c in CacheNamespace]
        assert len(values) == len(set(values))


class TestRideOption:
    """Tests for RideOption enum."""

    def test_has_friday(self):
        assert RideOption.FRIDAY == "Friday"

    def test_has_sunday_options(self):
        assert hasattr(RideOption, "SUNDAY_PICKUP")
        assert hasattr(RideOption, "SUNDAY_DROPOFF_BACK")
        assert hasattr(RideOption, "SUNDAY_DROPOFF_LUNCH")


class TestAccountRoles:
    """Tests for AccountRoles enum."""

    def test_admin(self):
        assert AccountRoles.ADMIN == "admin"

    def test_viewer(self):
        assert AccountRoles.VIEWER == "viewer"
