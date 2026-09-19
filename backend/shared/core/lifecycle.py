"""Shared bot lifecycle: construction, startup, extension loading, and event handlers."""

import asyncio
import importlib
import logging
import os
import pkgutil
import sys
import traceback
from collections.abc import Awaitable, Callable

import discord
from discord import Interaction
from discord.app_commands import AppCommandError, CheckFailure
from discord.ext import commands
from discord.ext.commands import Bot
from sqlalchemy import or_, update

from shared.core.bot_context import current_bot_var
from shared.core.bot_instance import get_registered_bots, set_bot_instance
from shared.core.bots import BotSpec
from shared.core.database import (
    AsyncSessionLocal,
    init_db,
    seed_admin_accounts,
    seed_bypass_account,
    seed_feature_flags,
    seed_message_schedule_pauses,
)
from shared.core.enums import BotName
from shared.core.error_reporter import send_error_to_discord
from shared.core.models import FeatureFlags
from shared.repositories.feature_flags_repository import FeatureFlagsRepository
from shared.utils.checks import UserFacingCheckFailure
from shared.utils.constants import REDIS_CONNECTION_TIMEOUT

logger = logging.getLogger(__name__)

APP_ENV: str = os.getenv("APP_ENV", "local")

_failed_extensions: dict[BotName, set[str]] = {}
_enabled_bots: set[BotName] = set()


def get_failed_extensions() -> dict[BotName, set[str]]:
    """Return extension names that failed to load, keyed by bot."""
    return _failed_extensions


def mark_bot_enabled(name: BotName) -> None:
    """Record that a bot was started in this process."""
    _enabled_bots.add(name)


def get_enabled_bot_names() -> set[BotName]:
    """Return the bots started in this process."""
    return set(_enabled_bots)


_SendErrorFn = Callable[..., Awaitable[None]]


def build_bot(spec: BotSpec) -> Bot:
    """Create a configured Bot instance using the intents from spec."""
    return commands.Bot(command_prefix="!", intents=spec.intents())


async def startup() -> None:
    """Initialize cache backend, database, seeds, feature flag cache, and local-env flags."""
    if APP_ENV != "local":
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        from shared.utils.cache_backends import RedisBackend, set_backend

        backend = RedisBackend(redis_url)
        try:
            await asyncio.wait_for(backend._redis.ping(), timeout=REDIS_CONNECTION_TIMEOUT)  # ty: ignore[invalid-argument-type]
            logger.info("Redis connection established")
            set_backend(backend)
        except Exception:
            logger.warning("Redis unavailable at startup, falling back to in-memory cache")

    await init_db()
    async with AsyncSessionLocal() as session:
        await seed_feature_flags(session)
    async with AsyncSessionLocal() as session:
        await seed_message_schedule_pauses(session)
    async with AsyncSessionLocal() as session:
        await seed_admin_accounts(session)
    async with AsyncSessionLocal() as session:
        await seed_bypass_account(session)
    async with AsyncSessionLocal() as session:
        await FeatureFlagsRepository.initialize_cache(session)
    await _disable_features_for_local_env()


async def _disable_features_for_local_env() -> None:
    if APP_ENV != "local":
        return

    logger.info("🔧 APP_ENV is 'local'. Disabling job and message-related feature flags...")
    async with AsyncSessionLocal() as session:
        try:
            stmt = (
                update(FeatureFlags)
                .where(
                    or_(
                        FeatureFlags.feature.like("%_job"),
                        FeatureFlags.feature.like("%_msg"),
                    )
                )
                .values(enabled=False)
            )
            result = await session.execute(stmt)
            await session.commit()
            if result.rowcount > 0:
                logger.info(f"🔩 Disabled {result.rowcount} feature flags for local development.")
            else:
                logger.info(
                    "🔩 No job or message flags needed to be disabled for local development."
                )
        except Exception:
            logger.exception("Failed to disable local-dev feature flags")
            await session.rollback()


def _sorted_module_stems(package: str, priority_stems: tuple[str, ...] = ()) -> list[str]:
    """Return non-underscore module stems in a package: priority stems first, then alphabetical."""
    module = importlib.import_module(package)
    stems = [
        info.name for info in pkgutil.iter_modules(module.__path__) if not info.name.startswith("_")
    ]
    return sorted(stems, key=lambda name: (name not in priority_stems, name))


