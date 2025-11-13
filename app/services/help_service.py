import discord
from discord import app_commands


class HelpService:
    @staticmethod
    def build_help_embed(bot) -> discord.Embed:
        """Generate an embed showing all slash commands and their parameters."""
        embed = discord.Embed(
            title="Available Slash Commands",
            description="Here are the commands and their parameters:",
            color=discord.Color.blue(),
        )

        cmds = bot.tree.get_commands()

        for cmd in cmds:
            if isinstance(cmd, app_commands.Command):
                param_list = []
                for param in cmd.parameters:
                    name = param.name
                    typ = getattr(param.type, "name", str(param.type))
                    required = "required" if param.required else "optional"
                    param_list.append(f"`{name}: {typ}` ({required})")

                params_str = "\n".join(param_list) if param_list else "*No parameters*"
                embed.add_field(
                    name=f"/{cmd.name} - {cmd.description or 'No description'}",
                    value=params_str,
                    inline=False,
                )

        return embed
