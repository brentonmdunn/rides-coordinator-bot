import discord
from discord.ext import commands
import requests
import csv
from collections import defaultdict

from enums import ChannelIds
from logger import logger
from enum import IntEnum
from dotenv import load_dotenv
import os
from utils.parsing import parse_discord_username


import aiohttp
import csv
import io
import os
from utils.constants import GUILD_ID


load_dotenv()

RETREAT_CSV_URL = os.getenv("RETREAT_CSV_URL")

# List of scholars housing locations
SCHOLARS_LOCATIONS = ["revelle", "muir", "sixth", "marshall", "erc", "seventh"]

LOCATIONS_CHANNELS_WHITELIST = [
    ChannelIds.SERVING__DRIVER_BOT_SPAM,
    ChannelIds.SERVING__LEADERSHIP,
    ChannelIds.SERVING__DRIVER_CHAT_WOOOOO,
    ChannelIds.BOT_STUFF__BOTS,
    ChannelIds.BOT_STUFF__BOT_SPAM_2,
    ChannelIds.SERVING__RETREAT_BOT_SPAM
]


class Col(IntEnum):
    EMAIL_ADDRESS = 1
    NAME = 2
    DISCORD_USERNAME = 3
    PREFERRED_CONTACT = 4
    NEED_RIDE = 5
    PICKUP_LOCATION = 6
    DRIVER_SPOTS = 8
    LEAVE_TIME = 9


class Retreat(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @discord.app_commands.command(
        name="list-drivers-retreat", description="List drivers for retreat."
    )
    async def list_drivers_retreat(self, interaction: discord.Interaction):
        logger.info(
            f"list-pickups command used by {interaction.user} in #{interaction.channel}"
        )

        if interaction.channel_id not in LOCATIONS_CHANNELS_WHITELIST:
            await interaction.response.send_message(
                "Command cannot be used in this channel.", ephemeral=True
            )
            logger.info(
                f"This command is not allowed in #{interaction.channel} by {interaction.user}"
            )
            return

        # Load CSV
        response = requests.get(RETREAT_CSV_URL)
        if response.status_code != 200:
            await interaction.response.send_message("Failed to retrieve the CSV file.")
            return

        csv_data = response.content.decode("utf-8")
        csv_reader = csv.reader(csv_data.splitlines(), delimiter=",")

        drivers = {}

        for i, row in enumerate(csv_reader):
            if "yes" in row[Col.NEED_RIDE].lower() or i == 0:
                continue
            name = row[Col.NAME]
            spots = row[Col.DRIVER_SPOTS]

            drivers[name] = spots

        # Build Embed
        embed = discord.Embed(
            title="Drivers",
            color=discord.Color.blue(),
        )

        embed.add_field(
            name=f"Total: {len(drivers)}",
            value="\n".join(f"• {spots} - {name}" for name, spots in drivers.items()),
            inline=False,
        )

        await interaction.response.send_message(embed=embed)

    @discord.app_commands.command(
        name="list-pickups-retreat", description="List pickups for retreat."
    )
    async def list_pickups_retreat(self, interaction: discord.Interaction):
        logger.info(
            f"list-pickups command used by {interaction.user} in #{interaction.channel}"
        )

        if interaction.channel_id not in LOCATIONS_CHANNELS_WHITELIST:
            await interaction.response.send_message(
                "Command cannot be used in this channel.", ephemeral=True
            )
            logger.info(
                f"This command is not allowed in #{interaction.channel} by {interaction.user}"
            )
            return

        # Load CSV
        response = requests.get(RETREAT_CSV_URL)
        if response.status_code != 200:
            await interaction.response.send_message("Failed to retrieve the CSV file.")
            return

        csv_data = response.content.decode("utf-8")
        csv_reader = csv.reader(csv_data.splitlines(), delimiter=",")

        locations_people = defaultdict(list)

        for i, row in enumerate(csv_reader):
            if "no" in row[Col.NEED_RIDE].lower() or i == 0:
                continue
            name = row[Col.NAME]
            location = row[Col.PICKUP_LOCATION]
            locations_people[location].append(name)

        # Build Embed
        embed = discord.Embed(title="🏠 Housing Breakdown", color=discord.Color.blue())

        groups = {
            "Scholars (no Eighth)": {
                "count": 0,
                "people": "",
                "filter": SCHOLARS_LOCATIONS,
            },
            "Warren + Pepper Canyon": {
                "count": 0,
                "people": "",
                "filter": ["warren", "pepper canyon"],
            },
            "Rita + Eighth": {"count": 0, "people": "", "filter": ["rita", "eighth"]},
            "Off Campus": {"count": 0, "people": "", "filter": []},
        }

        for location, people in locations_people.items():
            matched = False
            for group_name, group_data in groups.items():
                if any(keyword in location.lower() for keyword in group_data["filter"]):
                    group_data["count"] += len(people)
                    group_data["people"] += (
                        f"**({len(people)}) {location}:** {', '.join(people)}\n"
                    )
                    matched = True
                    break
            if not matched:
                groups["Off Campus"]["count"] += len(people)
                groups["Off Campus"]["people"] += (
                    f"**({len(people)}) {location}:** {', '.join(people)}\n"
                )

        for group_name, group_data in groups.items():
            if group_data["count"] > 0:
                embed.add_field(
                    name=f"{group_name} [{group_data['count']}]",
                    value=group_data["people"],
                    inline=False,
                )

        await interaction.response.send_message(embed=embed)







    @discord.app_commands.command(
        name="test", description="List pickups for retreat."
    )
    async def test(self, interaction: discord.Interaction):


        

        async def logic(reader):
            guild = self.bot.get_guild(GUILD_ID)
            for row in reader:
                if "no" in row[Col.NEED_RIDE].lower():
                    username = parse_discord_username(row[Col.DISCORD_USERNAME])
                    role_name = "retreat driver"

                    role = discord.utils.get(guild.roles, name=role_name)

                    # Try matching by both .name and .display_name, case-insensitive
                    member = discord.utils.find(
                        lambda m: m.name.lower() == username.lower() or m.display_name.lower() == username.lower(),
                        guild.members
                    )

                    if member is None:
                        print(f"⚠️ Could not find member with username: {username}")
                        continue
                    elif role is None:
                        print(f"⚠️ Role '{role_name}' not found.")
                        continue
                    elif role in member.roles:
                        print(f"⚠️ {username} already has '{role_name}' role.")
                        continue
                    else:
                        await member.add_roles(role)
                        print(f"✅ Added role '{role_name}' to {member.display_name}")



        async def fetch_csv():
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
                print(f"⚠️ Error fetching CSV: {e}")
            return None

        async def run_csv_job():
            reader = await fetch_csv()
            if reader:
                await logic(reader)


        await run_csv_job()


        await interaction.response.send_message("Success")

async def setup(bot: commands.Bot):
    await bot.add_cog(Retreat(bot))
