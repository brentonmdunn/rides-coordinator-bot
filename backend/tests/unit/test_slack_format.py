"""Unit tests for the Slack-to-Discord formatter."""

import pytest

from stonesbot.utils.slack_format import extract_user_ids, slack_to_discord, split_message

# ---------------------------------------------------------------------------
# slack_to_discord
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("slack", "discord"),
    [
        ("*bold*", "**bold**"),
        ("~gone~", "~~gone~~"),
        ("_italic_", "_italic_"),
        ("say *two words* here", "say **two words** here"),
        ("> quoted", "> quoted"),
    ],
)
def test_converts_formatting(slack, discord):
    assert slack_to_discord(slack) == discord


@pytest.mark.parametrize(
    "text",
    ["2*3*4", "snake_case_name", "a * b * c", "**already**", "*unclosed"],
)
def test_leaves_non_markers_alone(text):
    assert slack_to_discord(text) == text


def test_skips_formatting_inside_code():
    text = "`*x*` and ```\n*y* ~z~\n```"
    assert slack_to_discord(text) == text


def test_converts_labeled_link():
    assert slack_to_discord("<https://a.com/x|the site>") == "[the site](https://a.com/x)"


def test_converts_bare_link():
    assert slack_to_discord("go to <https://a.com>") == "go to https://a.com"


def test_link_url_markers_are_not_formatted():
    assert slack_to_discord("<https://a.com/*b*|t>") == "[t](https://a.com/*b*)"


def test_bold_around_link():
    assert slack_to_discord("*see <https://a.com|here>*") == "**see [here](https://a.com)**"


def test_mailto_link_shows_address():
    assert slack_to_discord("<mailto:a@b.co|a@b.co>") == "a@b.co"


def test_user_mention_uses_resolved_name():
    assert slack_to_discord("hi <@U123>", {"U123": "Jane"}) == "hi @Jane"


def test_user_mention_falls_back_to_label_then_unknown():
    assert slack_to_discord("<@U1|bob> <@U2>") == "@bob @unknown"


def test_channel_mention():
    assert slack_to_discord("see <#C123|general>") == "see #general"


@pytest.mark.parametrize(
    ("slack", "discord"),
    [("<!channel>", "@channel"), ("<!here>", "@here"), ("<!everyone>", "@everyone")],
)
def test_special_mentions_become_plain_text(slack, discord):
    assert slack_to_discord(slack) == discord


def test_user_group_and_date_use_label():
    text = "<!subteam^S1|@leaders> on <!date^1700000000^{date}|Nov 14>"
    assert slack_to_discord(text) == "@leaders on Nov 14"


def test_unescapes_html_entities():
    assert slack_to_discord("a &amp; b &lt;3 &gt;") == "a & b <3 >"


def test_extract_user_ids():
    assert extract_user_ids("<@U1> <@W2|x> <#C3|c> <!here>") == {"U1", "W2"}


# ---------------------------------------------------------------------------
# split_message
# ---------------------------------------------------------------------------


def test_split_short_text_is_one_chunk():
    assert split_message("hello\nworld") == ["hello\nworld"]


def test_split_empty_text_is_no_chunks():
    assert split_message("  \n ") == []


def test_split_prefers_line_breaks():
    text = "a" * 15 + "\n" + "b" * 15
    assert split_message(text, limit=20) == ["a" * 15, "b" * 15]


def test_split_long_line_at_spaces():
    text = " ".join(["word"] * 10)
    chunks = split_message(text, limit=20)
    assert all(len(c) <= 20 for c in chunks)
    assert " ".join(chunks) == text


def test_split_hard_cuts_overlong_word():
    chunks = split_message("x" * 45, limit=20)
    assert chunks == ["x" * 20, "x" * 20, "x" * 5]


def test_split_never_exceeds_discord_limit():
    text = "\n".join(["line " * 50] * 30)
    assert all(len(c) <= 2000 for c in split_message(text))
