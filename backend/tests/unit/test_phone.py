"""Unit tests for ridebot.utils.phone: normalize_phone, format_phone, phone_status."""

from __future__ import annotations

import pytest

from ridebot.utils.phone import format_phone, normalize_phone, phone_status

VALID_INPUTS: tuple[str, ...] = (
    "8585551234",
    "858-555-1234",
    "(858) 555-1234",
    "858.555.1234",
    "858 555 1234",
    "+1 858 555 1234",
    "1-858-555-1234",
    "+18585551234",
)

INVALID_INPUTS: tuple[str, ...] = (
    "858555123",  # 9 digits
    "285855512345",  # 11 digits, not leading 1
    "858555123a",  # letters
    "call me maybe",  # letters, no digits
    "058-555-1234",  # area code starts with 0
    "158-555-1234",  # area code starts with 1
    "858-055-1234",  # exchange starts with 0
    "858-155-1234",  # exchange starts with 1
    "2-858-555-1234",  # bogus country-code-like prefix
    "",
    "   ",
)


# --- normalize_phone ---------------------------------------------------------


@pytest.mark.parametrize("raw", VALID_INPUTS)
def test_normalize_phone_valid_inputs_return_10_digits(raw: str) -> None:
    assert normalize_phone(raw) == "8585551234"


@pytest.mark.parametrize("raw", INVALID_INPUTS)
def test_normalize_phone_invalid_inputs_return_none(raw: str) -> None:
    assert normalize_phone(raw) is None


def test_normalize_phone_none_returns_none() -> None:
    assert normalize_phone(None) is None


def test_normalize_phone_strips_surrounding_whitespace() -> None:
    assert normalize_phone("  858-555-1234  ") == "8585551234"


def test_normalize_phone_too_long_returns_none() -> None:
    assert normalize_phone("8585551234" + "0" * 25) is None


# --- format_phone -------------------------------------------------------------


def test_format_phone_ten_digits_formats() -> None:
    assert format_phone("8585551234") == "(858) 555-1234"


def test_format_phone_none_returns_none() -> None:
    assert format_phone(None) is None


def test_format_phone_blank_returns_none() -> None:
    assert format_phone("   ") is None


def test_format_phone_non_digit_stored_value_returned_stripped() -> None:
    assert format_phone("  call me maybe  ") == "call me maybe"


def test_format_phone_wrong_length_digits_returned_as_is() -> None:
    assert format_phone("12345") == "12345"


# --- phone_status --------------------------------------------------------------


def test_phone_status_none_is_missing() -> None:
    assert phone_status(None) == "missing"


def test_phone_status_blank_is_missing() -> None:
    assert phone_status("   ") == "missing"


def test_phone_status_ten_digits_is_ok() -> None:
    assert phone_status("8585551234") == "ok"


def test_phone_status_anything_else_is_invalid() -> None:
    assert phone_status("call me maybe") == "invalid"
    assert phone_status("12345") == "invalid"
