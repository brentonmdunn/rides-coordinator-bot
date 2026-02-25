"""Main entry point for the bot."""

import asyncio
import os
import traceback
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
from bot.core.enums import ChannelIds
from bot.core.logger import logger
from bot.core.models import FeatureFlags
from bot.repositories.feature_flags_repository import FeatureFlagsRepository

try:
    from bot.utils.constants import ERROR_CHANNEL_ID
except ImportError:
    logger.warning("❌ Could not import ERROR_CHANNEL_ID. Defaulting to BOT_STUFF__BOTS.")
    ERROR_CHANNEL_ID = ChannelIds.BOT_STUFF__BOTS

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
        # Log the error
        logger.error(f"App command error: {error}", exc_info=error)

        # Send error to the user
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ An error occurred while processing this command.",
                    ephemeral=True,
                )
                logger.info("✅ Sent error response to user")
            else:
                await interaction.followup.send(
                    "❌ An error occurred while processing this command.",
                    ephemeral=True,
                )
                logger.info("✅ Sent error followup to user")
        except Exception as user_msg_error:
            logger.warning(f"❌ Failed to send error message to user: {user_msg_error}")

        # Send to error channel
        try:
            logger.info(f"🔍 Attempting to send error to channel {ERROR_CHANNEL_ID}")
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
            channel = bot.get_channel(ERROR_CHANNEL_ID)
            if channel and isinstance(channel, discord.TextChannel):
                logger.info(f"🔍 Sending to channel, message length: {len(error_msg)}")
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
                    logger.info(f"✅ Sent error to channel in {len(chunks) + 1} messages")
                else:
                    await channel.send(error_msg)
                    logger.info("✅ Sent error to channel in 1 message")
            else:
                logger.warning(f"Error channel {ERROR_CHANNEL_ID} not found or not a text channel")
        except Exception as e:
            logger.error(
                f"❌ Failed to send app command error to channel {ERROR_CHANNEL_ID}: {e}",
                exc_info=e,
            )


@bot.event
async def on_error(event: str, *args, **kwargs) -> None:
    """Handle uncaught exceptions and send them to the error channel."""

    # Format the full traceback
    error_msg = f"**Uncaught Exception in Event: `{event}`**\n\n"

    # Get the full exception details from sys.exc_info() equivalent
    import sys

    exc_info = sys.exc_info()

    if exc_info[0] is not None:
        tb_lines = traceback.format_exception(*exc_info)
        tb_text = "".join(tb_lines)

        # Discord has a 2000 character limit for messages
        # Split into multiple messages if needed
        error_msg += f"```python\n{tb_text}\n```"

        # Log the error
        logger.error(f"Uncaught exception in {event}: {tb_text}")

        # Send to error channel
        try:
            channel = bot.get_channel(ERROR_CHANNEL_ID)
            if channel and isinstance(channel, discord.TextChannel):
                # Split message if too long
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
                logger.warning(f"Error channel {ERROR_CHANNEL_ID} not found or not a text channel")
        except Exception as e:
            logger.error(f"Failed to send error to channel {ERROR_CHANNEL_ID}: {e}")
    else:
        logger.error(f"Unknown error in event {event}")


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
        # Initialize cache backend (Redis for prod/preprod, in-memory for local)
        if APP_ENV != "local":
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
            from bot.utils.cache_backends import RedisBackend, set_backend

            set_backend(RedisBackend(redis_url))

        await init_db()
        async with AsyncSessionLocal() as session:
            await seed_feature_flags(session)
        async with AsyncSessionLocal() as session:
            await seed_message_schedule_pauses(session)
        await FeatureFlagsRepository.initialize_cache()
        await disable_features_for_local_env()
        await load_extensions()
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
