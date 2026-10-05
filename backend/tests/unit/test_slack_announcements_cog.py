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


@pytest.mark.asyncio
async def test_on_ready_connects_once():
    cog = SlackAnnouncements(MagicMock())
    cog.socket_client = MagicMock()
    cog.socket_client.is_connected = AsyncMock(side_effect=[False, True])
    cog.socket_client.connect = AsyncMock()

    await cog.on_ready()
    await cog.on_ready()

    cog.socket_client.connect.assert_awaited_once()


@pytest.mark.asyncio
async def test_on_ready_reports_connect_failure():
    cog = SlackAnnouncements(MagicMock())
    cog.socket_client = MagicMock()
    cog.socket_client.is_connected = AsyncMock(return_value=False)
    cog.socket_client.connect = AsyncMock(side_effect=RuntimeError("bad token"))

    with patch(f"{MODULE}.send_error_to_discord", AsyncMock()) as send_error:
        await cog.on_ready()

    send_error.assert_awaited_once()


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
