"""Main entry point for the bot."""

import asyncio
import os
from pathlib import Path

import discord
from discord import Interaction
from discord.app_commands import AppCommandError, CheckFailure
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


intents: discord.Intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.reactions = True
intents.members = True

bot: Bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready() -> None:
    """Log when the bot is ready and synced."""

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


async def load_extensions() -> None:
    """Load all cogs from the bot/cogs directory."""

    cogs_path = Path.cwd() / "bot" / "cogs"
    priority_filename = "job_scheduler.py"

    eligible_files = [
        filename
        for filename in cogs_path.iterdir()
        if filename.is_file() and filename.suffix == ".py" and not filename.name.startswith("_")
    ]

    # Sort files, ensuring job_scheduler.py is always first,
    # and the rest are sorted alphabetically.
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
        raise error


async def disable_features_for_local_env():
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


async def main() -> None:
    """Run the bot."""

    async with bot:
        await init_db()
        async with AsyncSessionLocal() as session:
            await seed_feature_flags(session)
        await FeatureFlagsRepository.initialize_cache()
        await disable_features_for_local_env()
        await load_extensions()
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
