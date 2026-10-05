"""Unit tests for SlackForwardService."""

from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from stonesbot.services.slack_forward_service import (
    WEBHOOK_NAME,
    SlackAuthor,
    SlackForwardService,
    is_thread_reply,
    plan_files,
    webhook_username,
)

MODULE = "stonesbot.services.slack_forward_service"
SLACK_CHANNEL = "C_ANNOUNCE"
DISCORD_CHANNEL = 999
BOT_USER_ID = 42
SIZE_LIMIT = 10 * 1024 * 1024


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row(message_id: int, part: int = 0) -> MagicMock:
    row = MagicMock()
    row.discord_message_id = str(message_id)
    row.part = part
    return row


def _http_error(cls=discord.HTTPException, status: int = 500):
    response = MagicMock()
    response.status = status
    return cls(response, "error")


def _make_webhook() -> MagicMock:
    webhook = MagicMock(spec=discord.Webhook)
    webhook.name = WEBHOOK_NAME
    webhook.token = "token"
    webhook.user = MagicMock(id=BOT_USER_ID)
    ids = iter(range(1000, 2000))
    webhook.send = AsyncMock(side_effect=lambda **_: MagicMock(id=next(ids)))
    webhook.edit_message = AsyncMock()
    webhook.delete_message = AsyncMock()
    return webhook


def _make_service(webhook=None, existing_hooks=None):
    webhook = webhook or _make_webhook()
    channel = MagicMock(spec=discord.TextChannel)
    channel.id = DISCORD_CHANNEL
    channel.guild = MagicMock(filesize_limit=SIZE_LIMIT)
    channel.webhooks = AsyncMock(
        return_value=[webhook] if existing_hooks is None else existing_hooks
    )
    channel.create_webhook = AsyncMock(return_value=webhook)

    bot = MagicMock()
    bot.get_channel.return_value = channel
    bot.user = MagicMock(id=BOT_USER_ID)

    slack = MagicMock()
    slack.users_info = AsyncMock(
        return_value={
            "user": {
                "name": "jdoe",
                "profile": {"display_name": "Jane", "image_192": "https://img/jane.png"},
            }
        }
    )
    slack.files_info = AsyncMock()

    service = SlackForwardService(bot, slack, "xoxb-token", SLACK_CHANNEL, DISCORD_CHANNEL)
    return service, webhook, channel


@pytest.fixture
def repo():
    """Patch the session factory and repository; get_parts returns [] by default."""
    session = MagicMock()
    session.commit = AsyncMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    with (
        patch(f"{MODULE}.AsyncSessionLocal", return_value=ctx),
        patch(f"{MODULE}.SlackForwardedMessageRepository") as repository,
    ):
        repository.get_parts = AsyncMock(return_value=[])
        repository.add = AsyncMock()
        repository.delete_parts = AsyncMock()
        yield repository


@pytest.fixture(autouse=True)
def send_error():
    with patch(f"{MODULE}.send_error_to_discord", AsyncMock()) as mock:
        yield mock


def _message(text="hello", ts="1.0", **extra):
    return {
        "type": "message",
        "channel": SLACK_CHANNEL,
        "user": "U1",
        "text": text,
        "ts": ts,
        **extra,
    }


def _saved_parts(repo) -> list[tuple[int, str]]:
    return [(c.kwargs["part"], c.kwargs["discord_message_id"]) for c in repo.add.await_args_list]


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def test_is_thread_reply():
    assert is_thread_reply({"ts": "2", "thread_ts": "1"})
    assert not is_thread_reply({"ts": "1", "thread_ts": "1"})
    assert not is_thread_reply({"ts": "1"})
    assert not is_thread_reply({"ts": "2", "thread_ts": "1", "subtype": "thread_broadcast"})


def test_webhook_username():
    assert webhook_username(SlackAuthor("Jane", None)) == "Jane (via Slack)"
    assert webhook_username(SlackAuthor("My Discord Guy", None)) == "Slack announcement"
    assert len(webhook_username(SlackAuthor("x" * 200, None))) == 80


