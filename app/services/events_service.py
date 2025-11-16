# app/services/events_service.py

from app.repositories.events_repository import EventsRepository
from app.utils.custom_exceptions import (
    ChannelNotFoundError,
    GuildNotFoundError,
    MessageNotFoundError,
    RoleNotFoundError,
)


class EventsService:
    """
    Handles the business logic for assigning roles based on reactions.
    """

    def __init__(self, repository: EventsRepository):
        self.repository = repository

    async def assign_role_to_reactors(
        self,
        guild_id: int,
        channel_id: int,
        message_id: int,
        role_name: str,
    ) -> int:
        """
        Assigns a role to all users who reacted to a message.

        Args:
            guild_id: The ID of the guild.
            channel_id: The ID of the channel.
            message_id: The ID of the message.
            role_name: The name of the role to assign.

        Returns:
            The number of members who were successfully given the role.

        Raises:
            GuildNotFoundError: If the guild doesn't exist.
            ChannelNotFoundError: If the channel doesn't exist.
            MessageNotFoundError: If the message doesn't exist.
            RoleNotFoundError: If the role doesn't exist.
        """
        guild = self.repository.get_guild(guild_id)
        if not guild:
            raise GuildNotFoundError(f"No guild found with ID {guild_id}")

        channel = self.repository.get_text_channel(guild, channel_id)
        if not channel:
            raise ChannelNotFoundError(f"No channel found with ID {channel_id}")

        message = await self.repository.fetch_message(channel, message_id)
        if not message:
            raise MessageNotFoundError(f"No message found with ID {message_id}")

        role = self.repository.get_role_by_name(guild, role_name)
        if not role:
            raise RoleNotFoundError(f"No role found with name '{role_name}'")

        members_to_add = await self.repository.get_reacting_members(message, guild)

        added_count = 0
        for member in members_to_add:
            if role not in member.roles:
                success = await self.repository.add_role_to_member(
                    member, role, reason="Reacted to message"
                )
                if success:
                    added_count += 1

        return added_count
