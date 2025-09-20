import discord
from discord.ext import commands

from app.core.enums import FeatureFlagNames, RoleIds
from app.utils.checks import feature_flag_enabled
from app.core.logger import logger

class OnMessageCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        msg=None
        usr = None
        target_user_id = 489147889117954059 # Replace with Brentond's actual user ID

        # Check if the message author is a bot OR if the message author is NOT the target user
        try:
            if message.author.bot or message.author.id != target_user_id:
                logger.info(f"Blocked {message.author.id=}")
                return
        except Exception:
            return


        # List of allowed role IDs
        allowed_role_ids = []
        
        # Check if the author has any of the allowed roles
        has_allowed_role = any(role.id in allowed_role_ids for role in message.author.roles)

        # Send a DM only if the message contains the forbidden mentions
        # AND the user does NOT have any of the allowed roles
        if ("@everyone" in message.content or "@here" in message.content) and not has_allowed_role:
            try:


                # Get the guild from the message
                guild = message.guild
                
                # Look up the role name based on its ID
                # Replace 12309 with the actual ID you want to reference
                role_id_to_lookup = RoleIds.COLLEGE
                if guild:
                    role_to_suggest = guild.get_role(role_id_to_lookup)
                else:
                    role_to_suggest = None
                    


                # Send a DM to the user with the forwarded message content
                msg = (
                    f"Hi {message.author.name},\n\nIf you are making an announcement for LSCC's College Fellowship, please use `@{role_to_suggest}` instead of `@everyone` or `@here`. If you need to make an announcement for everyone in the server, please message Brenton or Alex.\n\n"
                    f"**Original Message in #{message.channel.name}:**\n> {message.content}\n\n"
                )
                usr = message.author.name
                await message.author.send(msg)
                print(f"Deleted message and forwarded content to {message.author} in DMs.")
            except discord.Forbidden:
                # This handles cases where the bot cannot delete the message or send a DM.
                print(f"Could not delete message or send DM to {message.author}. Check permissions.")
            except discord.HTTPException:
                # This handles other errors, such as a message being too old to delete.
                print(f"HTTP exception while trying to delete message from {message.author}.")

        # Process other commands
        await self.bot.process_commands(message)
        channel = self.bot.get_channel(1418799918402764891)
        await channel.send(f"{usr}:\n> {msg}")

async def setup(bot: commands.Bot):
    await bot.add_cog(OnMessageCog(bot))