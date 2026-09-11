from types import SimpleNamespace

import pytest

from shared.core.bot_context import current_bot_var
from shared.core.enums import BotName


@pytest.fixture(autouse=True)
def _current_bot():
    """Set the current-bot contextvar to RideBot for every unit test.

    Most unit tests exercise RideBot cogs/services, which now rely on
    `get_current_bot_name()` (e.g. via `bot_enabled`) to resolve which bot
    they're running under. Outside any bot task (like here), the var
    defaults to None, so tests need it set explicitly. Reset afterward so
    tests don't leak state into each other.
    """
    token = current_bot_var.set(BotName.RIDEBOT)
    try:
        yield
    finally:
        current_bot_var.reset(token)


class FakeParam:
    """Simulates a Discord command parameter."""

    def __init__(self, name, typ, required):
        self.name = name
        self.type = SimpleNamespace(name=typ)
        self.required = required


class FakeCommand:
    """Simulates a Discord app command."""

    def __init__(self, name, description, parameters):
        self.name = name
        self.description = description
        self.parameters = parameters


class FakeCommandTree:
    """Simulates bot.tree.get_commands()."""

    def __init__(self, commands):
        self._commands = commands

    def get_commands(self):
        return self._commands


class FakeBot:
    """Fake bot mimicking discord.ext.commands.Bot enough for tests."""

    def __init__(self, commands=None):
        self.tree = FakeCommandTree(commands or [])


@pytest.fixture
def fake_bot():
    """Reusable fake bot fixture with example commands."""
    commands = [
        FakeCommand(
            name="ask-drivers",
            description="Ping all drivers",
            parameters=[
                FakeParam("day", "string", True),
                FakeParam("message", "string", True),
            ],
        ),
        FakeCommand(
            name="help",
            description="List all commands",
            parameters=[],
        ),
    ]
    return FakeBot(commands)
