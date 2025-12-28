"""
Bot API Access Layer

This module provides access to the Discord bot instance for the FastAPI application.
It manages the bot lifecycle and allows API endpoints to interact with Discord.
"""

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

import discord
from discord.ext import commands
from discord.ext.commands import Bot
from dotenv import load_dotenv
from sqlalchemy import or_, update

from bot.core.database import AsyncSessionLocal, init_db, seed_feature_flags
from bot.core.logger import logger
from bot.core.models import FeatureFlags
from bot.repositories.feature_flags_repository import FeatureFlagsRepository

load_dotenv()
TOKEN: str | None = os.getenv("TOKEN")
APP_ENV: str = os.getenv("APP_ENV", "local")

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

    # Initialize database and feature flags
    await init_db()
    async with AsyncSessionLocal() as session:
        await seed_feature_flags(session)
    await FeatureFlagsRepository.initialize_cache()
    await _disable_features_for_local_env()

    # Load extensions
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
