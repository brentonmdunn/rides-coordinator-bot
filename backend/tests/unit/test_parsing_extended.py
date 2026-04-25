"""Extended unit tests for bot.utils.parsing (beyond column_letter_to_index)."""

from datetime import time
from unittest.mock import MagicMock

import pytest

from bot.utils.parsing import (
    get_first_name,
    get_last_name,
    get_message_and_embed_content,
    parse_discord_username,
    parse_name,
    parse_time,
)


# ---------------------------------------------------------------------------
# parse_name
# ---------------------------------------------------------------------------
class TestParseName:
    """Tests for parse_name."""

    def test_name_with_username(self):
        name, username = parse_name("Alice (alice123)")
        assert name == "Alice"
        assert username == "alice123"

    def test_name_without_username(self):
        name, username = parse_name("Alice")
        assert name == "Alice"
        assert username is None

    def test_full_name_with_username(self):
        name, username = parse_name("Alice Smith (asmith)")
        assert name == "Alice Smith"
        assert username == "asmith"

    def test_empty_string(self):
        name, username = parse_name("")
        assert name == ""
        assert username is None

    def test_name_with_spaces_before_parens(self):
        name, username = parse_name("Alice   (alice)")
        assert name == "Alice"
        assert username == "alice"

    def test_nested_parens(self):
        _name, username = parse_name("Alice (a(b))")
        # regex is non-greedy, so it captures up to the last close paren
        assert username is not None


# ---------------------------------------------------------------------------
# parse_discord_username
# ---------------------------------------------------------------------------
class TestParseDiscordUsername:
    """Tests for parse_discord_username."""

    def test_with_at(self):
        assert parse_discord_username("@alice") == "alice"

    def test_without_at(self):
        assert parse_discord_username("alice") == "alice"

    def test_uppercase(self):
        assert parse_discord_username("Alice") == "alice"

    def test_with_spaces(self):
        assert parse_discord_username("  @Alice  ") == "alice"

    def test_empty_string(self):
        assert parse_discord_username("") == ""

    def test_multiple_at(self):
        result = parse_discord_username("@@alice")
        assert result == "@alice"


# ---------------------------------------------------------------------------
# get_first_name / get_last_name
# ---------------------------------------------------------------------------
class TestGetFirstName:
    """Tests for get_first_name."""

    def test_single_name(self):
        assert get_first_name("Alice") == "Alice"

    def test_full_name(self):
        assert get_first_name("Alice Smith") == "Alice"

    def test_three_names(self):
        assert get_first_name("Alice B Smith") == "Alice"


class TestGetLastName:
    """Tests for get_last_name."""

    def test_single_name(self):
        assert get_last_name("Alice") is None

    def test_two_names(self):
        assert get_last_name("Alice Smith") == "Smith"

    def test_three_names(self):
        assert get_last_name("Alice B Smith") == "B Smith"


# ---------------------------------------------------------------------------
# parse_time
# ---------------------------------------------------------------------------
class TestParseTime:
    """Tests for parse_time."""

    def test_24_hour_with_colon(self):
        assert parse_time("14:30") == time(14, 30)

    def test_24_hour_no_colon(self):
        assert parse_time("14") == time(14, 0)

    def test_12_hour_am(self):
        assert parse_time("9am") == time(9, 0)

    def test_12_hour_pm(self):
        assert parse_time("1:30pm") == time(13, 30)

    def test_shorthand_a(self):
        assert parse_time("9a") == time(9, 0)

    def test_shorthand_p(self):
        assert parse_time("10p") == time(22, 0)

    def test_with_spaces(self):
        assert parse_time(" 1 : 30 P ") == time(13, 30)

    def test_midnight(self):
        assert parse_time("0:00") == time(0, 0)

    def test_noon_12pm(self):
        assert parse_time("12pm") == time(12, 0)

    def test_12am(self):
        assert parse_time("12am") == time(0, 0)

    def test_invalid_string_raises(self):
        with pytest.raises(ValueError, match="Could not parse"):
            parse_time("not a time")

    def test_uppercase_am(self):
        assert parse_time("9AM") == time(9, 0)

    def test_uppercase_pm(self):
        assert parse_time("1:30PM") == time(13, 30)

    def test_just_hour_24(self):
        assert parse_time("7") == time(7, 0)

    def test_just_hour_with_am(self):
        assert parse_time("7am") == time(7, 0)


# ---------------------------------------------------------------------------
# get_message_and_embed_content
# ---------------------------------------------------------------------------
class TestGetMessageAndEmbedContent:
    """Tests for get_message_and_embed_content."""

    def _make_message(self, content="", embeds=None):
        msg = MagicMock()
        msg.content = content
        msg.embeds = embeds or []
        return msg

    def _make_embed(self, title=None, description=None, fields=None):
        embed = MagicMock()
        embed.title = title
        embed.description = description
        embed.fields = fields or []
        return embed

    def _make_field(self, name, value):
        field = MagicMock()
        field.name = name
        field.value = value
        return field

    def test_content_only(self):
        msg = self._make_message(content="Hello World")
        result = get_message_and_embed_content(msg)
        assert "hello world" in result

    def test_embed_only(self):
        embed = self._make_embed(title="My Title", description="My Desc")
        msg = self._make_message(embeds=[embed])
        result = get_message_and_embed_content(msg)
        assert "my title" in result
        assert "my desc" in result

    def test_embed_with_fields(self):
        field = self._make_field("Field Name", "Field Value")
        embed = self._make_embed(fields=[field])
        msg = self._make_message(embeds=[embed])
        result = get_message_and_embed_content(msg)
        assert "field name" in result
        assert "field value" in result

    def test_content_and_embed(self):
        embed = self._make_embed(title="Embed")
        msg = self._make_message(content="Content", embeds=[embed])
        result = get_message_and_embed_content(msg)
        assert "content" in result
        assert "embed" in result

    def test_no_content_flag(self):
        msg = self._make_message(content="Hidden")
        result = get_message_and_embed_content(msg, message_content=False)
        assert "hidden" not in result

    def test_no_embed_flag(self):
        embed = self._make_embed(title="Hidden Embed")
        msg = self._make_message(content="Visible", embeds=[embed])
        result = get_message_and_embed_content(msg, embed_content=False)
        assert "visible" in result
        assert "hidden embed" not in result

    def test_empty_message(self):
        msg = self._make_message()
        result = get_message_and_embed_content(msg)
        assert result == ""
