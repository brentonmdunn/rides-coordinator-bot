from types import SimpleNamespace

import pytest


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
