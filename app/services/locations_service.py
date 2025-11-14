# app/features/locations/locations_service.py

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Literal

import discord

from app.core.enums import AskRidesMessage, ChannelIds
from app.core.logger import logger
from app.repositories.locations_repository import LocationsRepository
from app.utils.custom_exceptions import NoMatchingMessageFoundError, NotAllowedInChannelError
from app.utils.lookups import get_location, get_name_location_no_sync, sync
from app.utils.parsing import get_message_and_embed_content

RideOptionsSchema = Literal[
    "Sunday pickup", "Sunday dropoff back", "Sunday dropoff lunch", "Friday"
]

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


class LocationsService:
    def __init__(self, bot):
        self.bot = bot
        self.repo = LocationsRepository()

    async def sync_locations(self):
        await sync()

    async def pickup_location(self, name: str) -> str:
        possible_people = await get_location(name)
        if not possible_people:
            return "No people found."
        return "\n".join(f"{n}: {loc}" for n, loc in possible_people)

    async def list_locations_wrapper(
        self,
        interaction,
        day=None,
        message_id=None,
        channel_id=ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS,
        option=None,
    ):
        try:
            args = await self.list_locations(day, message_id, channel_id, option)
            embed = self._build_embed(*args, option=option)
            if day and option and "dropoff" in option.lower():
                non_discord = await self.repo.get_non_discord_pickups(day)
                if non_discord:
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

    async def list_locations(
        self,
        day=None,
        message_id=None,
        channel_id=ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS,
        option=None,
    ):
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

        locations_people, location_found = await self._sort_locations(usernames_reacted)

        if day and (option is None or "dropoff" not in option.lower()):
            pickups = await self.repo.get_non_discord_pickups(day)
            for pickup in pickups:
                locations_people[pickup.location].append((pickup.name, None))

        return locations_people, usernames_reacted, location_found

    def _get_last_sunday(self):
        now = datetime.now()
        days_to_subtract = (now.weekday() + 1) % 7
        if days_to_subtract == 0:
            days_to_subtract = 7
        return now - timedelta(days=days_to_subtract)

    async def _find_correct_message(self, ask_rides_message: AskRidesMessage, channel_id):
        last_sunday = self._get_last_sunday()
        channel = self.bot.get_channel(channel_id)
        most_recent_message = None
        if not channel:
            return None
        async for message in channel.history(after=last_sunday):
            combined_text = get_message_and_embed_content(message, message_content=False)
            if ask_rides_message.lower() in combined_text.lower():
                most_recent_message = message
        return most_recent_message.id if most_recent_message else None

    async def _get_usernames_who_reacted(self, channel_id, message_id, option=None):
        usernames_reacted = set()
        channel = self.bot.get_channel(int(channel_id))
        message = await channel.fetch_message(int(message_id))
        for reaction in message.reactions:
            if option and option == "Sunday dropoff back" and (str(reaction.emoji) in ["🍔", "✳️"]):
                continue
            if option and option == "Sunday dropoff lunch" and (str(reaction.emoji) in ["🏠", "✳️"]):
                continue
            async for user in reaction.users():
                if not user.bot:
                    usernames_reacted.add(user)
        return usernames_reacted

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
                if person and person.location:
                    locations_people[person.location].append((person.name, username))
                    location_found.add(username)
        return locations_people, location_found

    def _build_embed(
        self, locations_people, usernames_reacted, location_found, option=None, custom_title=None
    ):
        title = "Housing Breakdown"
        if option:
            title += f" ({option})"
        embed = discord.Embed(
            title=title if custom_title is None else custom_title, color=discord.Color.blue()
        )

        groups = {
            "Scholars": {"count": 0, "people": "", "filter": SCHOLARS_LOCATIONS, "emoji": "🏫"},
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
            "Rita": {"count": 0, "people": "", "filter": ["rita"], "emoji": "🏡"},
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
