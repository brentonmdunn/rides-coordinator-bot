# jobs/csv_runner.py

import csv
import io
import os

import aiohttp
import discord
from cogs_disabled.retreat import Col

from app.core.enums import ChannelIds
from app.core.logger import logger
from app.utils.constants import GUILD_ID
from app.utils.parsing import parse_discord_username


async def logic(reader, bot):
    guild = bot.get_guild(GUILD_ID)
    for row in reader:
        if "no" in row[Col.NEED_RIDE].lower():
            username = parse_discord_username(row[Col.DISCORD_USERNAME])
            role_name = "retreat driver"

            role = discord.utils.get(guild.roles, name=role_name)

            # Try matching by both .name and .display_name, case-insensitive
            member = discord.utils.find(
                lambda m, username=username: (
                    m.name.lower() == username.lower() or m.display_name.lower() == username.lower()
                ),
                guild.members,
            )

            channel = bot.get_channel(ChannelIds.SERVING__RETREAT_BOT_SPAM)

            if member is None:
                # logger.info(f"⚠️ Could not find member with username: {username}")
                if channel:
                    await channel.send(
                        f"⚠️ Could not find member with username: {username}",
                    )
                continue
            elif role is None:
                # logger.info(f"⚠️ Role '{role_name}' not found.")
                continue
            elif role in member.roles:
                # logger.info(f"⚠️ {username} already has '{role_name}' role.")
                continue
            else:
                await member.add_roles(role)
                # logger.info(f"✅ Added role '{role_name}' to {member.display_name}")

                if channel:
                    await channel.send(
                        f"✅ Added role '{role_name}' to {member.display_name}",
                    )


async def fetch_csv(bot):
    url = os.getenv("RETREAT_CSV_URL")
    try:
        async with aiohttp.ClientSession() as session, session.get(url) as resp:
            if resp.status == 200:
                content = await resp.text()
                return csv.reader(io.StringIO(content))
            else:
                logger.info(f"❌ Failed to fetch CSV: HTTP {resp.status}")
    except Exception as e:
        channel = bot.get_channel(ChannelIds.SERVING__RETREAT_BOT_SPAM)
        if channel:
            await channel.send(f"⚠️ Error fetching CSV: {e}")
    return None


async def run_csv_job(bot):
    reader = await fetch_csv(bot)
    if reader:
        await logic(reader, bot)
