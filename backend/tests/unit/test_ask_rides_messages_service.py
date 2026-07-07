"""Unit tests for AskRidesMessagesService."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import OperationalError

from bot.core.enums import AskRidesMessageType
from bot.services.ask_rides_messages_service import AskRidesMessagesService, EffectiveTemplate
from bot.utils.ask_rides_defaults import DEFAULT_TEMPLATES


def _mock_session_local(mock_session_local):
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session_local.return_value = mock_session
    return mock_session


class TestGetEffectiveTemplate:
    @pytest.mark.asyncio
    @patch(
        "bot.services.ask_rides_messages_service.AskRidesMessagesRepository.get",
        new_callable=AsyncMock,
    )
    @patch("bot.services.ask_rides_messages_service.AsyncSessionLocal")
    async def test_returns_default_when_row_missing(self, mock_session_local, mock_get):
        _mock_session_local(mock_session_local)
        mock_get.return_value = None

        result = await AskRidesMessagesService.get_effective_template(
            AskRidesMessageType.WEDNESDAY_FELLOWSHIP
        )

        default = DEFAULT_TEMPLATES[AskRidesMessageType.WEDNESDAY_FELLOWSHIP]
        assert result.title == default.title
        assert result.body == default.body
        assert result.color == default.color.value
        assert result.is_customized is False

    @pytest.mark.asyncio
    @patch(
        "bot.services.ask_rides_messages_service.AskRidesMessagesRepository.get",
        new_callable=AsyncMock,
    )
    @patch("bot.services.ask_rides_messages_service.AsyncSessionLocal")
    async def test_returns_db_row_when_present(self, mock_session_local, mock_get):
        _mock_session_local(mock_session_local)
        fake_row = MagicMock(title="Custom title", body="Custom body", color="red")
        mock_get.return_value = fake_row

        result = await AskRidesMessagesService.get_effective_template(
            AskRidesMessageType.WEDNESDAY_FELLOWSHIP
        )

        assert result == EffectiveTemplate(
            title="Custom title", body="Custom body", color="red", is_customized=True
        )

    @pytest.mark.asyncio
    @patch("bot.services.ask_rides_messages_service.AsyncSessionLocal")
    async def test_falls_back_to_default_on_operational_error(self, mock_session_local, caplog):
        mock_session_local.side_effect = OperationalError("stmt", {}, Exception("no such table"))

        result = await AskRidesMessagesService.get_effective_template(
            AskRidesMessageType.WEDNESDAY_FELLOWSHIP
        )

        default = DEFAULT_TEMPLATES[AskRidesMessageType.WEDNESDAY_FELLOWSHIP]
        assert result.title == default.title
        assert result.is_customized is False

    @pytest.mark.asyncio
    @patch("bot.services.ask_rides_messages_service.AsyncSessionLocal")
    async def test_never_raises_on_unexpected_error(self, mock_session_local):
        mock_session_local.side_effect = RuntimeError("boom")

        # Must not raise.
        result = await AskRidesMessagesService.get_effective_template(
            AskRidesMessageType.SUNDAY_SERVICE
        )

        default = DEFAULT_TEMPLATES[AskRidesMessageType.SUNDAY_SERVICE]
        assert result.title == default.title
        assert result.is_customized is False


class TestGetEffectiveTemplates:
    @pytest.mark.asyncio
    @patch(
        "bot.services.ask_rides_messages_service.AskRidesMessagesRepository.get_all",
        new_callable=AsyncMock,
    )
    @patch("bot.services.ask_rides_messages_service.AsyncSessionLocal")
    async def test_merges_db_rows_over_defaults(self, mock_session_local, mock_get_all):
        _mock_session_local(mock_session_local)
        fake_row = MagicMock(
            message_type=AskRidesMessageType.SUNDAY_CLASS.value,
            title="Custom class title",
            body="Custom class body",
            color="purple",
        )
        mock_get_all.return_value = [fake_row]

        result = await AskRidesMessagesService.get_effective_templates()

        assert result[AskRidesMessageType.SUNDAY_CLASS].title == "Custom class title"
        assert result[AskRidesMessageType.SUNDAY_CLASS].is_customized is True
        # Untouched types still fall back to defaults.
        assert result[AskRidesMessageType.FRIDAY_FELLOWSHIP].is_customized is False
        assert (
            result[AskRidesMessageType.FRIDAY_FELLOWSHIP].title
            == DEFAULT_TEMPLATES[AskRidesMessageType.FRIDAY_FELLOWSHIP].title
        )

    @pytest.mark.asyncio
    @patch("bot.services.ask_rides_messages_service.AsyncSessionLocal")
    async def test_falls_back_to_all_defaults_on_db_error(self, mock_session_local):
        mock_session_local.side_effect = OperationalError("stmt", {}, Exception("no such table"))

        result = await AskRidesMessagesService.get_effective_templates()

        assert len(result) == len(DEFAULT_TEMPLATES)
        assert all(not t.is_customized for t in result.values())


class TestValidate:
    def test_rejects_empty_title(self):
        with pytest.raises(ValueError, match="Title must not be empty"):
            AskRidesMessagesService._validate(
                AskRidesMessageType.WEDNESDAY_FELLOWSHIP, "", "body", "teal"
            )

    def test_rejects_empty_body(self):
        with pytest.raises(ValueError, match="Body must not be empty"):
            AskRidesMessagesService._validate(
                AskRidesMessageType.WEDNESDAY_FELLOWSHIP, "title", "", "teal"
            )

    def test_rejects_title_over_length_cap(self):
        with pytest.raises(ValueError, match="256"):
            AskRidesMessagesService._validate(
                AskRidesMessageType.WEDNESDAY_FELLOWSHIP, "x" * 257, "body", "teal"
            )

    def test_rejects_body_over_length_cap(self):
        with pytest.raises(ValueError, match="4096"):
            AskRidesMessagesService._validate(
                AskRidesMessageType.WEDNESDAY_FELLOWSHIP, "title", "x" * 4097, "teal"
            )

    def test_rejects_invalid_color(self):
        with pytest.raises(ValueError, match="Invalid color"):
            AskRidesMessagesService._validate(
                AskRidesMessageType.WEDNESDAY_FELLOWSHIP, "title", "body", "not-a-color"
            )

    def test_rejects_unknown_placeholder(self):
        with pytest.raises(ValueError, match="Unsupported placeholder"):
            AskRidesMessagesService._validate(
                AskRidesMessageType.WEDNESDAY_FELLOWSHIP,
                "title",
                "body with {ping}",
                "teal",
            )

    def test_accepts_allowed_placeholder(self):
        # Should not raise.
        AskRidesMessagesService._validate(
            AskRidesMessageType.SUNDAY_SERVICE,
            "title {date}",
            "body {date} {ping}",
            "blue",
        )

    def test_accepts_valid_template_with_no_placeholders(self):
        AskRidesMessagesService._validate(
            AskRidesMessageType.WEDNESDAY_FELLOWSHIP, "title", "body", "teal"
        )


class TestUpdateTemplate:
    @pytest.mark.asyncio
    @patch("bot.services.ask_rides_messages_service.publish", new_callable=AsyncMock)
    @patch(
        "bot.services.ask_rides_messages_service.AskRidesMessagesRepository.upsert",
        new_callable=AsyncMock,
    )
    @patch("bot.services.ask_rides_messages_service.AsyncSessionLocal")
    async def test_validates_then_upserts_and_publishes(
        self, mock_session_local, mock_upsert, mock_publish
    ):
        _mock_session_local(mock_session_local)
        mock_upsert.return_value = MagicMock(title="New title", body="New body", color="red")

        result = await AskRidesMessagesService.update_template(
            AskRidesMessageType.WEDNESDAY_FELLOWSHIP,
            "New title",
            "New body",
            "red",
            "editor@example.com",
        )

        assert result.title == "New title"
        assert result.is_customized is True
        mock_upsert.assert_awaited_once()
        mock_publish.assert_awaited_once_with(
            {"type": "templates_updated", "message_type": "wednesday_fellowship"}
        )

    @pytest.mark.asyncio
    @patch("bot.services.ask_rides_messages_service.publish", new_callable=AsyncMock)
    async def test_raises_on_invalid_input_without_touching_db(self, mock_publish):
        with pytest.raises(ValueError):
            await AskRidesMessagesService.update_template(
                AskRidesMessageType.WEDNESDAY_FELLOWSHIP,
                "",
                "body",
                "teal",
                "editor@example.com",
            )
        mock_publish.assert_not_awaited()


class TestResetTemplate:
    @pytest.mark.asyncio
    @patch("bot.services.ask_rides_messages_service.publish", new_callable=AsyncMock)
    @patch(
        "bot.services.ask_rides_messages_service.AskRidesMessagesRepository.delete",
        new_callable=AsyncMock,
    )
    @patch("bot.services.ask_rides_messages_service.AsyncSessionLocal")
    async def test_deletes_and_publishes(self, mock_session_local, mock_delete, mock_publish):
        _mock_session_local(mock_session_local)

        await AskRidesMessagesService.reset_template(AskRidesMessageType.SUNDAY_CLASS)

        mock_delete.assert_awaited_once()
        mock_publish.assert_awaited_once_with(
            {"type": "templates_updated", "message_type": "sunday_class"}
        )


class TestRender:
    def test_fills_date_token(self):
        template = EffectiveTemplate(
            title="Title {date}", body="Body {date}", color="teal", is_customized=False
        )
        title, body = AskRidesMessagesService.render(
            template, AskRidesMessageType.WEDNESDAY_FELLOWSHIP, date_str="4/22"
        )
        assert title == "Title 4/22"
        assert body == "Body 4/22"

    def test_fills_ping_token_for_sunday_service(self):
        template = EffectiveTemplate(
            title="Title {date}",
            body="Body {date} ping {ping}",
            color="blue",
            is_customized=False,
        )
        title, body = AskRidesMessagesService.render(
            template,
            AskRidesMessageType.SUNDAY_SERVICE,
            date_str="4/26",
            ping_text="@coordinator",
        )
        assert title == "Title 4/26"
        assert body == "Body 4/26 ping @coordinator"

    def test_never_raises_on_stray_token(self):
        template = EffectiveTemplate(
            title="Title {unknown}", body="Body {also_unknown}", color="teal", is_customized=False
        )
        title, body = AskRidesMessagesService.render(
            template, AskRidesMessageType.WEDNESDAY_FELLOWSHIP, date_str="4/22"
        )
        assert title == "Title {unknown}"
        assert body == "Body {also_unknown}"

    def test_ping_not_required_for_non_sunday_service_types(self):
        template = EffectiveTemplate(
            title="Title", body="Body {date}", color="teal", is_customized=False
        )
        title, body = AskRidesMessagesService.render(
            template, AskRidesMessageType.FRIDAY_FELLOWSHIP, date_str="4/24"
        )
        assert title == "Title"
        assert body == "Body 4/24"
