import discord
from discord import app_commands
from discord.ext import commands

from app.core.enums import FeatureFlagNames
from app.utils.checks import feature_flag_enabled


class HelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="help",
        description="List all slash commands with their parameters",
    )
    @feature_flag_enabled(FeatureFlagNames.BOT)
    async def help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Available Slash Commands",
            description="Here are the commands and their parameters:",
            color=discord.Color.blue(),
        )

        cmds = self.bot.tree.get_commands()

        for cmd in cmds:
            if isinstance(cmd, app_commands.Command):
                param_list = []
                for param in cmd.parameters:
                    name = param.name
                    typ = param.type.name if hasattr(param.type, "name") else str(param.type)
                    required = "required" if param.required else "optional"
                    param_list.append(f"`{name}: {typ}` ({required})")

                params_str = "\n".join(param_list) if param_list else "*No parameters*"
                embed.add_field(
                    name=f"/{cmd.name} - {cmd.description or 'No description'}",
                    value=params_str,
                    inline=False,
                )

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCog(bot))
