"""Registry of Discord bots run by this process."""

from collections.abc import Callable
from dataclasses import dataclass

import discord

from shared.core.enums import BotName, FeatureFlagNames

SHARED_PACKAGE = "shared"


@dataclass(frozen=True)
class BotSpec:
    """Static configuration for one Discord bot."""

    name: BotName
    token_env: str
    cog_packages: tuple[str, ...]
    intents: Callable[[], discord.Intents]
    kill_switch_flag: FeatureFlagNames
    priority_extensions: tuple[str, ...] = ()
    testing_cog_package: str | None = None


@dataclass(frozen=True)
class EnabledBot:
    """A bot whose token was found at startup."""

    spec: BotSpec
    token: str


def _ridebot_intents() -> discord.Intents:
    intents = discord.Intents.default()
    intents.message_content = True
    intents.guilds = True
    intents.reactions = True
    intents.members = True
    return intents


# Order is the error-reporting fallback priority.
BOT_REGISTRY: tuple[BotSpec, ...] = (
    BotSpec(
        name=BotName.RIDEBOT,
        token_env="RIDEBOT_TOKEN",
        cog_packages=("ridebot.cogs", "shared.cogs"),
        intents=_ridebot_intents,
        kill_switch_flag=FeatureFlagNames.RIDEBOT,
        priority_extensions=("job_scheduler",),
        testing_cog_package="ridebot.cogs_testing",
    ),
)


def get_spec(name: BotName) -> BotSpec:
    """Return the spec for a bot. Raises KeyError if it is not registered."""
    for spec in BOT_REGISTRY:
        if spec.name == name:
            return spec
    raise KeyError(name)


def bot_package_names() -> set[str]:
    """Return the top-level Python package of every registered bot."""
    return {
        pkg.split(".", 1)[0]
        for spec in BOT_REGISTRY
        for pkg in spec.cog_packages
        if pkg.split(".", 1)[0] != SHARED_PACKAGE
    }


def resolve_enabled_bots() -> list[EnabledBot]:
    """Read bot tokens and decide which bots start; exits on misconfiguration."""
    raise NotImplementedError
