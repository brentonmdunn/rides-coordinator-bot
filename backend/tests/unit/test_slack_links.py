"""Unit tests for Slack message link parsing."""

import pytest

from stonesbot.utils.slack_links import SlackMessageLink, parse_message_link


def test_parses_copied_link():
    link = parse_message_link("https://church.slack.com/archives/C0C6YVAMCV8/p1791253088119709")
    assert link == SlackMessageLink(
        channel_id="C0C6YVAMCV8", ts="1791253088.119709", thread_ts=None
    )
    assert not link.is_thread_reply


def test_parses_thread_reply_link():
    link = parse_message_link(
        "https://church.slack.com/archives/C0C6YVAMCV8/p1791253099000200"
        "?thread_ts=1791253088.119709&cid=C0C6YVAMCV8"
    )
    assert link is not None
    assert link.ts == "1791253099.000200"
    assert link.thread_ts == "1791253088.119709"
    assert link.is_thread_reply


def test_thread_parent_link_is_not_a_reply():
    link = parse_message_link(
        "https://church.slack.com/archives/C1/p1791253088119709?thread_ts=1791253088.119709"
    )
    assert link is not None
    assert not link.is_thread_reply


@pytest.mark.parametrize(
    "url",
    [
        "  <https://church.slack.com/archives/C1/p1791253088119709>  ",
        "https://app.slack.com/archives/C1/p1791253088119709/",
        "http://church.slack.com/archives/C1/p1791253088119709",
    ],
)
def test_tolerates_wrapping_and_variants(url):
    link = parse_message_link(url)
    assert link is not None
    assert link.ts == "1791253088.119709"


@pytest.mark.parametrize(
    "url",
    [
        "",
        "not a link",
        "https://church.slack.com/archives/C1",
        "https://church.slack.com/archives/C1/1791253088119709",
        "https://church.slack.com/files/U1/F1/flyer.png",
        "https://evilslack.com/archives/C1/p1791253088119709",
        "https://slack.com.evil.io/archives/C1/p1791253088119709",
        "ftp://church.slack.com/archives/C1/p1791253088119709",
        "https://discord.com/channels/1/2/3",
    ],
)
def test_rejects_non_message_links(url):
    assert parse_message_link(url) is None
