"""Service for driver-related operations."""

import re

import discord
from discord.ext import commands

from app.core.enums import AskRidesMessage, ChannelIds
from app.core.logger import logger
from app.services.locations_service import LocationsService
from app.utils.format_message import ping_user

DETECT_DRIVE_MSG = r"drive.+?\d:\d"


class CheckRidesService:
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.locations_service = LocationsService(bot)

    async def check_pings(
        self,
        message: discord.Message,
        channel_id: int | None = ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS,
    ):
        if str(message.channel.id) == str(channel_id) and re.search(
            DETECT_DRIVE_MSG, message.content
        ):
            # If it is a rides grouping message, check if it has any pings
            logger.debug(f"{message.content=}")

            drive_index = message.content.lower().index("drive") + len("drive")
            content_after_drive = message.content[drive_index:]
            pings = re.findall(r"<@(\d+)>", content_after_drive)
            logger.debug(f"{pings=}")

            # For each ping, double check that user reacted
            msg = await self.locations_service._find_correct_message(
                AskRidesMessage.FRIDAY_FELLOWSHIP, channel_id
            )
            if not msg:
                logger.debug("No message found")
                return

            channel = self.bot.get_channel(channel_id)
            msg_obj = await channel.fetch_message(msg)

            reacted_for_ride = {}

            for reaction in msg_obj.reactions:
                async for user in reaction.users():
                    logger.debug(f"{user=}")
                    logger.debug(f"{type(user.id)=}")
                    reacted_for_ride[str(user.id)] = user

            notif_channel = self.bot.get_channel(ChannelIds.BOT_STUFF__BOTS)

            for ping in pings:
                if ping not in reacted_for_ride:
                    await notif_channel.send(
                        f"Warning: {ping_user(int(ping))} did not react for a ride. "
                        "Did you mean to ping someone else?"
                    )
