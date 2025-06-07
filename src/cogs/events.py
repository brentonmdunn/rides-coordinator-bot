import discord
from discord.ext import commands


class Events(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @discord.app_commands.command(
        name="assign-role-to-reacts",
        description="Assign a role to everyone who reacted to a specific message.",
    )
    @discord.app_commands.describe(
        message_id="The ID of the message to check reactions on.",
        channel_id="The ID of the channel the message is in.",
        role_name="Name of the role to assign.",
    )
    async def give_role(
        self,
        interaction: discord.Interaction,
        message_id: str,
        channel_id: str,
        role_name: str,
    ):
        guild = interaction.guild
        if not guild:
            await interaction.response.send_message(
                "This command must be used in a server.", ephemeral=True
            )
            return

        # Acknowledge the command to avoid interaction timeout
        await interaction.response.defer()

        # Convert IDs
        try:
            message_id = int(message_id)
            channel_id = int(channel_id)
        except ValueError:
            await interaction.followup.send(
                "Invalid message or channel ID.", ephemeral=True
            )
            return

        # Get channel
        channel = guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            await interaction.followup.send(
                "Could not find the specified text channel.", ephemeral=True
            )
            return

        # Fetch message
        try:
            message = await channel.fetch_message(message_id)

        except discord.NotFound:
            await interaction.followup.send("Message not found.", ephemeral=True)
            return

        # Get role
        role = discord.utils.get(guild.roles, name=role_name)
        if not role:
            await interaction.followup.send("Role not found.", ephemeral=True)
            return

        added_members = set()

        # Iterate over all reactions and users
        for reaction in message.reactions:
            async for user in reaction.users():
                if user.bot:
                    continue
                member = guild.get_member(user.id)

                if member and role not in member.roles:
                    try:
                        await member.add_roles(role, reason="Reacted to message")
                        added_members.add(member)
                    except discord.Forbidden:
                        # Bot may lack permission
                        continue

        await interaction.followup.send(
            f"Gave **{role_name}** role to **{len(added_members)}** user(s)."
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Events(bot))
