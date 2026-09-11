"""Unit tests for shared.core.bots."""

import pytest

import shared.core.bots as bots_module
from shared.core.bots import BotSpec, EnabledBot, bot_package_names, get_spec, resolve_enabled_bots
from shared.core.enums import BotName, FeatureFlagNames


def _spec(name: BotName, token_env: str, flag: FeatureFlagNames) -> BotSpec:
    return BotSpec(
        name=name,
        token_env=token_env,
        cog_packages=(f"{name}.cogs",),
        intents=lambda: object(),  # not used by resolve_enabled_bots
        kill_switch_flag=flag,
    )


RIDEBOT_SPEC = _spec(BotName.RIDEBOT, "RIDEBOT_TOKEN", FeatureFlagNames.RIDEBOT)


class TestGetSpec:
    """Tests for get_spec."""

    def test_returns_registered_spec(self):
        assert get_spec(BotName.RIDEBOT).name == BotName.RIDEBOT

    def test_raises_key_error_for_unknown_bot(self, monkeypatch):
        monkeypatch.setattr(bots_module, "BOT_REGISTRY", ())
        with pytest.raises(KeyError):
            get_spec(BotName.RIDEBOT)


class TestBotPackageNames:
    """Tests for bot_package_names."""

    def test_excludes_shared_package(self, monkeypatch):
        spec = BotSpec(
            name=BotName.RIDEBOT,
            token_env="RIDEBOT_TOKEN",
            cog_packages=("ridebot.cogs", "shared.cogs"),
            intents=lambda: object(),
            kill_switch_flag=FeatureFlagNames.RIDEBOT,
        )
        monkeypatch.setattr(bots_module, "BOT_REGISTRY", (spec,))
        assert bot_package_names() == {"ridebot"}


class TestResolveEnabledBots:
    """Tests for resolve_enabled_bots, covering every token-behavior-table row."""

    def _single_registry(self, monkeypatch):
        monkeypatch.setattr(bots_module, "BOT_REGISTRY", (RIDEBOT_SPEC,))

    def test_non_local_all_set_starts_every_bot(self, monkeypatch):
        self._single_registry(monkeypatch)
        monkeypatch.setenv("APP_ENV", "prod")
        monkeypatch.setenv("RIDEBOT_TOKEN", "abc123")

        enabled = resolve_enabled_bots()

        assert enabled == [EnabledBot(spec=RIDEBOT_SPEC, token="abc123")]

    def test_non_local_missing_token_exits(self, monkeypatch):
        self._single_registry(monkeypatch)
        monkeypatch.setenv("APP_ENV", "preprod")
        monkeypatch.delenv("RIDEBOT_TOKEN", raising=False)

        with pytest.raises(SystemExit) as exc_info:
            resolve_enabled_bots()
        assert exc_info.value.code == 1

    def test_non_local_blank_token_counts_as_missing(self, monkeypatch):
        self._single_registry(monkeypatch)
        monkeypatch.setenv("APP_ENV", "prod")
        monkeypatch.setenv("RIDEBOT_TOKEN", "   ")

        with pytest.raises(SystemExit):
            resolve_enabled_bots()

    def test_non_local_logs_every_missing_var_before_exit(self, monkeypatch, caplog):
        spec_a = _spec(BotName.RIDEBOT, "RIDEBOT_TOKEN", FeatureFlagNames.RIDEBOT)
        # StonesBot doesn't exist yet on this branch; use a synthetic second spec
        # to exercise "log every missing var" with more than one bot.
        spec_b = BotSpec(
            name=BotName.RIDEBOT,
            token_env="SECOND_TOKEN",
            cog_packages=("ridebot.cogs",),
            intents=lambda: object(),
            kill_switch_flag=FeatureFlagNames.RIDEBOT,
        )
        monkeypatch.setattr(bots_module, "BOT_REGISTRY", (spec_a, spec_b))
        monkeypatch.setenv("APP_ENV", "prod")
        monkeypatch.delenv("RIDEBOT_TOKEN", raising=False)
        monkeypatch.delenv("SECOND_TOKEN", raising=False)

        with caplog.at_level("CRITICAL"), pytest.raises(SystemExit):
            resolve_enabled_bots()

        messages = [r.message for r in caplog.records]
        assert any("RIDEBOT_TOKEN" in m for m in messages)
        assert any("SECOND_TOKEN" in m for m in messages)

    def test_local_all_set_starts_every_bot(self, monkeypatch):
        self._single_registry(monkeypatch)
        monkeypatch.setenv("APP_ENV", "local")
        monkeypatch.setenv("RIDEBOT_TOKEN", "abc123")

        enabled = resolve_enabled_bots()

        assert enabled == [EnabledBot(spec=RIDEBOT_SPEC, token="abc123")]

    def test_local_some_missing_warns_and_skips(self, monkeypatch, caplog):
        spec_a = _spec(BotName.RIDEBOT, "RIDEBOT_TOKEN", FeatureFlagNames.RIDEBOT)
        spec_b = BotSpec(
            name=BotName.RIDEBOT,
            token_env="SECOND_TOKEN",
            cog_packages=("ridebot.cogs",),
            intents=lambda: object(),
            kill_switch_flag=FeatureFlagNames.RIDEBOT,
        )
        monkeypatch.setattr(bots_module, "BOT_REGISTRY", (spec_a, spec_b))
        monkeypatch.setenv("APP_ENV", "local")
        monkeypatch.setenv("RIDEBOT_TOKEN", "abc123")
        monkeypatch.setenv("SECOND_TOKEN", "")

        with caplog.at_level("WARNING"):
            enabled = resolve_enabled_bots()

        assert [e.spec for e in enabled] == [spec_a]
        assert any("SECOND_TOKEN" in r.message for r in caplog.records)

    def test_local_none_set_exits(self, monkeypatch):
        self._single_registry(monkeypatch)
        monkeypatch.setenv("APP_ENV", "local")
        monkeypatch.delenv("RIDEBOT_TOKEN", raising=False)

        with pytest.raises(SystemExit) as exc_info:
            resolve_enabled_bots()
        assert exc_info.value.code == 1

    def test_local_blank_token_counts_as_missing(self, monkeypatch):
        self._single_registry(monkeypatch)
        monkeypatch.setenv("APP_ENV", "local")
        monkeypatch.setenv("RIDEBOT_TOKEN", "   ")

        with pytest.raises(SystemExit):
            resolve_enabled_bots()

    def test_default_app_env_is_local(self, monkeypatch):
        self._single_registry(monkeypatch)
        monkeypatch.delenv("APP_ENV", raising=False)
        monkeypatch.delenv("RIDEBOT_TOKEN", raising=False)

        with pytest.raises(SystemExit):
            resolve_enabled_bots()

    def test_reads_env_at_call_time(self, monkeypatch):
        self._single_registry(monkeypatch)
        monkeypatch.setenv("APP_ENV", "local")
        monkeypatch.delenv("RIDEBOT_TOKEN", raising=False)
        with pytest.raises(SystemExit):
            resolve_enabled_bots()

        monkeypatch.setenv("RIDEBOT_TOKEN", "now-set")
        enabled = resolve_enabled_bots()
        assert enabled[0].token == "now-set"
