"""Methods that ping or assist in pinging users or roles."""

import discord

def get_member(guild_members: discord.utils.SequenceProxy, username: str) -> discord.member.Member:
    """
    Gets ping-able member object.
    
    Args:
        guild_members (discord.utils.SequenceProxy): iterable with members in guild
        username (str): username to find

    Returns: (discord.member.Member)
        Returns ping-able member object.
    """
    return discord.utils.get(guild_members, name=username)

def get_role(my_guild: discord.guild.Guild, role_id: int) -> discord.role.Role:
    """
    Gets ping-able role object.

    Args:
        my_guild (discord.guild.Guild): current guild
        role_id (int): number for role based on dev tools
    Returns: (discord.role.Roles)
        Returns ping-able role object.
    """

    return my_guild.get_role(role_id)

def create_message(role: discord.role.Role, message: str) -> str:
    """
    Formats message by pinging role followed by message.

    Args:
        role (discord.role.Role): role to ping 
        message (str): message to ping with 

    Returns: (str)
        Pinged role followed by message
    """
    return f"{role.mention} {message}"