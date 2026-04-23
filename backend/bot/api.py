"""
Bot API Access Layer

This module provides the bot lifecycle context manager for the FastAPI application.
Bot instance access is in bot.core.bot_instance; error reporting is in bot.core.error_reporter.
"""

import asyncio
import logging
import os
import traceback
from contextlib import asynccontextmanager
from pathlib import Path

import discord
from discord import Interaction
from discord.app_commands import AppCommandError, CheckFailure
from discord.ext import commands
from discord.ext.commands import Bot
from dotenv import load_dotenv
from sqlalchemy import or_, update

from bot.core.bot_instance import set_bot_instance
from bot.core.database import (
    AsyncSessionLocal,
    init_db,
    seed_admin_accounts,
    seed_feature_flags,
    seed_message_schedule_pauses,
)
from bot.core.error_reporter import send_error_to_discord
from bot.core.models import FeatureFlags
from bot.repositories.feature_flags_repository import FeatureFlagsRepository

logger = logging.getLogger(__name__)

load_dotenv()
APP_ENV: str = os.getenv("APP_ENV", "local")
TOKEN: str | None = os.getenv("TOKEN")


async def _load_extensions(bot: Bot) -> None:
    """Load all bot extensions (cogs)."""
    cogs_path = Path.cwd() / "bot" / "cogs"
    priority_filename = "job_scheduler.py"

    eligible_files = [
        filename
        for filename in cogs_path.iterdir()
        if filename.is_file() and filename.suffix == ".py" and not filename.name.startswith("_")
    ]

    # Sort files, ensuring job_scheduler.py is always first
    eligible_files.sort(key=lambda f: (f.name != priority_filename, f.name))

    for filename in eligible_files:
        extension: str = f"bot.cogs.{filename.stem}"
        try:
            await bot.load_extension(extension)
            logger.info(f"✅ Loaded extension: {extension}")
        except Exception as e:
            logger.warning(f"❌ Failed to load extension {extension}: {e}")

    if APP_ENV == "local":
        cogs_testing_path = Path.cwd() / "bot" / "cogs_testing"

        eligible_files = [
            filename
            for filename in cogs_testing_path.iterdir()
            if filename.is_file() and filename.suffix == ".py" and not filename.name.startswith("_")
        ]

        for filename in reversed(eligible_files):
            extension: str = f"bot.cogs_testing.{filename.stem}"
            try:
                await bot.load_extension(extension)
                logger.info(f"✅ Loaded extension: {extension}")
            except Exception as e:
                logger.warning(f"❌ Failed to load extension {extension}: {e}")


async def _disable_features_for_local_env():
    """If running locally, disable all jobs and message-related flags to prevent spam."""
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
        except Exception as e:
            logger.error(f"❌ Failed to disable local-dev feature flags: {e}")
            await session.rollback()


@asynccontextmanager
async def bot_lifespan():
    """
    Async context manager for Discord bot lifecycle.

    Handles bot initialization, startup, and shutdown.
    Sets the global _bot_instance for API access.

    Usage:
        async with bot_lifespan():
            # Bot is running
            pass
        # Bot is shutdown
    """
    # Setup bot intents
    intents: discord.Intents = discord.Intents.default()
    intents.message_content = True
    intents.guilds = True
    intents.reactions = True
    intents.members = True

    # Create bot instance
    bot: Bot = commands.Bot(command_prefix="!", intents=intents)

    # Set up event handlers
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
        """Handle uncaught exceptions and send them to the error channel."""
        import sys

        exc_info = sys.exc_info()

        if exc_info[0] is not None:
            tb_lines = traceback.format_exception(*exc_info)
            tb_text = "".join(tb_lines)

            logger.error(f"Uncaught exception in {event}: {tb_text}")
            await send_error_to_discord(f"**Uncaught Exception in Event: `{event}`**", tb_text)
        else:
            logger.error(f"Unknown error in event {event}")

    @bot.tree.error
    async def on_app_command_error(
        interaction: Interaction,
        error: AppCommandError,
    ) -> None:
        """Handle errors for app commands."""
        if isinstance(error, CheckFailure):
            await interaction.response.send_message(
                "❌ You must be a server admin to use this command.",
                ephemeral=True,
            )
        else:
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

            error_msg = "**App Command Error**\n"
            error_msg += f"Command: `{cmd_name}`\n"
            error_msg += f"User: {interaction.user.mention} ({interaction.user.id})\n"
            error_msg += f"Channel: {channel_mention}\n"

            await send_error_to_discord(error_msg)

    # Initialize cache backend (Redis for prod/preprod, in-memory for local)
    if APP_ENV != "local":
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        from bot.utils.cache_backends import RedisBackend, set_backend

        set_backend(RedisBackend(redis_url))

    # Initialize database and feature flags
    await init_db()
    async with AsyncSessionLocal() as session:
        await seed_feature_flags(session)
    async with AsyncSessionLocal() as session:
        await seed_message_schedule_pauses(session)
    async with AsyncSessionLocal() as session:
        await seed_admin_accounts(session)
    async with AsyncSessionLocal() as session:
        await FeatureFlagsRepository.initialize_cache(session)
    await _disable_features_for_local_env()

    # Load extensions
    if APP_ENV != "local":
        await _load_extensions(bot)

    # Start bot in background
    set_bot_instance(bot)
    bot_task = asyncio.create_task(bot.start(TOKEN))

    try:
        while not bot.is_ready():
            await asyncio.sleep(0.1)

        logger.info("🤖 Discord bot is ready and connected!")
        yield bot

    finally:
        logger.info("🛑 Shutting down Discord bot...")
        await bot.close()
        await bot_task
        set_bot_instance(None)
        logger.info("✅ Discord bot shutdown complete")