def test_plan_files_attaches_small_and_notes_the_rest():
    files = [
        {"id": "F1", "name": "small.png", "size": 100},
        {"id": "F2", "name": "huge.mov", "size": SIZE_LIMIT + 1},
        {"id": "F3", "name": "doc", "mode": "external", "url_private": "https://drive/x"},
        {"id": "F4", "mode": "tombstone"},
    ]
    plan = plan_files(files, SIZE_LIMIT)
    assert [f["id"] for f in plan.attach] == ["F1"]
    assert plan.notes == [
        "📎 huge.mov (too large to attach here, see Slack)",
        "📎 [doc](https://drive/x)",
    ]


def test_plan_files_caps_at_ten_attachments():
    files = [{"id": f"F{i}", "name": f"{i}.png", "size": 1} for i in range(12)]
    plan = plan_files(files, SIZE_LIMIT)
    assert len(plan.attach) == 10
    assert len(plan.notes) == 2


# ---------------------------------------------------------------------------
# New posts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_new_post_is_sent_as_author_and_recorded(repo):
    service, webhook, _ = _make_service()

    await service.handle_event(_message("*Service* moved <!channel>"))

    webhook.send.assert_awaited_once()
    kwargs = webhook.send.await_args.kwargs
    assert kwargs["content"] == "**Service** moved @channel"
    assert kwargs["username"] == "Jane (via Slack)"
    assert kwargs["avatar_url"] == "https://img/jane.png"
    assert kwargs["allowed_mentions"].everyone is False
    assert kwargs["allowed_mentions"].users is False
    assert kwargs["allowed_mentions"].roles is False
    assert kwargs["wait"] is True
    assert _saved_parts(repo) == [(0, "1000")]


@pytest.mark.asyncio
async def test_events_from_other_channels_are_ignored(repo):
    service, webhook, _ = _make_service()

    await service.handle_event({**_message(), "channel": "C_OTHER"})

    webhook.send.assert_not_awaited()


@pytest.mark.asyncio
async def test_thread_replies_are_ignored(repo):
    service, webhook, _ = _make_service()

    await service.handle_event(_message(ts="2.0", thread_ts="1.0"))

    webhook.send.assert_not_awaited()


@pytest.mark.asyncio
async def test_thread_broadcasts_are_forwarded(repo):
    service, webhook, _ = _make_service()

    await service.handle_event(_message(ts="2.0", thread_ts="1.0", subtype="thread_broadcast"))

    webhook.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_other_subtypes_are_ignored(repo):
    service, webhook, _ = _make_service()

    await service.handle_event(_message(subtype="channel_join"))

    webhook.send.assert_not_awaited()


@pytest.mark.asyncio
async def test_already_forwarded_message_is_skipped(repo):
    service, webhook, _ = _make_service()
    repo.get_parts.return_value = [_row(5)]

    await service.handle_event(_message())

    webhook.send.assert_not_awaited()


@pytest.mark.asyncio
async def test_long_post_is_split_into_parts(repo):
    service, webhook, _ = _make_service()
    text = ("a" * 1500 + "\n") * 2

    await service.handle_event(_message(text))

    assert webhook.send.await_count == 2
    assert _saved_parts(repo) == [(0, "1000"), (1, "1001")]


@pytest.mark.asyncio
async def test_mentions_are_resolved_to_names(repo):
    service, webhook, _ = _make_service()

    await service.handle_event(_message("thanks <@U9>!"))

    assert webhook.send.await_args.kwargs["content"] == "thanks @Jane!"
    service.slack.users_info.assert_any_await(user="U9")


@pytest.mark.asyncio
async def test_author_lookup_failure_falls_back(repo):
    from slack_sdk.errors import SlackApiError

    service, webhook, _ = _make_service()
    service.slack.users_info.side_effect = SlackApiError("nope", MagicMock())

    await service.handle_event(_message())

    assert webhook.send.await_args.kwargs["username"] == "Slack (via Slack)"


