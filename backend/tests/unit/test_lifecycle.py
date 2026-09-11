"""Unit tests for shared.core.lifecycle."""

import contextlib
import importlib
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

import shared.core.lifecycle as lifecycle
import shared.core.lifespan as lifespan
from shared.core.bot_instance import get_registered_bots, set_bot_instance
from shared.core.bots import BotSpec, EnabledBot
from shared.core.enums import BotName, FeatureFlagNames


@contextlib.contextmanager
def synthetic_package(tmp_path: Path, name: str, modules: list[str]):
    """Create an importable package with the given empty module files, then clean it up."""
    pkg_dir = tmp_path / name
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("")
    for module_name in modules:
        (pkg_dir / f"{module_name}.py").write_text("")

    sys.path.insert(0, str(tmp_path))
    importlib.invalidate_caches()
    try:
        yield name
    finally:
        sys.path.remove(str(tmp_path))
        for mod_name in list(sys.modules):
            if mod_name == name or mod_name.startswith(f"{name}."):
                del sys.modules[mod_name]


class FakeTree:
    """Fake discord.app_commands.CommandTree, just enough for attach_event_handlers."""

    def error(self, func):
        return func

    async def sync(self):
        return []


class FakeBot:
    """Fake discord.ext.commands.Bot for exercising load_extensions/close_bot."""

    def __init__(self, fail_extensions: set[str] | None = None):
        self.tree = FakeTree()
        self.user = "FakeUser#0000"
        self.guilds: list = []
        self.loaded: list[str] = []
        self.fail_extensions = fail_extensions or set()
        self.closed = False

    def event(self, func):
        return func

    async def load_extension(self, extension: str) -> None:
        if extension in self.fail_extensions:
            raise RuntimeError(f"boom loading {extension}")
        self.loaded.append(extension)

    def is_ready(self) -> bool:
        return True

    async def close(self) -> None:
        self.closed = True


def _spec(**overrides) -> BotSpec:
    defaults = {
        "name": BotName.RIDEBOT,
        "token_env": "RIDEBOT_TOKEN",
        "cog_packages": (),
        "intents": lambda: object(),
        "kill_switch_flag": FeatureFlagNames.RIDEBOT,
    }
    defaults.update(overrides)
    return BotSpec(**defaults)


@pytest.fixture(autouse=True)
def _clear_failed_extensions():
    lifecycle._failed_extensions.clear()
    lifecycle._enabled_bots.clear()
    yield
    lifecycle._failed_extensions.clear()
    lifecycle._enabled_bots.clear()


class TestLoadExtensions:
    """Tests for load_extensions: discovery, ordering, priority, and failure recording."""

    @pytest.mark.asyncio
    async def test_priority_stems_load_first_then_alphabetical(self, tmp_path):
        with synthetic_package(tmp_path, "pkg_priority", ["c", "a", "b", "_hidden"]) as pkg:
            spec = _spec(cog_packages=(pkg,), priority_extensions=("b",))
            bot = FakeBot()

            await lifecycle.load_extensions(bot, spec)

            assert bot.loaded == [f"{pkg}.b", f"{pkg}.a", f"{pkg}.c"]

    @pytest.mark.asyncio
    async def test_loads_multiple_packages_in_order(self, tmp_path):
        with (
            synthetic_package(tmp_path, "pkg_one", ["z", "a"]) as pkg1,
            synthetic_package(tmp_path, "pkg_two", ["m"]) as pkg2,
        ):
            spec = _spec(cog_packages=(pkg1, pkg2))
            bot = FakeBot()

            await lifecycle.load_extensions(bot, spec)

            assert bot.loaded == [f"{pkg1}.a", f"{pkg1}.z", f"{pkg2}.m"]

    @pytest.mark.asyncio
    async def test_testing_package_loaded_last_only_when_local(self, tmp_path, monkeypatch):
        with (
            synthetic_package(tmp_path, "pkg_main", ["a"]) as pkg,
            synthetic_package(tmp_path, "pkg_testing", ["t"]) as testing_pkg,
        ):
            spec = _spec(cog_packages=(pkg,), testing_cog_package=testing_pkg)

            monkeypatch.setattr(lifecycle, "APP_ENV", "local")
            bot = FakeBot()
            await lifecycle.load_extensions(bot, spec)
            assert bot.loaded == [f"{pkg}.a", f"{testing_pkg}.t"]

            monkeypatch.setattr(lifecycle, "APP_ENV", "prod")
            bot = FakeBot()
            await lifecycle.load_extensions(bot, spec)
            assert bot.loaded == [f"{pkg}.a"]

    @pytest.mark.asyncio
    async def test_failures_recorded_per_bot_and_do_not_stop_the_rest(self, tmp_path):
        with synthetic_package(tmp_path, "pkg_fail", ["a", "b", "c"]) as pkg:
            spec = _spec(name=BotName.RIDEBOT, cog_packages=(pkg,))
            bot = FakeBot(fail_extensions={f"{pkg}.b"})

            await lifecycle.load_extensions(bot, spec)

            assert bot.loaded == [f"{pkg}.a", f"{pkg}.c"]
            assert lifecycle.get_failed_extensions() == {BotName.RIDEBOT: {f"{pkg}.b"}}

    @pytest.mark.asyncio
    async def test_skips_names_starting_with_underscore(self, tmp_path):
        with synthetic_package(tmp_path, "pkg_underscore", ["visible", "_skipped"]) as pkg:
            spec = _spec(cog_packages=(pkg,))
            bot = FakeBot()

            await lifecycle.load_extensions(bot, spec)

            assert bot.loaded == [f"{pkg}.visible"]


