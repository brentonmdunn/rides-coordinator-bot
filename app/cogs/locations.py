import os
from collections import defaultdict
from datetime import datetime, timedelta

import discord
from discord.ext import commands
from dotenv import load_dotenv

from app.core.enums import ChannelIds, FeatureFlagNames
from app.core.logger import logger
from app.utils.checks import feature_flag_enabled
from app.utils.lookups import get_location, get_name_location_no_sync, sync

load_dotenv()

LSCC_PPL_CSV_URL = os.getenv("LSCC_PPL_CSV_URL")

# List of scholars housing locations
SCHOLARS_LOCATIONS = ["revelle", "muir", "sixth", "marshall", "erc", "seventh", "new marshall"]

LOCATIONS_CHANNELS_WHITELIST = [
    ChannelIds.SERVING__DRIVER_BOT_SPAM,
    ChannelIds.SERVING__LEADERSHIP,
    ChannelIds.SERVING__DRIVER_CHAT_WOOOOO,
    ChannelIds.BOT_STUFF__BOTS,
    ChannelIds.BOT_STUFF__BOT_SPAM_2,
]


class Locations(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @discord.app_commands.command(
        name="sync-locations",
        description="Sync Google Sheets with database.",
    )
    @feature_flag_enabled(FeatureFlagNames.BOT)
    async def sync_locations(self, interaction: discord.Interaction):
        from app.utils.lookups import sync

        await sync()
        await interaction.response.send_message("Sync complete")

    @discord.app_commands.command(
        name="pickup-location",
        description="Pickup location for a person (name or Discord username).",
    )
    @feature_flag_enabled(FeatureFlagNames.BOT)
    async def pickup_location(self, interaction: discord.Interaction, name: str):
        """Finds and sends a pickup location for a given person."""
        logger.info(
            f"pickup-location command used by {interaction.user} in #{interaction.channel}",
        )

        if interaction.channel_id not in LOCATIONS_CHANNELS_WHITELIST:
            await interaction.response.send_message(
                "Command cannot be used in this channel.",
                ephemeral=True,
            )
            logger.info(
                f"pickup-location not allowed in #{interaction.channel} by {interaction.user}",
            )
            return

        possible_people: list[tuple[str, str]] | None = await get_location(name)

        if not possible_people:
            await interaction.response.send_message("No people found.")
            return

        output = "\n".join(f"{n}: {loc}" for n, loc in possible_people)
        await interaction.response.send_message(output)

    @discord.app_commands.command(
        name="list-pickups-sunday",
        description="List pickups for Sunday service.",
    )
    @feature_flag_enabled(FeatureFlagNames.BOT)
    async def list_locations_sunday(self, interaction: discord.Interaction):
        await self._list_locations(interaction, day="sunday")

    @discord.app_commands.command(
        name="list-pickups-friday",
        description="List pickups for Friday fellowship.",
    )
    @feature_flag_enabled(FeatureFlagNames.BOT)
    async def list_locations_friday(self, interaction: discord.Interaction):
        await self._list_locations(interaction, day="friday")

    @discord.app_commands.command(
        name="list-pickups-by-message-id",
        description="List pickups using a specific message ID.",
    )
    @discord.app_commands.describe(
        message_id="The message ID to fetch pickups from",
        channel_id="Optional channel ID where the message is located",
    )
    @feature_flag_enabled(FeatureFlagNames.BOT)
    async def list_locations_unknown(
        self,
        interaction: discord.Interaction,
        message_id: str,
        channel_id: str | None = None,
    ):
        if channel_id:
            await self._list_locations(
                interaction,
                message_id=message_id,
                channel_id=channel_id,
            )
        else:
            await self._list_locations(interaction, message_id=message_id)

    def _get_last_sunday(self):
        now = datetime.now()
        if now.weekday() == 6:
            return now - timedelta(days=7)
        else:
            return now - timedelta(days=(now.weekday() + 1))

    async def _find_correct_message(self, day) -> str | None:
        """
        Returns message id of message corresponding to day.

        Args:
            day

        Returns:
            channel id (str) if found, otherwise None
        """
        last_sunday = self._get_last_sunday()
        channel = self.bot.get_channel(ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS)
        most_recent_message = None

        if not channel:
            return None

        async for message in channel.history(after=last_sunday):
            if (
                day in message.content.lower()
                and "react" in message.content.lower()
                and "class" not in message.content.lower()
            ):
                most_recent_message = message
        if not most_recent_message:
            return None
        message_id = most_recent_message.id
        return message_id

    async def _list_locations(
        self,
        interaction,
        day=None,
        message_id=None,
        channel_id=ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS,
    ):
        logger.info(
            f"list-pickups command used by {interaction.user} in #{interaction.channel}",
        )

        if interaction.channel_id not in LOCATIONS_CHANNELS_WHITELIST:
            await interaction.response.send_message(
                "Command cannot be used in this channel.",
                ephemeral=True,
            )
            logger.info(
                f"list-pickups not allowed in #{interaction.channel} by {interaction.user}",
            )
            return

        if (day is None and message_id is None) or (day is not None and message_id is not None):
            await interaction.response.send_message("Please provide either day or message ID")
            return

        # Find the relevant message
        if day:
            message_id = await self._find_correct_message(interaction, day)
            if message_id is None:
                await interaction.response.send_message("No matching message found.")
                return

        usernames_reacted = set()
        channel = self.bot.get_channel(int(channel_id))
        try:
            message = await channel.fetch_message(int(message_id))
            for reaction in message.reactions:
                async for user in reaction.users():
                    usernames_reacted.add(user)
        except Exception as e:
            logger.info(f"Error fetching message: {e}")
            await interaction.response.send_message("Failed to fetch message.")
            return

        locations_people = defaultdict(list)
        location_found = set()

        cache_miss = []
        for username in usernames_reacted:
            person = await get_name_location_no_sync(username)

            if person is None or person.location is None:
                cache_miss.append(username)
                continue
            locations_people[person.location].append(person.name)
            location_found.add(username)

        if cache_miss:
            await sync()
            for username in cache_miss:
                person = await get_name_location_no_sync(username)
                if person is None or person.location is None:
                    continue

                locations_people[person.location].append(person.name)
                location_found.add(username)

        # Build Embed
        embed = discord.Embed(title="Housing Breakdown", color=discord.Color.blue())

        groups = {
            "Scholars (no Eighth)": {
                "count": 0,
                "people": "",
                "filter": SCHOLARS_LOCATIONS,
                "emoji": "🏫",
            },
            "Warren + Pepper Canyon": {
                "count": 0,
                "people": "",
                "filter": [
                    "warren",
                    "pcyn",
                    "pce",
                    "pcw",
                    "pepper canyon east",
                    "pepper canyon west",
                ],
                "emoji": "🏠",
            },
            "Rita + Eighth": {
                "count": 0,
                "people": "",
                "filter": ["rita", "eighth"],
                "emoji": "🏡",
            },
            "Off Campus": {"count": 0, "people": "", "filter": [], "emoji": "🌍"},
        }

        for location, people in locations_people.items():
            matched = False
            for _, group_data in groups.items():
                if any(keyword in location.lower() for keyword in group_data["filter"]):
                    group_data["count"] += len(people)
                    group_data["people"] += f"**({len(people)}) {location}:** {', '.join(people)}\n"
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
                    name=f"{group_data['emoji']} [{group_data['count']}] {group_name}",
                    value=group_data["people"],
                    inline=False,
                )

        unknown_location = set(usernames_reacted) - location_found
        if unknown_location:
            unknown_names = [str(user) for user in unknown_location]
            embed.add_field(
                name=f"❓ [{len(unknown_names)}] Unknown Location",
                value=", ".join(unknown_names)
                + "\n(Make sure their Discord username is correct in the sheet!)",
                inline=False,
            )

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Locations(bot))
