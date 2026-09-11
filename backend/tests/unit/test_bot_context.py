"""Unit tests for shared.core.bot_context."""

import asyncio

import pytest

from shared.core.bot_context import current_bot_var, get_current_bot_name
from shared.core.enums import BotName


class TestGetCurrentBotName:
    """Tests for get_current_bot_name."""

    def test_defaults_to_none(self):
        assert get_current_bot_name() is None

    def test_returns_value_set_on_the_contextvar(self):
        token = current_bot_var.set(BotName.RIDEBOT)
        try:
            assert get_current_bot_name() is BotName.RIDEBOT
        finally:
            current_bot_var.reset(token)


class TestContextPropagation:
    """The core assumption behind per-bot logging/kill-switches: child tasks inherit the var."""

    @pytest.mark.asyncio
    async def test_child_task_created_inside_bot_task_sees_the_bot_name(self):
        seen: list[BotName | None] = []

        async def child() -> None:
            # Simulates an event handler / slash command / scheduled job callback
            # spawned from inside a bot's run task.
            seen.append(get_current_bot_name())

        async def parent() -> None:
            current_bot_var.set(BotName.RIDEBOT)
            await asyncio.create_task(child())

        await asyncio.create_task(parent())

        assert seen == [BotName.RIDEBOT]

    @pytest.mark.asyncio
    async def test_sibling_tasks_do_not_leak_into_each_other(self):
        results: dict[str, BotName | None] = {}

        async def task_with_bot() -> None:
            current_bot_var.set(BotName.RIDEBOT)
            await asyncio.sleep(0)
            results["with_bot"] = get_current_bot_name()

        async def task_without_bot() -> None:
            await asyncio.sleep(0)
            results["without_bot"] = get_current_bot_name()

        await asyncio.gather(
            asyncio.create_task(task_with_bot()), asyncio.create_task(task_without_bot())
        )

        assert results["with_bot"] is BotName.RIDEBOT
        assert results["without_bot"] is None
