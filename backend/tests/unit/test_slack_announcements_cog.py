"""Unit tests for the SlackAnnouncements cog."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.core.bot_context import current_bot_var
from shared.core.enums import BotName, ChannelIds
from stonesbot.cogs.slack_announcements import SlackAnnouncements

MODULE = "stonesbot.cogs.slack_announcements"

SLACK_ENV = {
    "SLACK_BOT_TOKEN": "xoxb-1",
    "SLACK_APP_TOKEN": "xapp-1",
    "SLACK_ANNOUNCEMENTS_CHANNEL_ID": "C_ANNOUNCE",
}


@pytest.mark.asyncio
async def test_cog_load_without_env_does_nothing(monkeypatch):
    for name in SLACK_ENV:
        monkeypatch.delenv(name, raising=False)
    cog = SlackAnnouncements(MagicMock())

    await cog.cog_load()
    await cog.on_ready()

    assert cog.socket_client is None
    assert cog.service is None


@pytest.mark.asyncio
async def test_cog_load_with_env_builds_clients_for_resolved_channel(monkeypatch):
    for name, value in SLACK_ENV.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("APP_ENV", "local")
    cog = SlackAnnouncements(MagicMock())

    with patch(f"{MODULE}.SocketModeClient") as client_cls:
        await cog.cog_load()

    client_cls.assert_called_once()
    assert client_cls.call_args.kwargs["app_token"] == "xapp-1"
    assert cog.service is not None
    assert cog.service.slack_channel_id == "C_ANNOUNCE"
    # Locally every outbound message is routed to the bots channel.
    assert cog.service.discord_channel_id == ChannelIds.BOT_STUFF__BOTS


def _slack_error(code: str):
    from slack_sdk.errors import SlackApiError

    return SlackApiError(code, {"ok": False, "error": code})


def _connectable_cog():
    cog = SlackAnnouncements(MagicMock())
    cog.socket_client = MagicMock()
    cog.socket_client.issue_new_wss_url = AsyncMock(return_value="wss://slack")
    cog.socket_client.connect = AsyncMock()
    cog.service = MagicMock()
    cog.service.slack.auth_test = AsyncMock(return_value={"ok": True})
    return cog


@pytest.fixture
def send_error():
    with patch(f"{MODULE}.send_error_to_discord", AsyncMock()) as mock:
        yield mock


@pytest.fixture
def no_sleep():
    with patch(f"{MODULE}.asyncio.sleep", AsyncMock()) as mock:
        yield mock


@pytest.mark.asyncio
async def test_on_ready_starts_connecting_once():
    cog = _connectable_cog()

    await cog.on_ready()
    await cog.on_ready()
    assert cog._connect_task is not None
    await cog._connect_task

    cog.socket_client.connect.assert_awaited_once()
    assert cog.socket_client.wss_uri == "wss://slack"


@pytest.mark.asyncio
async def test_bad_app_token_is_reported_once_and_not_retried(send_error, no_sleep):
    cog = _connectable_cog()
    cog.socket_client.issue_new_wss_url.side_effect = _slack_error("invalid_auth")

    await cog._connect()

    cog.socket_client.issue_new_wss_url.assert_awaited_once()
    cog.socket_client.connect.assert_not_awaited()
    send_error.assert_awaited_once()
    assert "SLACK_APP_TOKEN" in send_error.await_args.args[0]
    no_sleep.assert_not_awaited()


@pytest.mark.asyncio
async def test_transient_failures_back_off_and_report_once(send_error, no_sleep):
    cog = _connectable_cog()
    cog.socket_client.issue_new_wss_url.side_effect = [
        ConnectionError(),
        TimeoutError(),
        _slack_error("internal_error"),
        "wss://slack",
    ]

    await cog._connect()

    cog.socket_client.connect.assert_awaited_once()
    send_error.assert_awaited_once()
    assert [c.args[0] for c in no_sleep.await_args_list] == [30, 60, 120]


@pytest.mark.asyncio
async def test_backoff_is_capped(no_sleep, send_error):
    cog = _connectable_cog()
    cog.socket_client.issue_new_wss_url.side_effect = [ConnectionError()] * 8 + ["wss://slack"]

    await cog._connect()

    assert max(c.args[0] for c in no_sleep.await_args_list) == 15 * 60


@pytest.mark.asyncio
async def test_bad_bot_token_is_reported_but_still_connects(send_error):
    cog = _connectable_cog()
    cog.service.slack.auth_test.side_effect = _slack_error("token_revoked")

    await cog._connect()

    send_error.assert_awaited_once()
    assert "SLACK_BOT_TOKEN" in send_error.await_args.args[0]
    cog.socket_client.connect.assert_awaited_once()


@pytest.mark.asyncio
async def test_unverifiable_bot_token_is_not_reported(send_error):
    cog = _connectable_cog()
    cog.service.slack.auth_test.side_effect = TimeoutError()

    await cog._connect()

    send_error.assert_not_awaited()
    cog.socket_client.connect.assert_awaited_once()


@pytest.mark.asyncio
async def test_cog_unload_cancels_pending_connect():
    cog = _connectable_cog()
    cog.socket_client.close = AsyncMock()
    task = MagicMock()
    cog._connect_task = task

    await cog.cog_unload()

    task.cancel.assert_called_once()
    cog.socket_client.close.assert_awaited_once()


def _request(type_="events_api", event=None):
    request = MagicMock()
    request.type = type_
    request.envelope_id = "env-1"
    request.payload = {"event": event or {"type": "message"}}
    return request


@pytest.fixture
def flag_enabled():
    """Run as StonesBot with every feature flag reading as enabled."""
    token = current_bot_var.set(BotName.STONESBOT)
    with patch(
        "shared.utils.checks.FeatureFlagsRepository._cache",
        {"stonesbot": True, "slack_announcements_forwarding": True},
    ):
        yield
    current_bot_var.reset(token)


@pytest.mark.asyncio
async def test_request_is_acked_and_forwarded(flag_enabled):
    cog = SlackAnnouncements(MagicMock())
    cog.service = MagicMock()
    cog.service.handle_event = AsyncMock()
    client = MagicMock()
    client.send_socket_mode_response = AsyncMock()
    event = {"type": "message", "text": "hi"}

    await cog._on_request(client, _request(event=event))

    assert client.send_socket_mode_response.await_args.args[0].envelope_id == "env-1"
    cog.service.handle_event.assert_awaited_once_with(event)


@pytest.mark.asyncio
async def test_non_event_requests_are_acked_but_not_forwarded(flag_enabled):
    cog = SlackAnnouncements(MagicMock())
    cog.service = MagicMock()
    cog.service.handle_event = AsyncMock()
    client = MagicMock()
    client.send_socket_mode_response = AsyncMock()

    await cog._on_request(client, _request(type_="slash_commands"))

    client.send_socket_mode_response.assert_awaited_once()
    cog.service.handle_event.assert_not_awaited()


@pytest.mark.asyncio
async def test_disabled_flag_blocks_forwarding():
    token = current_bot_var.set(BotName.STONESBOT)
    cog = SlackAnnouncements(MagicMock())
    cog.service = MagicMock()
    cog.service.handle_event = AsyncMock()
    client = MagicMock()
    client.send_socket_mode_response = AsyncMock()

    try:
        with patch(
            "shared.utils.checks.FeatureFlagsRepository._cache",
            {"stonesbot": True, "slack_announcements_forwarding": False},
        ):
            await cog._on_request(client, _request())
    finally:
        current_bot_var.reset(token)

    client.send_socket_mode_response.assert_awaited_once()
    cog.service.handle_event.assert_not_awaited()
