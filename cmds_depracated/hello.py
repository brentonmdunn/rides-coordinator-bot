from discord.ext import commands
import discord

@commands.hybrid_command()
async def hello(ctx):
    await ctx.send(f"Hello {ctx.author.display_name}!")
    # await interaction.response.send_message("Slash command")

async def setup(bot):
    bot.add_command(hello)
