"""Repository for modmail message data access."""

import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.enums import ModmailSenderType
from bot.core.models import ModmailMessages

logger = logging.getLogger(__name__)


class ModmailMessagesRepository:
    """Handles database operations for ModmailMessages."""

    @staticmethod
    async def create(
        session: AsyncSession,
        *,
        user_id: str,
        sender_type: ModmailSenderType,
        sender_id: str,
        sender_name: str | None,
        content: str,
        attachments_json: str | None = None,
    ) -> ModmailMessages:
        """
        Insert a new modmail message.

        Args:
            session: The database session.
            user_id: The Discord user ID of the conversation owner.
            sender_type: Who sent the message (user, admin, or bot).
            sender_id: The sender's Discord user ID or admin identifier.
            sender_name: Human-readable sender name.
            content: The message text.
            attachments_json: Optional JSON string of attachment URLs.

        Returns:
            The newly created ModmailMessages row.
        """
        row = ModmailMessages(
            user_id=user_id,
            sender_type=sender_type,
            sender_id=sender_id,
            sender_name=sender_name,
            content=content,
            attachments_json=attachments_json,
        )
        session.add(row)
        return row

    @staticmethod
    async def get_messages(
        session: AsyncSession,
        user_id: str,
        *,
        limit: int = 50,
        before_id: int | None = None,
    ) -> list[ModmailMessages]:
        """
        Fetch messages for a conversation, ordered oldest-first.

        Args:
            session: The database session.
            user_id: The conversation owner's Discord user ID.
            limit: Maximum number of messages to return.
            before_id: If set, only return messages with id < before_id (for pagination).

        Returns:
            List of ModmailMessages rows ordered by created_at ascending.
        """
        stmt = select(ModmailMessages).where(ModmailMessages.user_id == user_id)
        if before_id is not None:
            stmt = stmt.where(ModmailMessages.id < before_id)
        stmt = stmt.order_by(ModmailMessages.id.desc()).limit(limit)
        result = await session.execute(stmt)
        rows = list(result.scalars().all())
        rows.reverse()
        return rows

    @staticmethod
    async def get_conversations(
        session: AsyncSession,
    ) -> list[dict]:
        """
        List all conversations with their latest message and message count.

        Args:
            session: The database session.

        Returns:
            List of dicts with user_id, last_message_content, last_message_at,
            sender_name, and message_count.
        """
        subq = (
            select(
                ModmailMessages.user_id,
                func.max(ModmailMessages.id).label("max_id"),
                func.count(ModmailMessages.id).label("message_count"),
            )
            .group_by(ModmailMessages.user_id)
            .subquery()
        )

        stmt = (
            select(
                ModmailMessages.user_id,
                ModmailMessages.content,
                ModmailMessages.created_at,
                ModmailMessages.sender_name,
                ModmailMessages.sender_type,
                subq.c.message_count,
            )
            .join(subq, ModmailMessages.id == subq.c.max_id)
            .order_by(ModmailMessages.created_at.desc())
        )

        result = await session.execute(stmt)
        rows = result.all()
        return [
            {
                "user_id": row.user_id,
                "last_message_content": row.content,
                "last_message_at": row.created_at.isoformat() if row.created_at else None,
                "sender_name": row.sender_name,
                "sender_type": row.sender_type,
                "message_count": row.message_count,
            }
            for row in rows
        ]
