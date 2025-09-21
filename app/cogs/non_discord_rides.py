import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.core.database import AsyncSessionLocal
from app.core.enums import (
    CampusLivingLocations,
    DaysOfWeek,
    FeatureFlagNames,
)
from app.core.logger import log_cmd
from app.core.models import NonDiscordRides
from app.utils.channel_whitelist import LOCATIONS_CHANNELS_WHITELIST, cmd_is_allowed
from app.utils.checks import feature_flag_enabled
from app.utils.time_helpers import get_next_date_obj


class NonDiscordRidesCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def day_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        days = [DaysOfWeek.SUNDAY, DaysOfWeek.FRIDAY]
        return [
            app_commands.Choice(name=day, value=day)
            for day in days
            if current.lower() in day.lower()
        ]

    async def location_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        locations = [location.value for location in CampusLivingLocations]
        return [
            app_commands.Choice(name=location, value=location)
            for location in locations
            if current.lower() in location.lower()
        ]

    @app_commands.command(
        name="add-pickup",
        description="Add non-Discord user to list of pickups",
    )
    @feature_flag_enabled(FeatureFlagNames.BOT)
    @app_commands.autocomplete(day=day_autocomplete)
    @app_commands.autocomplete(location=location_autocomplete)
    @log_cmd
    async def add_pickup(
        self, interaction: discord.Interaction, name: str, day: str, location: str
    ):
        if not await cmd_is_allowed(
            interaction, interaction.channel_id, LOCATIONS_CHANNELS_WHITELIST
        ):
            return

        try:
            async with AsyncSessionLocal() as session:
                session.add(
                    NonDiscordRides(name=name, date=get_next_date_obj(day), location=location)
                )
                await session.commit()
        except IntegrityError:
            await interaction.response.send_message(
                f"Pickup for {name} on {day} already exists.", ephemeral=True
            )
            return
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {e}")
        await interaction.response.send_message(f"Added {name} for pickup at {location} on {day}.")

    @app_commands.command(
        name="remove-pickup",
        description="Remove a non-Discord user from the list of pickups",
    )
    @feature_flag_enabled(FeatureFlagNames.BOT)
    @app_commands.autocomplete(day=day_autocomplete)
    @log_cmd
    async def remove_pickup(self, interaction: discord.Interaction, name: str, day: str):
        """
        Removes a non-Discord user's pickup entry.
        """
        if not await cmd_is_allowed(
            interaction, interaction.channel_id, LOCATIONS_CHANNELS_WHITELIST
        ):
            return

        date_to_remove = get_next_date_obj(day)

        async with AsyncSessionLocal() as session:
            try:
                # Check if the entry exists before attempting to delete
                stmt = select(NonDiscordRides).where(
                    NonDiscordRides.name == name, NonDiscordRides.date == date_to_remove
                )
                result = await session.execute(stmt)
                ride_to_remove = result.scalar_one_or_none()

                if ride_to_remove:
                    # If the entry exists, delete it
                    await session.delete(ride_to_remove)
                    await session.commit()
                    await interaction.response.send_message(
                        f"Successfully removed the pickup entry for **{name}** on **{day}**."
                    )
                else:
                    # If the entry does not exist
                    await interaction.response.send_message(
                        f"Could not find a pickup entry for **{name}** on **{day}**.",
                        ephemeral=True,
                    )

            except SQLAlchemyError as e:
                # Handle any potential database errors gracefully
                await session.rollback()
                print(f"Database error: {e}")
                await interaction.response.send_message(
                    "An error occurred while trying to remove the pickup entry. "
                    "Please try again later.",
                    ephemeral=True,
                )
            except Exception as e:
                # Handle other potential errors
                print(f"An unexpected error occurred: {e}")
                await interaction.response.send_message(
                    "An unexpected error occurred. Please try again later.", ephemeral=True
                )

    @app_commands.command(
        name="list-added-pickups",
        description="Lists all added pickups for a specific day.",
    )
    @feature_flag_enabled(FeatureFlagNames.BOT)
    @app_commands.autocomplete(day=day_autocomplete)
    @log_cmd
    async def list_added_pickups(self, interaction: discord.Interaction, day: str):
        """
        Lists all non-Discord user pickups for a given day.
        """
        if not await cmd_is_allowed(
            interaction, interaction.channel_id, LOCATIONS_CHANNELS_WHITELIST
        ):
            return

        date_to_list = get_next_date_obj(day)

        async with AsyncSessionLocal() as session:
            try:
                stmt = select(NonDiscordRides).where(NonDiscordRides.date == date_to_list)
                result = await session.execute(stmt)
                pickups = result.scalars().all()

                if pickups:
                    # Format the list of pickups
                    message = f"**Pickups for {day}:**\n"
                    for pickup in pickups:
                        message += f"- {pickup.name} at {pickup.location}\n"

                    await interaction.response.send_message(message)
                else:
                    # If no pickups are found
                    await interaction.response.send_message(
                        f"No pickups found for **{day}**.", ephemeral=True
                    )

            except Exception as e:
                print(f"An error occurred while listing pickups: {e}")
                await interaction.response.send_message(
                    "An error occurred while trying to list the pickups. Please try again later.",
                    ephemeral=True,
                )


async def setup(bot: commands.Bot):
    await bot.add_cog(NonDiscordRidesCog(bot))