@pytest.mark.asyncio
async def test_attachments_go_on_last_part_with_notes_for_skipped(repo):
    service, webhook, _ = _make_service()
    attachment = MagicMock(spec=discord.File)
    files = [
        {"id": "F1", "name": "flyer.png", "size": 100, "url_private_download": "https://f/1"},
        {"id": "F2", "name": "video.mov", "size": SIZE_LIMIT + 1},
    ]

    with patch.object(service, "_download_files", AsyncMock(return_value=[attachment])) as dl:
        await service.handle_event(_message("See flyer", subtype="file_share", files=files))

    assert [f["id"] for f in dl.await_args.args[0]] == ["F1"]
    kwargs = webhook.send.await_args.kwargs
    assert kwargs["files"] == [attachment]
    assert kwargs["content"] == "See flyer\n📎 video.mov (too large to attach here, see Slack)"


@pytest.mark.asyncio
async def test_file_only_post_sends_without_content(repo):
    service, webhook, _ = _make_service()
    attachment = MagicMock(spec=discord.File)
    files = [{"id": "F1", "name": "a.png", "size": 1, "url_private_download": "https://f/1"}]

    with patch.object(service, "_download_files", AsyncMock(return_value=[attachment])):
        await service.handle_event(_message("", subtype="file_share", files=files))

    kwargs = webhook.send.await_args.kwargs
    assert "content" not in kwargs
    assert kwargs["files"] == [attachment]


@pytest.mark.asyncio
async def test_rejected_attachments_are_retried_as_notes(repo):
    service, webhook, _ = _make_service()
    files = [{"id": "F1", "name": "big.pdf", "size": 100, "url_private_download": "https://f/1"}]
    sent = MagicMock(id=7)
    webhook.send.side_effect = [_http_error(status=413), sent]

    with patch.object(service, "_download_files", AsyncMock(return_value=[MagicMock()])):
        await service.handle_event(_message("Info", subtype="file_share", files=files))

    retry = webhook.send.await_args_list[1].kwargs
    assert "files" not in retry
    assert retry["content"] == "Info\n📎 big.pdf (too large to attach here, see Slack)"
    assert _saved_parts(repo) == [(0, "7")]


@pytest.mark.asyncio
async def test_partial_send_failure_cleans_up_and_reports(repo, send_error):
    service, webhook, _ = _make_service()
    webhook.send.side_effect = [MagicMock(id=1), _http_error()]

    await service.handle_event(_message(("a" * 1500 + "\n") * 2))

    webhook.delete_message.assert_awaited_once_with(1)
    repo.add.assert_not_awaited()
    send_error.assert_awaited_once()


# ---------------------------------------------------------------------------
# Webhook
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_existing_webhook_is_reused(repo):
    service, _, channel = _make_service()

    await service.handle_event(_message(ts="1"))
    await service.handle_event(_message(ts="2"))

    channel.webhooks.assert_awaited_once()
    channel.create_webhook.assert_not_awaited()


@pytest.mark.asyncio
async def test_webhook_is_created_when_missing(repo):
    stranger = MagicMock(spec=discord.Webhook)
    stranger.name = WEBHOOK_NAME
    stranger.token = "t"
    stranger.user = MagicMock(id=7)
    service, webhook, channel = _make_service(existing_hooks=[stranger])

    await service.handle_event(_message())

    channel.create_webhook.assert_awaited_once()
    webhook.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_missing_manage_webhooks_is_reported(repo, send_error):
    service, webhook, channel = _make_service()
    channel.webhooks.side_effect = _http_error(discord.Forbidden, 403)

    await service.handle_event(_message())

    webhook.send.assert_not_awaited()
    send_error.assert_awaited_once()
    assert "Manage Webhooks" in send_error.await_args.args[0]


# ---------------------------------------------------------------------------
# Edits
# ---------------------------------------------------------------------------


def _edit(text, previous_text="old", ts="1.0", files=None, previous_files=None, **message_extra):
    return {
        "type": "message",
        "subtype": "message_changed",
        "channel": SLACK_CHANNEL,
        "message": {"user": "U1", "text": text, "ts": ts, "files": files, **message_extra},
        "previous_message": {"text": previous_text, "ts": ts, "files": previous_files},
    }


@pytest.mark.asyncio
async def test_edit_updates_message_in_place(repo):
    service, webhook, _ = _make_service()
    repo.get_parts.return_value = [_row(55)]

    await service.handle_event(_edit("*new* text"))

    webhook.edit_message.assert_awaited_once()
    assert webhook.edit_message.await_args.args == (55,)
    assert webhook.edit_message.await_args.kwargs["content"] == "**new** text"
    webhook.send.assert_not_awaited()


