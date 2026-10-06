"""Unit tests for shared.core.lifecycle."""

import contextlib
import importlib
import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import discord
import pytest

import shared.core.bots as bots_module
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

    @pytest.fixture(autouse=True)
    def _no_single_bot_extensions(self, monkeypatch):
        """Keep these tests about package loading; single-bot routing is tested below."""
        monkeypatch.setattr(bots_module, "SINGLE_BOT_EXTENSIONS", {})
        monkeypatch.setattr(lifecycle, "SINGLE_BOT_EXTENSIONS", {})

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


class TestSingleBotExtensions:
    """Tests for routing SINGLE_BOT_EXTENSIONS to exactly one running bot."""

    EXTENSION = "shared.single_bot_cogs.example"

    @pytest.fixture(autouse=True)
    def _example_extension(self, monkeypatch):
        registry = {self.EXTENSION: (BotName.RIDEBOT, BotName.STONESBOT)}
        monkeypatch.setattr(bots_module, "SINGLE_BOT_EXTENSIONS", registry)
        monkeypatch.setattr(lifecycle, "SINGLE_BOT_EXTENSIONS", registry)

    @pytest.mark.parametrize(
        ("running", "owner"),
        [
            ({BotName.RIDEBOT, BotName.STONESBOT}, BotName.RIDEBOT),
            ({BotName.RIDEBOT}, BotName.RIDEBOT),
            ({BotName.STONESBOT}, BotName.STONESBOT),
        ],
    )
    def test_first_running_bot_in_preference_owns_it(self, running, owner):
        for name in running:
            expected = [self.EXTENSION] if name == owner else []
            assert bots_module.single_bot_extensions_for(name, running) == expected

    @pytest.mark.parametrize(
        "running",
        [
            {BotName.RIDEBOT, BotName.STONESBOT},
            {BotName.RIDEBOT},
            {BotName.STONESBOT},
        ],
    )
    def test_exactly_one_running_bot_owns_it(self, running):
        owners = [
            name
            for name in running
            if self.EXTENSION in bots_module.single_bot_extensions_for(name, running)
        ]
        assert len(owners) == 1

    def test_not_loaded_when_no_listed_bot_runs(self):
        assert bots_module.single_bot_extensions_for(BotName.STONESBOT, set()) == []

    @pytest.mark.asyncio
    async def test_loaded_after_packages_before_testing(self, tmp_path, monkeypatch):
        with (
            synthetic_package(tmp_path, "pkg_single_main", ["a"]) as pkg,
            synthetic_package(tmp_path, "pkg_single_testing", ["t"]) as testing_pkg,
        ):
            spec = _spec(
                name=BotName.STONESBOT, cog_packages=(pkg,), testing_cog_package=testing_pkg
            )
            monkeypatch.setattr(lifecycle, "APP_ENV", "local")
            bot = FakeBot()

            await lifecycle.load_extensions(bot, spec, running={BotName.STONESBOT})

            assert bot.loaded == [f"{pkg}.a", self.EXTENSION, f"{testing_pkg}.t"]

    @pytest.mark.asyncio
    async def test_fallback_bot_skips_it_when_usual_bot_runs(self, tmp_path):
        with synthetic_package(tmp_path, "pkg_single_skip", ["a"]) as pkg:
            spec = _spec(name=BotName.STONESBOT, cog_packages=(pkg,))
            bot = FakeBot()

            await lifecycle.load_extensions(bot, spec, running={BotName.RIDEBOT, BotName.STONESBOT})

            assert bot.loaded == [f"{pkg}.a"]

    @pytest.mark.asyncio
    async def test_defaults_to_all_registered_bots_running(self, tmp_path):
        with synthetic_package(tmp_path, "pkg_single_default", ["a"]) as pkg:
            ridebot = FakeBot()
            stonesbot = FakeBot()

            await lifecycle.load_extensions(ridebot, _spec(cog_packages=(pkg,)))
            await lifecycle.load_extensions(
                stonesbot, _spec(name=BotName.STONESBOT, cog_packages=(pkg,))
            )

            assert self.EXTENSION in ridebot.loaded
            assert self.EXTENSION not in stonesbot.loaded

    @pytest.mark.asyncio
    async def test_failure_is_recorded_for_the_loading_bot(self, tmp_path):
        with synthetic_package(tmp_path, "pkg_single_fail", ["a"]) as pkg:
            spec = _spec(name=BotName.STONESBOT, cog_packages=(pkg,))
            bot = FakeBot(fail_extensions={self.EXTENSION})

            await lifecycle.load_extensions(bot, spec, running={BotName.STONESBOT})

            assert lifecycle.get_failed_extensions() == {BotName.STONESBOT: {self.EXTENSION}}