class TestCloseBot:
    """Tests for close_bot."""

    @pytest.mark.asyncio
    async def test_closes_and_clears_a_registered_bot(self):
        bot = FakeBot()
        set_bot_instance(BotName.RIDEBOT, bot)
        try:
            await lifecycle.close_bot(BotName.RIDEBOT)
            assert bot.closed is True
            assert BotName.RIDEBOT not in get_registered_bots()
        finally:
            set_bot_instance(BotName.RIDEBOT, None)

    @pytest.mark.asyncio
    async def test_no_op_when_not_registered(self):
        # Should not raise even though no bot was ever registered.
        await lifecycle.close_bot(BotName.RIDEBOT)
        assert BotName.RIDEBOT not in get_registered_bots()

    @pytest.mark.asyncio
    async def test_timeout_warns_and_still_clears_instance(self, monkeypatch, caplog):
        bot = FakeBot()
        set_bot_instance(BotName.RIDEBOT, bot)

        class _TimingOutAsyncio:
            async def wait_for(self, coro, timeout):
                coro.close()
                raise TimeoutError

        monkeypatch.setattr(lifecycle, "asyncio", _TimingOutAsyncio())

        try:
            with caplog.at_level("WARNING"):
                await lifecycle.close_bot(BotName.RIDEBOT)

            assert any("timed out" in r.message.lower() for r in caplog.records)
            assert BotName.RIDEBOT not in get_registered_bots()
        finally:
            set_bot_instance(BotName.RIDEBOT, None)


class TestBotLifespanReadiness:
    """Tests for bot_lifespan's ready/exit-early race, in shared.core.lifespan."""

    @pytest.mark.asyncio
    async def test_exits_when_a_bot_task_finishes_before_ready(self, monkeypatch):
        spec = _spec()
        enabled = EnabledBot(spec=spec, token="tok")

        monkeypatch.delenv("DISABLE_DISCORD_BOT", raising=False)
        monkeypatch.setattr(lifespan, "resolve_enabled_bots", lambda: [enabled])
        monkeypatch.setattr(lifespan, "startup", AsyncMock())
        monkeypatch.setattr(lifespan, "close_bot", AsyncMock())
        monkeypatch.setattr(lifespan, "get_bot", lambda name: None)

        async def crashing_run_bot(spec, token):
            # Finishes immediately, simulating a bad token / crash before readiness.
            return

        monkeypatch.setattr(lifespan, "run_bot", crashing_run_bot)

        with pytest.raises(SystemExit) as exc_info:
            async with lifespan.bot_lifespan():
                pytest.fail("should not reach the yield when a bot task exits early")

        assert exc_info.value.code == 1
