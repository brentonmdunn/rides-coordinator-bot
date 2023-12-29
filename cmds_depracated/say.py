from discord.ext import commands
from discord import app_commands
import discord
@app_commands.describe(thing_to_say="What should I say?", second_param="second")
async def say_command(interaction: discord.Interaction, thing_to_say: str, second_param: str):
    await interaction.response.send_message(f"{interaction.user.name} said: `{thing_to_say}`, second param: {second_param}")

def setup(bot):
    bot.tree.add_command(say_command)
