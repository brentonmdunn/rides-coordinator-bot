"""Unit tests for shared.core.logger.BotNameFilter."""

import logging

from shared.core.bot_context import current_bot_var
from shared.core.enums import BotName
from shared.core.logger import BotNameFilter


def _make_record() -> logging.LogRecord:
    return logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="message",
        args=(),
        exc_info=None,
    )


class TestBotNameFilter:
    """Tests for BotNameFilter."""

    def test_sets_bot_name_when_context_set(self):
        token = current_bot_var.set(BotName.RIDEBOT)
        try:
            record = _make_record()
            result = BotNameFilter().filter(record)
        finally:
            current_bot_var.reset(token)

        assert result is True
        assert record.bot_name == BotName.RIDEBOT

    def test_defaults_to_dash_when_unset(self):
        record = _make_record()
        result = BotNameFilter().filter(record)

        assert result is True
        assert record.bot_name == "-"
