"""Repository for forwarded Slack announcement data access."""

import logging

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.core.models import SlackForwardedMessage

logger = logging.getLogger(__name__)


class SlackForwardedMessageRepository:
    """Handles database operations for SlackForwardedMessage."""

    @staticmethod
    async def get_parts(
        session: AsyncSession, slack_channel_id: str, slack_ts: str
    ) -> list[SlackForwardedMessage]:
        """
        Fetch the Discord messages posted for one Slack message, in part order.

        Args:
            session: The database session.
            slack_channel_id: The Slack channel the message was posted in.
            slack_ts: The Slack message's ts (its id within the channel).

        Returns:
            The rows for that message ordered by part, or an empty list if it was
            never forwarded.
        """
        result = await session.execute(
            select(SlackForwardedMessage)
            .where(
                SlackForwardedMessage.slack_channel_id == slack_channel_id,
                SlackForwardedMessage.slack_ts == slack_ts,
            )
            .order_by(SlackForwardedMessage.part)
        )
        return list(result.scalars().all())

    @staticmethod
    async def add(
        session: AsyncSession,
        slack_channel_id: str,
        slack_ts: str,
        part: int,
        discord_channel_id: str,
        discord_message_id: str,
    ) -> SlackForwardedMessage:
        """
        Record one Discord message posted for a Slack message.

        Args:
            session: The database session.
            slack_channel_id: The Slack channel the message was posted in.
            slack_ts: The Slack message's ts.
            part: Zero-based index of this Discord message among the message's parts.
            discord_channel_id: The Discord channel it was posted in.
            discord_message_id: The posted Discord message's id.

        Returns:
            The created SlackForwardedMessage object.
        """
        row = SlackForwardedMessage(
            slack_channel_id=slack_channel_id,
            slack_ts=slack_ts,
            part=part,
            discord_channel_id=discord_channel_id,
            discord_message_id=discord_message_id,
        )
        session.add(row)
        return row

    @staticmethod
    async def delete_parts(session: AsyncSession, slack_channel_id: str, slack_ts: str) -> None:
        """
        Delete every row recorded for one Slack message.

        Args:
            session: The database session.
            slack_channel_id: The Slack channel the message was posted in.
            slack_ts: The Slack message's ts.
        """
        await session.execute(
            delete(SlackForwardedMessage).where(
                SlackForwardedMessage.slack_channel_id == slack_channel_id,
                SlackForwardedMessage.slack_ts == slack_ts,
            )
        )
