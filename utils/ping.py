import discord
def get_member(guild_members: discord.utils.SequenceProxy, username: str) -> discord.member.Member:
    """Returns ping-able member object."""
    return discord.utils.get(guild_members, name=username)