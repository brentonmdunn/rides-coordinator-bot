import os
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Literal

import discord
from discord.ext import commands
from dotenv import load_dotenv
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.enums import (
    AskRidesMessage,
    ChannelIds,
    FeatureFlagNames,
)
from app.core.logger import log_cmd, logger
from app.core.models import NonDiscordRides
from app.utils.channel_whitelist import LOCATIONS_CHANNELS_WHITELIST, cmd_is_allowed
from app.utils.checks import feature_flag_enabled
from app.utils.constants import MAP_LINKS
from app.utils.custom_exceptions import NoMatchingMessageFoundError, NotAllowedInChannelError
from app.utils.lookups import get_location, get_name_location_no_sync, sync
from app.utils.parsing import get_message_and_embed_content
from app.utils.time_helpers import get_next_date_obj

load_dotenv()

LSCC_PPL_CSV_URL = os.getenv("LSCC_PPL_CSV_URL")

# List of scholars housing locations
SCHOLARS_LOCATIONS = [
    "revelle",
    "muir",
    "sixth",
    "marshall",
    "erc",
    "seventh",
    "new marshall",
    "eighth",
]

RideOptionsSchema = Literal[
    "Sunday pickup", "Sunday dropoff back", "Sunday dropoff lunch", "Friday"
]


