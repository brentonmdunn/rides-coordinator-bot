"""Service for grouping locations into housing categories and building embeds."""

import logging

import discord

from bot.core.enums import Emoji

logger = logging.getLogger(__name__)

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


class HousingGroupService:
    """Groups location data into housing categories and builds Discord embeds."""

    def group_locations_by_housing(self, locations_people, usernames_reacted, location_found):
        """
        Groups locations into housing categories.

        Args:
            locations_people: Dictionary mapping locations to people.
            usernames_reacted: Set of all usernames who reacted.
            location_found: Set of usernames whose location was found.

        Returns:
            A dictionary with housing groups and unknown users.
        """
        housing_groups = {
            "Scholars": {
                "count": 0,
                "locations": {},
                "filter": SCHOLARS_LOCATIONS,
                "emoji": Emoji.SCHOOL,
            },
            "Warren + Pepper Canyon": {
                "count": 0,
                "locations": {},
                "filter": [
                    "warren",
                    "pcyn",
                    "pce",
                    "pcw",
                    "pepper canyon east",
                    "pepper canyon west",
                ],
                "emoji": Emoji.HOUSE,
            },
            "Rita": {
                "count": 0,
                "locations": {},
                "filter": ["rita"],
                "emoji": Emoji.HOUSE_WITH_GARDEN,
            },
            "Off Campus": {"count": 0, "locations": {}, "filter": [], "emoji": Emoji.GLOBE},
        }

        for location, people_username_list in locations_people.items():
            people = people_username_list
            matched = False

            for _, group_data in housing_groups.items():
                if any(keyword in location.lower() for keyword in group_data["filter"]):
                    group_data["count"] += len(people)
                    group_data["locations"][location] = people
                    matched = True
                    break

            if not matched:
                housing_groups["Off Campus"]["count"] += len(people)
                housing_groups["Off Campus"]["locations"][location] = people

        unknown_location = set(usernames_reacted) - location_found
        unknown_users = [str(user) for user in unknown_location] if unknown_location else []

        return {"groups": housing_groups, "unknown_users": unknown_users}

    def build_embed(
        self, locations_people, usernames_reacted, location_found, option=None, custom_title=None
    ):
        """
        Builds a Discord embed displaying location breakdowns.

        Args:
            locations_people: Dictionary mapping locations to people.
            usernames_reacted: Set of all usernames who reacted.
            location_found: Set of usernames whose location was found.
            option: Optional filter option string.
            custom_title: Optional custom title for the embed.

        Returns:
            A Discord Embed object.
        """
        title = "Housing Breakdown"
        if option:
            title += f" ({option})"
        embed = discord.Embed(
            title=title if custom_title is None else custom_title, color=discord.Color.blue()
        )

        grouped_data = self.group_locations_by_housing(
            locations_people, usernames_reacted, location_found
        )

        for group_name, group_data in grouped_data["groups"].items():
            if group_data["count"] > 0:
                people_str = ""
                for location, people in group_data["locations"].items():
                    people_names = [p[0] for p in people]
                    people_str += f"**({len(people)}) {location}:** {', '.join(people_names)}\n"

                embed.add_field(
                    name=f"{group_data['emoji']} [{group_data['count']}] {group_name}",
                    value=people_str,
                    inline=False,
                )

        if grouped_data["unknown_users"]:
            embed.add_field(
                name=f"❓ [{len(grouped_data['unknown_users'])}] Unknown Location",
                value=", ".join(grouped_data["unknown_users"])
                + "\n(Make sure their Discord username is correct in the sheet!)",
                inline=False,
            )

        return embed