class TestRealSingleBotRegistry:
    """The real registry: /feature-flag lives on RideBot, falling back to StonesBot."""

    def test_feature_flags_cog_preference(self):
        assert bots_module.SINGLE_BOT_EXTENSIONS["shared.single_bot_cogs.feature_flags"] == (
            BotName.RIDEBOT,
            BotName.STONESBOT,
        )

    def test_every_listed_bot_is_registered(self):
        registered = {spec.name for spec in bots_module.BOT_REGISTRY}
        for preference in bots_module.SINGLE_BOT_EXTENSIONS.values():
            assert set(preference) <= registered

    def test_extensions_are_importable_and_not_auto_loaded(self):
        auto_loaded = {pkg for spec in bots_module.BOT_REGISTRY for pkg in spec.cog_packages}
        for extension in bots_module.SINGLE_BOT_EXTENSIONS:
            module = importlib.import_module(extension)
            assert hasattr(module, "setup")
            assert extension.rsplit(".", 1)[0] not in auto_loaded


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


class CapturingBot:
    """Fake bot that stores event handlers so on_error can be invoked directly."""

    def __init__(self):
        self.tree = FakeTree()
        self.events: dict = {}

    def event(self, func):
        self.events[func.__name__] = func
        return func


def _reaction_payload() -> Mock:
    payload = Mock(spec=discord.RawReactionActionEvent)
    payload.guild_id = 916817752918982716
    payload.channel_id = 939950319721406464
    payload.message_id = 1554930864163397674
    payload.user_id = 42
    payload.emoji = "🍔"
    payload.event_type = "REACTION_ADD"
    return payload


class TestOnError:
    """Tests for the on_error handler's payload description (item A)."""

    @pytest.mark.asyncio
    async def test_reaction_payload_ids_in_alert(self):
        send_error_fn = AsyncMock()
        bot = CapturingBot()
        lifecycle.attach_event_handlers(bot, _spec(), send_error_fn)
        on_error = bot.events["on_error"]

        try:
            raise RuntimeError("boom")
        except RuntimeError:
            await on_error("on_raw_reaction_add", _reaction_payload())

        send_error_fn.assert_awaited_once()
        header = send_error_fn.await_args.args[0]
        assert "916817752918982716" in header  # guild_id
        assert "939950319721406464" in header  # channel_id
        assert "1554930864163397674" in header  # message_id
        assert "42" in header  # user_id
        assert "🍔" in header  # emoji

    @pytest.mark.asyncio
    async def test_arg_description_failure_still_sends_traceback(self):
        send_error_fn = AsyncMock()
        bot = CapturingBot()
        lifecycle.attach_event_handlers(bot, _spec(), send_error_fn)
        on_error = bot.events["on_error"]

        class Exploding:
            def __repr__(self):
                raise ValueError("no repr for you")

        try:
            raise RuntimeError("boom")
        except RuntimeError:
            # Must not raise even though describing the arg fails.
            await on_error("on_raw_reaction_add", Exploding())

        send_error_fn.assert_awaited_once()
        tb_text = send_error_fn.await_args.kwargs["tb_text"]
        assert "RuntimeError" in tb_text

    @pytest.mark.asyncio
    async def test_no_message_content_in_description(self):
        send_error_fn = AsyncMock()
        bot = CapturingBot()
        lifecycle.attach_event_handlers(bot, _spec(), send_error_fn)
        on_error = bot.events["on_error"]

        message = Mock(spec=discord.Message)
        message.id = 123
        message.channel = Mock()
        message.channel.id = 456
        message.author = Mock()
        message.author.id = 789
        message.content = "SECRET_CONTENT"

        try:
            raise RuntimeError("boom")
        except RuntimeError:
            await on_error("on_message", message)

        header = send_error_fn.await_args.args[0]
        assert "SECRET_CONTENT" not in header
        assert "123" in header  # the message id is present


class TestDescribeEventArgs:
    """Direct tests for _describe_event_args (item A)."""

    def test_empty_args(self):
        assert lifecycle._describe_event_args(()) == "<no args>"

    def test_truncates_long_output(self):
        # Many args so the joined description exceeds the overall cap.
        args = tuple("value" for _ in range(200))
        out = lifecycle._describe_event_args(args)
        assert len(out) <= lifecycle._MAX_DESCRIPTION
        assert out.endswith("…")


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

        async def crashing_run_bot(spec, token, running=None):
            # Finishes immediately, simulating a bad token / crash before readiness.
            return

        monkeypatch.setattr(lifespan, "run_bot", crashing_run_bot)

        with pytest.raises(SystemExit) as exc_info:
            async with lifespan.bot_lifespan():
                pytest.fail("should not reach the yield when a bot task exits early")

        assert exc_info.value.code == 1