class Locations(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @discord.app_commands.command(
        name="sync-locations",
        description="Sync Google Sheets with database.",
    )
    @feature_flag_enabled(FeatureFlagNames.BOT)
    @log_cmd
    async def sync_locations(self, interaction: discord.Interaction):
        from app.utils.lookups import sync

        await sync()
        await interaction.response.send_message("Sync complete")

    @discord.app_commands.command(
        name="pickup-location",
        description="Pickup location for a person (name or Discord username).",
    )
    @feature_flag_enabled(FeatureFlagNames.BOT)
    @log_cmd
    async def pickup_location(self, interaction: discord.Interaction, name: str):
        """Finds and sends a pickup location for a given person."""
        if not await cmd_is_allowed(
            interaction, interaction.channel_id, LOCATIONS_CHANNELS_WHITELIST
        ):
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
    @log_cmd
    async def list_pickups_sunday(self, interaction: discord.Interaction):
        if not await cmd_is_allowed(
            interaction, interaction.channel_id, LOCATIONS_CHANNELS_WHITELIST
        ):
            return

        await self._list_locations_wrapper(interaction, day="sunday", option="Sunday pickup")

    @discord.app_commands.command(
        name="list-dropoffs-sunday-back",
        description="List dropoffs after Sunday service no lunch.",
    )
    @feature_flag_enabled(FeatureFlagNames.BOT)
    @log_cmd
    async def list_dropoffs_sunday_back(self, interaction: discord.Interaction):
        if not await cmd_is_allowed(
            interaction, interaction.channel_id, LOCATIONS_CHANNELS_WHITELIST
        ):
            return

        await self._list_locations_wrapper(interaction, day="sunday", option="Sunday dropoff back")

    @discord.app_commands.command(
        name="list-dropoffs-sunday-lunch",
        description="List dropoffs after Sunday service lunch.",
    )
    @feature_flag_enabled(FeatureFlagNames.BOT)
    @log_cmd
    async def list_dropoffs_sunday_lunch(self, interaction: discord.Interaction):
        if not await cmd_is_allowed(
            interaction, interaction.channel_id, LOCATIONS_CHANNELS_WHITELIST
        ):
            return

        await self._list_locations_wrapper(interaction, day="sunday", option="Sunday dropoff lunch")

    @discord.app_commands.command(
        name="list-pickups-friday",
        description="List pickups for Friday fellowship.",
    )
    @feature_flag_enabled(FeatureFlagNames.BOT)
    @log_cmd
    async def list_locations_friday(self, interaction: discord.Interaction):
        if not await cmd_is_allowed(
            interaction, interaction.channel_id, LOCATIONS_CHANNELS_WHITELIST
        ):
            return

        await self._list_locations_wrapper(interaction, day="friday")

    @discord.app_commands.command(
        name="list-pickups-by-message-id",
        description="List pickups using a specific message ID.",
    )
    @discord.app_commands.describe(
        message_id="The message ID to fetch pickups from",
        channel_id="Optional channel ID where the message is located",
    )
    @feature_flag_enabled(FeatureFlagNames.BOT)
    @log_cmd
    async def list_locations_unknown(
        self,
        interaction: discord.Interaction,
        message_id: str,
        channel_id: str | None = None,
    ):
        if not await cmd_is_allowed(
            interaction, interaction.channel_id, LOCATIONS_CHANNELS_WHITELIST
        ):
            return

        if channel_id:
            await self._list_locations_wrapper(
                interaction,
                message_id=message_id,
                channel_id=channel_id,
            )
        else:
            await self._list_locations_wrapper(interaction, message_id=message_id)

    def _get_last_sunday(self):
        now = datetime.now()
        if now.weekday() == 6:
            return now - timedelta(days=7)
        else:
            return now - timedelta(days=(now.weekday() + 1))

    async def _find_correct_message(
        self,
        ask_rides_message: AskRidesMessage,
        channel_id=ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS,
    ) -> str | None:
        """
        Returns message id of message corresponding to day.

        Args:
            ask_rides_message

        Returns:
            message id (str) if found, otherwise None
        """
        last_sunday = self._get_last_sunday()
        channel = self.bot.get_channel(channel_id)
        most_recent_message = None

        if not channel:
            return None

        async for message in channel.history(after=last_sunday):
            combined_text = get_message_and_embed_content(message)
            if ask_rides_message.lower() in combined_text.lower():
                most_recent_message = message
        if not most_recent_message:
            return None
        message_id = most_recent_message.id
        return message_id

    def _build_embed(
        self,
        locations_people,
        usernames_reacted,
        location_found,
        option: RideOptionsSchema | None = None,
        custom_title: str | None = None,
    ):
        """Builds a Discord embed based on grouped locations and people."""
        title = "Housing Breakdown"
        if option:
            title += f" ({option})"
        embed = discord.Embed(
            title=title if custom_title is None else custom_title, color=discord.Color.blue()
        )

        groups = {
            "Scholars": {
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
            "Rita": {
                "count": 0,
                "people": "",
                "filter": ["rita"],
                "emoji": "🏡",
            },
            "Off Campus": {"count": 0, "people": "", "filter": [], "emoji": "🌍"},
        }

        for location, people_username_list in locations_people.items():
            people = [person[0] for person in people_username_list]

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

        return embed

    async def _sort_locations(self, usernames_reacted):
        locations_people = defaultdict(list)
        location_found = set()

        cache_miss = []
        for username in usernames_reacted:
            person = await get_name_location_no_sync(username)

            if person is None or person.location is None:
                cache_miss.append(username)
                continue
            locations_people[person.location].append((person.name, username))
            location_found.add(username)

        if cache_miss:
            await sync()
            for username in cache_miss:
                person = await get_name_location_no_sync(username)
                if person is None or person.location is None:
                    continue

                locations_people[person.location].append((person.name, username))
                location_found.add(username)
        return locations_people, location_found

    async def _get_usernames_who_reacted(
        self,
        channel_id,
        message_id,
        option: RideOptionsSchema | None = None,
    ):
        usernames_reacted = set()
        channel = self.bot.get_channel(int(channel_id))
        message = await channel.fetch_message(int(message_id))
        for reaction in message.reactions:
            # if option and option == "Sunday pickup":
            #     continue
            if (
                option
                and option == "Sunday dropoff back"
                and (str(reaction.emoji) == "🍔" or str(reaction.emoji) == "✳️")
            ):
                continue
            if (
                option
                and option == "Sunday dropoff lunch"
                and (str(reaction.emoji) == "🏠" or str(reaction.emoji) == "✳️")
            ):
                continue
            async for user in reaction.users():
                if user.bot:
                    continue
                usernames_reacted.add(user)
        return usernames_reacted

    async def _get_non_discord_pickups(self, day) -> list[NonDiscordRides]:
        date_to_list = get_next_date_obj(day.title())
        # non discord additions
        async with AsyncSessionLocal() as session:
            try:
                stmt = select(NonDiscordRides).where(NonDiscordRides.date == date_to_list)
                result = await session.execute(stmt)
                pickups = result.scalars().all()

                if pickups:
                    return pickups
                else:
                    pass

            except Exception:
                logger.exception("An error occurred while listing pickups")
        return []

    async def list_locations(
        self,
        day=None,
        message_id=None,
        channel_id=ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS,
        option: RideOptionsSchema | None = None,
    ):
        """
        Gets appropriate rides announcement message and grouped people by location.

        Note: day and message_id have an XOR relationship

        Args:
            day: lowercase day of the week to get rides message for
            message_id: message id of rides announcement message
            channel_id: channel to look for message id

        Returns:
            tuple of:
                - dict[str, [list[tuple[str,str]]]]: dictionary of location that contains a list of
                  people who live there in the tuple form (name, discord.Member)
                - set[str]: set of usernames who reacted to message
                - set[str]: set of usernames who bot found a location for
        """

        # Find the relevant message
        if day:
            if day.lower() == "sunday":
                ask_rides_message = AskRidesMessage.SUNDAY_SERVICE
            elif day.lower() == "friday":
                ask_rides_message = AskRidesMessage.FRIDAY_FELLOWSHIP
            else:
                raise ValueError(f"Invalid day: {day}")
            message_id = await self._find_correct_message(ask_rides_message, channel_id)
            if message_id is None:
                raise NoMatchingMessageFoundError()

        usernames_reacted = await self._get_usernames_who_reacted(channel_id, message_id, option)
        # -----
        # If use message_id instead of day
        # Need to only delete class reacts if doing sunday rides
        tmp_content = ""
        if not day:
            tmp_channel = self.bot.get_channel(int(ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS))
            tmp_message = await tmp_channel.fetch_message(int(message_id))
            tmp_content = get_message_and_embed_content(tmp_message).lower()
        if (
            (day and day.lower() == "sunday")
            or ("service" in tmp_content and "sunday" in tmp_content)
        ) and (
            class_message_id := await self._find_correct_message(
                AskRidesMessage.SUNDAY_CLASS, channel_id
            )
        ) is not None:
            usernames_reacted -= await self._get_usernames_who_reacted(channel_id, class_message_id)
        # -----

        locations_people, location_found = await self._sort_locations(usernames_reacted)

        if day and (option is None or "dropoff" not in option.lower()):
            pickups = await self._get_non_discord_pickups(day)
            for pickup in pickups:
                locations_people[pickup.location].append((pickup.name, None))

        return locations_people, usernames_reacted, location_found

    async def _list_locations_wrapper(
        self,
        interaction,
        day=None,
        message_id=None,
        channel_id=ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS,
        option: RideOptionsSchema | None = None,
    ):
        try:
            args = await self.list_locations(day, message_id, channel_id, option)
            embed = self._build_embed(*args, option=option)
            if day and option and "dropoff" in option.lower():
                non_discord = await self._get_non_discord_pickups(day)
                if non_discord:
                    # do smth
                    non_discord_locations_people = defaultdict(list)

                    for pickup in non_discord:
                        non_discord_locations_people[pickup.location].append((pickup.name, None))

                    await interaction.response.send_message(
                        embeds=[
                            embed,
                            self._build_embed(
                                non_discord_locations_people,
                                set(),
                                set(),
                                custom_title="Non-Discord Dropoffs (unknown lunch)",
                            ),
                        ]
                    )
                    return

            await interaction.response.send_message(embed=embed)
        except NotAllowedInChannelError:
            await interaction.response.send_message("Command not allowed in channel.")
        except NoMatchingMessageFoundError:
            await interaction.response.send_message("No matching message found.")
        except Exception as e:
            logger.exception("An error occurred: ")
            await interaction.response.send_message(f"Unknown error: {e}")

    @discord.app_commands.command(
        name="map-links",
        description="Google Map links for pickups",
    )
    @feature_flag_enabled(FeatureFlagNames.BOT)
    @log_cmd
    async def map_links(self, interaction: discord.Interaction):
        message: list[str] = []
        for location, link in MAP_LINKS.items():
            message.append(f"{location}: <{link}>")
        await interaction.response.send_message("\n".join(message))


async def setup(bot: commands.Bot):
    await bot.add_cog(Locations(bot))
