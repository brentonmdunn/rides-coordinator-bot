"""cogs/threads.py"""

import asyncio

import discord
from discord.ext import commands

from app.core.enums import FeatureFlagNames
from app.core.logger import logger
from app.utils.checks import feature_flag_enabled


class Threads(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _is_thread(self, interaction: discord.Interaction) -> bool:
        return isinstance(interaction.channel, discord.Thread)


    @discord.app_commands.command(
        name="add-reacts-to-thread",
        description="Must be run in thread. Adds everyone who reacted to parent message to thread.",
    )
    @feature_flag_enabled(FeatureFlagNames.BOT)
    async def add_reacts_to_thread(self, interaction: discord.Interaction) -> None:
        await self._bulk_add_reacts_to_thread(interaction)

    async def _bulk_add_reacts_to_thread(self, interaction):
        if not self._is_thread(interaction):
            await interaction.response.send_message(
                "This command can only be used inside a thread.", ephemeral=True
            )
            return
        # Defer the response because fetching users can take time
        await interaction.response.defer(ephemeral=True, thinking=True)

        thread = interaction.channel

        # 2. Get the starter message
        try:
            # fetch_message is used to ensure we get the message even if it's not in the cache
            starter_message = await thread.parent.fetch_message(thread.id)
        except discord.NotFound:
            await interaction.followup.send(
                "Could not find the message that started this thread. Has it been deleted?"
            )
            return
        except discord.Forbidden:
            await interaction.followup.send(
                "I don't have permission to read the history of this "
                "channel to find the first message."
            )
            return

        if not starter_message.reactions:
            await interaction.followup.send("The first message has no reactions.")
            return

        # 3. Gather all unique users who reacted
        reactors = set()
        for reaction in starter_message.reactions:
            # reaction.users() is an async iterator
            async for user in reaction.users():
                if not user.bot:  # Optional: ignore bots
                    reactors.add(user)

        if not reactors:
            await interaction.followup.send("No users have reacted to the starter message yet.")
            return

        # 4. Add users to the thread
        added_users = []
        failed_users = []

        thread_members = await thread.fetch_members()
        thread_member_ids = {member.id for member in thread_members}
        for user in reactors:
            logger.info(f"{user=}")
            if user.bot or user.id in thread_member_ids:
                continue

            try:
                await thread.add_user(user)
                added_users.append(user.mention)
                # A small sleep can help avoid hitting rate limits if there are many users
                await asyncio.sleep(0.25)
            except discord.Forbidden:
                # This happens if the bot lacks permissions
                await interaction.followup.send(
                    "I lack the `Manage Threads` permission to add users to this private thread."
                )
                return
            except Exception as e:
                print(f"Failed to add {user.name}: {e}")
                failed_users.append(user.name)

        # 5. Send a final confirmation message
        response_message = ""
        if added_users:
            response_message += f"✅ Successfully added {len(added_users)} users:\n" + ", ".join(
                added_users
            )
        if failed_users:
            response_message += f"\n❌ Failed to add {len(failed_users)} users: " + ", ".join(
                failed_users
            )
        if not response_message:
            response_message = "All users who reacted are already in the thread."

        await interaction.followup.send(
            response_message, ephemeral=False
        )  # Send publicly so new users see it


async def setup(bot: commands.Bot):
    await bot.add_cog(Threads(bot))