@pytest.mark.asyncio
async def test_edit_without_text_change_is_ignored(repo):
    service, webhook, _ = _make_service()
    repo.get_parts.return_value = [_row(55)]

    await service.handle_event(_edit("same", previous_text="same"))

    webhook.edit_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_edit_of_unforwarded_message_is_ignored(repo):
    service, webhook, _ = _make_service()

    await service.handle_event(_edit("new"))

    webhook.edit_message.assert_not_awaited()
    webhook.send.assert_not_awaited()


@pytest.mark.asyncio
async def test_edit_that_changes_part_count_reposts(repo):
    service, webhook, _ = _make_service()
    repo.get_parts.return_value = [_row(55)]

    await service.handle_event(_edit(("a" * 1500 + "\n") * 2))

    assert webhook.send.await_count == 2
    webhook.delete_message.assert_awaited_once_with(55)
    repo.delete_parts.assert_awaited_once()
    assert _saved_parts(repo) == [(0, "1000"), (1, "1001")]


@pytest.mark.asyncio
async def test_edit_that_changes_files_reposts(repo):
    service, webhook, _ = _make_service()
    repo.get_parts.return_value = [_row(55)]
    files = [{"id": "F1", "name": "a.png", "size": 1}]
    previous_files = [*files, {"id": "F2", "name": "b.png", "size": 1}]

    with patch.object(service, "_download_files", AsyncMock(return_value=[MagicMock()])):
        await service.handle_event(_edit("t", "t", files=files, previous_files=previous_files))

    webhook.send.assert_awaited_once()
    webhook.delete_message.assert_awaited_once_with(55)
    webhook.edit_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_tombstone_edit_deletes(repo):
    service, webhook, _ = _make_service()
    repo.get_parts.return_value = [_row(55)]

    await service.handle_event(_edit("This message was deleted.", subtype="tombstone"))

    webhook.delete_message.assert_awaited_once_with(55)
    repo.delete_parts.assert_awaited_once()


# ---------------------------------------------------------------------------
# Deletes
# ---------------------------------------------------------------------------


def _delete(ts="1.0"):
    return {
        "type": "message",
        "subtype": "message_deleted",
        "channel": SLACK_CHANNEL,
        "deleted_ts": ts,
    }


@pytest.mark.asyncio
async def test_delete_removes_every_part(repo):
    service, webhook, _ = _make_service()
    repo.get_parts.return_value = [_row(55, 0), _row(56, 1)]

    await service.handle_event(_delete())

    assert [c.args[0] for c in webhook.delete_message.await_args_list] == [55, 56]
    repo.delete_parts.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_tolerates_already_deleted_discord_message(repo, send_error):
    service, webhook, _ = _make_service()
    repo.get_parts.return_value = [_row(55, 0), _row(56, 1)]
    webhook.delete_message.side_effect = [_http_error(discord.NotFound, 404), None]

    await service.handle_event(_delete())

    assert webhook.delete_message.await_count == 2
    repo.delete_parts.assert_awaited_once()
    send_error.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_of_unforwarded_message_is_ignored(repo):
    service, webhook, _ = _make_service()

    await service.handle_event(_delete())

    webhook.delete_message.assert_not_awaited()
    repo.delete_parts.assert_not_awaited()


# ---------------------------------------------------------------------------
# Downloads
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_download_rejects_slack_sign_in_page():
    service, _, _ = _make_service()
    response = MagicMock()
    response.headers = {"content-type": "text/html; charset=utf-8"}
    response.raise_for_status = MagicMock()
    client = MagicMock()
    client.get = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)

    with (
        patch(f"{MODULE}.httpx.AsyncClient", return_value=client),
        pytest.raises(RuntimeError, match="files:read"),
    ):
        await service._download_files(
            [{"id": "F1", "name": "a.png", "filetype": "png", "url_private_download": "u"}]
        )

    assert client.get.await_args.kwargs["headers"] == {"Authorization": "Bearer xoxb-token"}
