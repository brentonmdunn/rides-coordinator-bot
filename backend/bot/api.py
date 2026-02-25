"""
Bot API Access Layer

This module provides access to the Discord bot instance for the FastAPI application.
It manages the bot lifecycle and allows API endpoints to interact with Discord.
"""

import asyncio
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

from bot.core.database import (
    AsyncSessionLocal,
    init_db,
    seed_feature_flags,
    seed_message_schedule_pauses,
)
from bot.core.logger import logger
from bot.core.models import FeatureFlags
from bot.repositories.feature_flags_repository import FeatureFlagsRepository

load_dotenv()
TOKEN: str | None = os.getenv("TOKEN")
APP_ENV: str = os.getenv("APP_ENV", "local")
_error_channel_id = os.getenv("ERROR_CHANNEL_ID")
ERROR_CHANNEL_ID: int | None = int(_error_channel_id) if _error_channel_id else None

if ERROR_CHANNEL_ID:
    logger.info(f"✅ Error channel configured: {ERROR_CHANNEL_ID}")
else:
    logger.warning("⚠️  Error channel not configured - errors will only be logged")

# Global bot instance
_bot_instance: Bot | None = None


def get_bot() -> Bot | None:
    """
    Get the running Discord bot instance.

    Returns:
        The bot instance if running and ready, None otherwise.
    """
    return _bot_instance if _bot_instance and _bot_instance.is_ready() else None


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
    global _bot_instance

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
        # Get exception info
        import sys

        exc_info = sys.exc_info()

        # Format the full traceback
        error_msg = f"**Uncaught Exception in Event: `{event}`**\n\n"

        if exc_info[0] is not None:
            tb_lines = traceback.format_exception(*exc_info)
            tb_text = "".join(tb_lines)

            # Discord has a 2000 character limit for messages
            # Split into multiple messages if needed
            error_msg += f"```python\n{tb_text}\n```"

            # Log the error
            logger.error(f"Uncaught exception in {event}: {tb_text}")

            if APP_ENV == "local" or ERROR_CHANNEL_ID is None:
                return

            # Send to error channel
            try:
                channel = bot.get_channel(ERROR_CHANNEL_ID)
                if channel and isinstance(channel, discord.TextChannel):
                    if len(error_msg) > 2000:
                        # Send header
                        await channel.send(f"**Uncaught Exception in Event: `{event}`**")
                        # Send traceback in chunks
                        chunks = [tb_text[i : i + 1900] for i in range(0, len(tb_text), 1900)]
                        for chunk in chunks:
                            await channel.send(f"```python\n{chunk}\n```")
                    else:
                        await channel.send(error_msg)
                else:
                    logger.warning(
                        f"Error channel {ERROR_CHANNEL_ID} not found or not a text channel"
                    )
            except Exception as e:
                logger.error(f"Failed to send error to channel {ERROR_CHANNEL_ID}: {e}")
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
            # Log the error
            logger.error(f"App command error: {error}", exc_info=error)

            # Send error to the user
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
                pass  # Fail silently if we can't respond to the user

            if APP_ENV == "local" or ERROR_CHANNEL_ID is None:
                return

            # Send to error channel
            try:
                tb_lines = traceback.format_exception(type(error), error, error.__traceback__)
                tb_text = "".join(tb_lines)

                error_msg = "**App Command Error**\n"
                cmd_name = interaction.command.name if interaction.command else "Unknown"
                error_msg += f"Command: `{cmd_name}`\n"
                error_msg += f"User: {interaction.user.mention} ({interaction.user.id})\n"
                channel_mention = interaction.channel.mention if interaction.channel else "Unknown"
                error_msg += f"Channel: {channel_mention}\n\n"
                error_msg += f"```python\n{tb_text}\n```"

                channel = bot.get_channel(ERROR_CHANNEL_ID)
                if channel and isinstance(channel, discord.TextChannel):
                    if len(error_msg) > 2000:
                        # Send header
                        header = "**App Command Error**\n"
                        cmd_name = interaction.command.name if interaction.command else "Unknown"
                        header += f"Command: `{cmd_name}`\n"
                        header += f"User: {interaction.user.mention} ({interaction.user.id})\n"
                        channel_mention = (
                            interaction.channel.mention if interaction.channel else "Unknown"
                        )
                        header += f"Channel: {channel_mention}\n"
                        await channel.send(header)
                        # Send traceback in chunks
                        chunks = [tb_text[i : i + 1900] for i in range(0, len(tb_text), 1900)]
                        for chunk in chunks:
                            await channel.send(f"```python\n{chunk}\n```")
                    else:
                        await channel.send(error_msg)
                else:
                    logger.warning(
                        f"Error channel {ERROR_CHANNEL_ID} not found or not a text channel"
                    )
            except Exception as e:
                logger.error(f"Failed to send app command error to channel {ERROR_CHANNEL_ID}: {e}")

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
    await FeatureFlagsRepository.initialize_cache()
    await _disable_features_for_local_env()

    # Load extensions
    if APP_ENV != "local":
        await _load_extensions(bot)

    # Start bot in background
    _bot_instance = bot
    bot_task = asyncio.create_task(bot.start(TOKEN))

    try:
        # Wait for bot to be ready
        while not bot.is_ready():
            await asyncio.sleep(0.1)

        logger.info("🤖 Discord bot is ready and connected!")
        yield bot

    finally:
        # Cleanup
        logger.info("🛑 Shutting down Discord bot...")
        await bot.close()
        await bot_task
        _bot_instance = None
        logger.info("✅ Discord bot shutdown complete")
