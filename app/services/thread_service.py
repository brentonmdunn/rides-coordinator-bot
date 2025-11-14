import asyncio

import discord

from app.core.database import AsyncSessionLocal
from app.core.logger import logger
from app.repositories.thread_repository import EventThreadRepository


# Custom exceptions to communicate outcomes to the cog layer
class EventThreadError(Exception):
    """Base exception for thread service errors."""


class EventThreadAlreadyExistsError(EventThreadError):
    """Raised when an event thread is already being tracked."""


class EventThreadNotFoundError(EventThreadError):
    """Raised when no active event thread is found for an operation."""


class StarterMessageError(EventThreadError):
    """Raised when the thread's starter message cannot be found or read."""


class ThreadService:
    """Manages the business logic for event threads."""

    def __init__(self, repository: EventThreadRepository):
        self.repository = repository

    async def end_event_thread(self, thread_id: str) -> None:
        """
        Stops tracking an event thread.

        Raises:
            EventThreadNotFoundError: If no matching thread is found in the DB.
        """
        async with AsyncSessionLocal() as session:
            # Use get_by_message_id as the ID is the thread/message ID
            thread_to_delete = await self.repository.get_by_message_id(session, thread_id)

            if not thread_to_delete:
                raise EventThreadNotFoundError("No active event thread found.")

            await self.repository.delete(session, thread_to_delete)
            await session.commit()

    async def create_event_thread(
        self, thread: discord.Thread
    ) -> tuple[list[discord.Member], list[str]]:
        """
        Creates and registers a new event thread, then bulk-adds reactors.

        Raises:
            EventThreadAlreadyExistsError: If the thread is already tracked.
            StarterMessageError: If the starter message can't be found.
            discord.Forbidden: If bot permissions are missing.
        """
        thread_id = str(thread.id)
        async with AsyncSessionLocal() as session:
            existing_thread = await self.repository.get_by_id(session, thread_id)
            if existing_thread:
                raise EventThreadAlreadyExistsError("Event thread has already been created.")

        # Perform bulk add *before* committing to DB, as per original logic
        added, failed = await self.bulk_add_reactors_to_thread(thread)

        async with AsyncSessionLocal() as session:
            await self.repository.create(session, thread_id)
            await session.commit()

        return added, failed

    async def bulk_add_reactors_to_thread(
        self, thread: discord.Thread
    ) -> tuple[list[discord.Member], list[str]]:
        """
        Adds all users who reacted to the thread's starter message.

        Returns:
            A tuple of (added_users_list, failed_users_list).

        Raises:
            StarterMessageError: If the starter message can't be found.
            discord.Forbidden: If bot permissions are missing.
        """
        try:
            starter_message = await thread.parent.fetch_message(thread.id)
        except discord.NotFound:
            raise StarterMessageError(
                "Could not find the message that started this thread. Has it been deleted?"
            )
        except discord.Forbidden:
            raise StarterMessageError(
                "I don't have permission to read the history of this "
                "channel to find the first message."
            )

        if not starter_message.reactions:
            return [], []  # No reactions, return empty lists

        reactors = set()
        for reaction in starter_message.reactions:
            async for user in reaction.users():
                if not user.bot:
                    reactors.add(user)

        if not reactors:
            return [], []  # No users reacted

        added_users = []
        failed_users = []

        try:
            thread_members = await thread.fetch_members()
            thread_member_ids = {member.id for member in thread_members}
        except discord.Forbidden:
            # This can happen if the bot was removed from the thread
            # after creation but before this command is run.
            logger.warning(
                f"Failed to fetch members for thread {thread.id}. "
                "Proceeding, but may try to add existing members."
            )
            thread_member_ids = set()

        for user in reactors:
            if user.bot or user.id in thread_member_ids:
                continue

            try:
                await thread.add_user(user)
                added_users.append(user)
                await asyncio.sleep(0.25)  # Avoid rate limits
            except discord.Forbidden:
                # This is a critical failure, bot can't add anyone
                raise
            except Exception:
                logger.exception(f"Failed to add {user.name} to thread {thread.name}")
                failed_users.append(user.name)

        return added_users, failed_users