async def _load_package_extensions(
    bot: Bot, spec: BotSpec, package: str, priority_stems: tuple[str, ...] = ()
) -> None:
    for stem in _sorted_module_stems(package, priority_stems):
        extension = f"{package}.{stem}"
        try:
            await bot.load_extension(extension)
            logger.info(f"✅ Loaded extension: {extension}")
        except Exception:
            logger.exception(f"❌ Failed to load extension {extension}")
            _failed_extensions.setdefault(spec.name, set()).add(extension)


async def load_extensions(bot: Bot, spec: BotSpec) -> None:
    """Load every cog package in spec.cog_packages, then the testing package when local."""
    for package in spec.cog_packages:
        await _load_package_extensions(bot, spec, package, spec.priority_extensions)

    if APP_ENV == "local" and spec.testing_cog_package:
        await _load_package_extensions(bot, spec, spec.testing_cog_package)


def attach_event_handlers(bot: Bot, spec: BotSpec, send_error_fn: _SendErrorFn) -> None:
    """Attach on_ready, on_error, and on_app_command_error to bot."""

    @bot.event
    async def on_ready() -> None:
        logger.info(f"✅ [{spec.name}] Logged in as {bot.user}!")
        logger.info(f"🛠️  [{spec.name}] Synced {len(await bot.tree.sync())} slash commands.")
        for guild in bot.guilds:
            try:
                members: list[discord.Member] = []
                async for member in guild.fetch_members(limit=None):
                    members.append(member)
                logger.info(f"📥 [{spec.name}] Cached {len(members)} members in '{guild.name}'")
            except Exception as e:
                logger.warning(
                    f"❌ [{spec.name}] Failed to fetch members for guild '{guild.name}': {e}"
                )

    @bot.event
    async def on_error(event: str, *args, **kwargs) -> None:
        exc_info = sys.exc_info()
        if exc_info[0] is not None:
            tb_lines = traceback.format_exception(*exc_info)
            tb_text = "".join(tb_lines)
            logger.exception(f"[{spec.name}] Uncaught exception in {event}")
            await send_error_fn(
                f"**[{spec.name}] Uncaught Exception in Event: `{event}`**", tb_text=tb_text
            )
        else:
            logger.error(f"[{spec.name}] Unknown error in event {event}")

    @bot.tree.error
    async def on_app_command_error(interaction: Interaction, error: AppCommandError) -> None:
        if isinstance(error, CheckFailure):
            message = (
                str(error)
                if isinstance(error, UserFacingCheckFailure)
                else "❌ You must be a server admin to use this command."
            )
            await interaction.response.send_message(message, ephemeral=True)
            return

        logger.error(f"[{spec.name}] App command error: {error}", exc_info=error)

        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ An error occurred while processing this command.",
                    ephemeral=True,
                )
            else:
                await interaction.followup.send(
                    "❌ An error occurred while processing this command.",
                    ephemeral=True,
                )
        except Exception:
            logger.exception(f"[{spec.name}] Failed to send Discord error response for app command")

        cmd_name = interaction.command.name if interaction.command else "Unknown"
        channel_mention = (
            interaction.channel.mention
            if isinstance(interaction.channel, discord.TextChannel)
            else "Unknown"
        )
        error_msg = (
            f"**[{spec.name}] App Command Error**\n"
            f"Command: `{cmd_name}`\n"
            f"User: {interaction.user.mention} ({interaction.user.id})\n"
            f"Channel: {channel_mention}\n"
        )
        await send_error_fn(error_msg, error=error)


async def run_bot(spec: BotSpec, token: str) -> None:
    """Set up and start one bot inside its own task. Exceptions propagate to the caller."""
    current_bot_var.set(spec.name)

    mark_bot_enabled(spec.name)

    bot = build_bot(spec)
    attach_event_handlers(bot, spec, send_error_to_discord)
    set_bot_instance(spec.name, bot)

    await load_extensions(bot, spec)
    await bot.start(token)


async def close_bot(name: BotName) -> None:
    """Close a registered bot with a timeout, then clear its instance. No-op if not registered."""
    bot = get_registered_bots().get(name)
    if bot is None:
        return

    try:
        await asyncio.wait_for(bot.close(), timeout=10.0)
    except TimeoutError:
        logger.warning(f"[{name}] Bot close timed out after 10s")
    set_bot_instance(name, None)
