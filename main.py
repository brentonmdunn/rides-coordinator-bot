import asyncio
import os

import discord
from discord import Interaction
from discord.app_commands import AppCommandError, CheckFailure
from discord.ext import commands
from discord.ext.commands import Bot
from dotenv import load_dotenv

from database import init_db

load_dotenv()
TOKEN: str | None = os.getenv("TOKEN")

intents: discord.Intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.reactions = True
intents.members = True

bot: Bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready() -> None:
    print(f"✅ Logged in as {bot.user}!")
    print(f"🛠️  Synced {len(await bot.tree.sync())} slash commands.")

    for guild in bot.guilds:
        try:
            members: list[discord.Member] = []
            async for member in guild.fetch_members(limit=None):
                members.append(member)
            print(f"📥 Cached {len(members)} members in '{guild.name}'")
        except Exception as e:
            print(f"❌ Failed to fetch members for guild '{guild.name}': {e}")


async def load_extensions() -> None:
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py") and not filename.startswith("_"):
            extension: str = f"cogs.{filename[:-3]}"
            try:
                await bot.load_extension(extension)
                print(f"Loaded extension: {extension}")
            except Exception as e:
                print(f"❌ Failed to load extension {extension}: {e}")


@bot.tree.error
async def on_app_command_error(
    interaction: Interaction,
    error: AppCommandError,
) -> None:
    if isinstance(error, CheckFailure):
        await interaction.response.send_message(
            "❌ You must be a server admin to use this command.",
            ephemeral=True,
        )
    else:
        raise error


async def main() -> None:
    async with bot:
        await init_db()
        await load_extensions()
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
