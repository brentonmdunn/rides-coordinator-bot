# jobs/csv_runner.py

import aiohttp
import csv
import io
import os
from utils.constants import GUILD_ID
from utils.parsing import parse_discord_username
from cogs.retreat import Col
import discord
from enums import ChannelIds


async def logic(reader, bot):
    guild = bot.get_guild(GUILD_ID)
    for row in reader:
        if "no" in row[Col.NEED_RIDE].lower():
            username = parse_discord_username(row[Col.DISCORD_USERNAME])
            role_name = "retreat driver"

            role = discord.utils.get(guild.roles, name=role_name)

            # Try matching by both .name and .display_name, case-insensitive
            member = discord.utils.find(
                lambda m: m.name.lower() == username.lower()
                or m.display_name.lower() == username.lower(),
                guild.members,
            )

            channel = bot.get_channel(ChannelIds.SERVING__RETREAT_BOT_SPAM)

            if member is None:
                # print(f"⚠️ Could not find member with username: {username}")
                if channel:
                    await channel.send(
                        f"⚠️ Could not find member with username: {username}"
                    )
                continue
            elif role is None:
                # print(f"⚠️ Role '{role_name}' not found.")
                continue
            elif role in member.roles:
                # print(f"⚠️ {username} already has '{role_name}' role.")
                continue
            else:
                await member.add_roles(role)
                # print(f"✅ Added role '{role_name}' to {member.display_name}")

                if channel:
                    await channel.send(
                        f"✅ Added role '{role_name}' to {member.display_name}"
                    )


async def fetch_csv(bot):
    url = os.getenv("RETREAT_CSV_URL")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    content = await resp.text()
                    return csv.reader(io.StringIO(content))
                else:
                    print(f"❌ Failed to fetch CSV: HTTP {resp.status}")
    except Exception as e:
        channel = bot.get_channel(ChannelIds.SERVING__RETREAT_BOT_SPAM)
        if channel:
            channel.send(f"⚠️ Error fetching CSV: {e}")
    return None


async def run_csv_job(bot):
    reader = await fetch_csv(bot)
    if reader:
        await logic(reader, bot)
