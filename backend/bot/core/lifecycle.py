"""Shared bot lifecycle: construction, startup, extension loading, and event handlers."""

import logging
import os
import sys
import traceback
from collections.abc import Awaitable, Callable
from pathlib import Path

import discord
from discord import Interaction
from discord.app_commands import AppCommandError, CheckFailure
from discord.ext import commands
from discord.ext.commands import Bot
from sqlalchemy import or_, update

from bot.core.database import (
    AsyncSessionLocal,
    init_db,
    seed_admin_accounts,
    seed_feature_flags,
    seed_message_schedule_pauses,
)
from bot.core.models import FeatureFlags
from bot.repositories.feature_flags_repository import FeatureFlagsRepository

logger = logging.getLogger(__name__)

APP_ENV: str = os.getenv("APP_ENV", "local")

_SendErrorFn = Callable[..., Awaitable[None]]


def build_bot() -> Bot:
    """Create a configured Bot instance with the standard intents."""
    intents = discord.Intents.default()
    intents.message_content = True
    intents.guilds = True
    intents.reactions = True
    intents.members = True
    return commands.Bot(command_prefix="!", intents=intents)


async def startup() -> None:
    """Initialize cache backend, database, seeds, feature flag cache, and local-env flags."""
    if APP_ENV != "local":
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        from bot.utils.cache_backends import RedisBackend, set_backend

        set_backend(RedisBackend(redis_url))

    await init_db()
    async with AsyncSessionLocal() as session:
        await seed_feature_flags(session)
    async with AsyncSessionLocal() as session:
        await seed_message_schedule_pauses(session)
    async with AsyncSessionLocal() as session:
        await seed_admin_accounts(session)
    await FeatureFlagsRepository.initialize_cache()
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


async def load_extensions(bot: Bot) -> None:
    """Load all cogs from bot/cogs (and bot/cogs_testing in local env)."""
    cogs_path = Path.cwd() / "bot" / "cogs"
    priority_filename = "job_scheduler.py"

    eligible_files = [
        f
        for f in cogs_path.iterdir()
        if f.is_file() and f.suffix == ".py" and not f.name.startswith("_")
    ]
    eligible_files.sort(key=lambda f: (f.name != priority_filename, f.name))

    for filename in eligible_files:
        extension = f"bot.cogs.{filename.stem}"
        try:
            await bot.load_extension(extension)
            logger.info(f"✅ Loaded extension: {extension}")
        except Exception as e:
            logger.warning(f"❌ Failed to load extension {extension}: {e}")

    if APP_ENV == "local":
        cogs_testing_path = Path.cwd() / "bot" / "cogs_testing"
        eligible_files = [
            f
            for f in cogs_testing_path.iterdir()
            if f.is_file() and f.suffix == ".py" and not f.name.startswith("_")
        ]
        for filename in reversed(eligible_files):
            extension = f"bot.cogs_testing.{filename.stem}"
            try:
                await bot.load_extension(extension)
                logger.info(f"✅ Loaded extension: {extension}")
            except Exception as e:
                logger.warning(f"❌ Failed to load extension {extension}: {e}")


def attach_event_handlers(bot: Bot, send_error_fn: _SendErrorFn) -> None:
    """Attach on_ready, on_error, and on_app_command_error to bot."""

    @bot.event
    async def on_ready() -> None:
        logger.info(f"✅ Logged in as {bot.user}!")
        logger.info(f"🛠️  Synced {len(await bot.tree.sync())} slash commands.")
        for guild in bot.guilds:
            try:
                members: list[discord.Member] = []
                async for member in guild.fetch_members(limit=None):
                    members.append(member)
                logger.info(f"📥 Cached {len(members)} members in '{guild.name}'")
            except Exception as e:
                logger.warning(f"❌ Failed to fetch members for guild '{guild.name}': {e}")

    @bot.event
    async def on_error(event: str, *args, **kwargs) -> None:
        exc_info = sys.exc_info()
        if exc_info[0] is not None:
            tb_lines = traceback.format_exception(*exc_info)
            tb_text = "".join(tb_lines)
            logger.exception(f"Uncaught exception in {event}")
            await send_error_fn(f"**Uncaught Exception in Event: `{event}`**", tb_text=tb_text)
        else:
            logger.error(f"Unknown error in event {event}")

    @bot.tree.error
    async def on_app_command_error(interaction: Interaction, error: AppCommandError) -> None:
        if isinstance(error, CheckFailure):
            await interaction.response.send_message(
                "❌ You must be a server admin to use this command.",
                ephemeral=True,
            )
            return

        logger.error(f"App command error: {error}", exc_info=error)

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
            pass

        cmd_name = interaction.command.name if interaction.command else "Unknown"
        channel_mention = interaction.channel.mention if interaction.channel else "Unknown"
        error_msg = (
            "**App Command Error**\n"
            f"Command: `{cmd_name}`\n"
            f"User: {interaction.user.mention} ({interaction.user.id})\n"
            f"Channel: {channel_mention}\n"
        )
        await send_error_fn(error_msg, error=error)
