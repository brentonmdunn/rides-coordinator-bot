import pytest

from bot.utils.parsing import column_letter_to_index


@pytest.mark.parametrize(
    "letter,expected",
    [
        ("A", 0),
        ("B", 1),
        ("Z", 25),
        ("AA", 26),
        ("AB", 27),
        ("AZ", 51),
        ("BA", 52),
        ("a", 0),
        ("ab", 27),
    ],
)
def test_column_letter_to_index(letter, expected):
    assert column_letter_to_index(letter) == expected
