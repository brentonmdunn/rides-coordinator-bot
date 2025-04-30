import os
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.reactions = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}!")
    print(f"🛠️  Synced {len(await bot.tree.sync())} slash commands.")

    for guild in bot.guilds:
        try:
            members = []
            async for member in guild.fetch_members(limit=None):
                members.append(member)
            print(f"📥 Cached {len(members)} members in '{guild.name}'")
        except Exception as e:
            print(f"❌ Failed to fetch members for guild '{guild.name}': {e}")


async def load_extensions():
    # Scan the "cogs" folder for all .py files
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py") and not filename.startswith("_"):
            extension = f"cogs.{filename[:-3]}"  # remove '.py' from filename
            try:
                await bot.load_extension(extension)
                print(f"Loaded extension: {extension}")
            except Exception as e:
                print(f"❌ Failed to load extension {extension}: {e}")


async def main():
    async with bot:
        await load_extensions()
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
