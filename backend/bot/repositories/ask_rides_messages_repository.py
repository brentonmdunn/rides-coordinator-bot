"""Data access layer for editable ask-rides message templates."""

from sqlalchemy import delete, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.enums import AskRidesMessageType
from bot.core.models import AskRidesMessageTemplate


class AskRidesMessagesRepository:
    """Handles database operations for ask-rides message templates."""

    @staticmethod
    async def get_all(session: AsyncSession) -> list[AskRidesMessageTemplate]:
        """Return all saved ask-rides message templates."""
        stmt = select(AskRidesMessageTemplate)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get(
        session: AsyncSession, message_type: AskRidesMessageType
    ) -> AskRidesMessageTemplate | None:
        """Return the saved template for a message type, or None if not customized."""
        stmt = select(AskRidesMessageTemplate).where(
            AskRidesMessageTemplate.message_type == message_type
        )
        result = await session.execute(stmt)
        return result.scalars().one_or_none()

    @staticmethod
    async def upsert(
        session: AsyncSession,
        message_type: AskRidesMessageType,
        title: str,
        body: str,
        color: str,
        updated_by: str,
    ) -> AskRidesMessageTemplate:
        """Insert or update the template row for a message type."""
        stmt = insert(AskRidesMessageTemplate).values(
            message_type=message_type,
            title=title,
            body=body,
            color=color,
            updated_by=updated_by,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[AskRidesMessageTemplate.message_type],
            set_={
                "title": title,
                "body": body,
                "color": color,
                "updated_by": updated_by,
            },
        )
        await session.execute(stmt)
        await session.commit()

        result = await AskRidesMessagesRepository.get(session, message_type)
        if result is None:
            # Should never happen — the row was just upserted above.
            raise RuntimeError(f"Failed to read back upserted template for {message_type}")
        return result

    @staticmethod
    async def delete(session: AsyncSession, message_type: AskRidesMessageType) -> None:
        """Delete the saved template row for a message type (reset to default)."""
        stmt = delete(AskRidesMessageTemplate).where(
            AskRidesMessageTemplate.message_type == message_type
        )
        await session.execute(stmt)
        await session.commit()
