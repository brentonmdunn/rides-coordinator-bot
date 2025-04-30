import discord
from discord.ext import commands


class HelpRides(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @discord.app_commands.command(
        name="help-rides",
        description="Available commands for the ride bot",
    )
    async def help_rides(self, interaction: discord.Interaction) -> None:
        """Sends an embed listing ride-related commands."""
        embed = discord.Embed(
            title="🚗 Ride Bot Commands",
            description="Here's what I can do:",
            color=discord.Color.blue(),
        )

        embed.add_field(
            name="`/ask-drivers <message>`",
            value="Pings drivers to see who is available to drive.",
            inline=False,
        )

        embed.add_field(
            name="`/pickup-location <name or username>`",
            value="Outputs the pickup location for a specified name or username.",
            inline=False,
        )

        embed.add_field(
            name="`/list-pickups-friday`",
            value="Shows who needs rides for Friday fellowship and their pickup locations.",
            inline=False,
        )

        embed.add_field(
            name="`/list-pickups-sunday`",
            value="Shows who needs rides for Sunday service and their pickup locations.",
            inline=False,
        )

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(HelpRides(bot))
