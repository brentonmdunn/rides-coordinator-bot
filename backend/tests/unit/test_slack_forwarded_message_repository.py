"""Unit tests for SlackForwardedMessageRepository, against an in-memory SQLite DB."""

import pytest
import pytest_asyncio
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from shared.core.base import Base
from stonesbot.repositories.slack_forwarded_message_repository import (
    SlackForwardedMessageRepository,
)


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        yield session
    await engine.dispose()


async def _add(session, ts="1.0", part=0, message_id="100", channel="C1"):
    await SlackForwardedMessageRepository.add(
        session,
        slack_channel_id=channel,
        slack_ts=ts,
        part=part,
        discord_channel_id="999",
        discord_message_id=message_id,
    )


@pytest.mark.asyncio
async def test_get_parts_returns_rows_in_part_order(session):
    await _add(session, part=1, message_id="101")
    await _add(session, part=0, message_id="100")
    await _add(session, ts="2.0", message_id="200")
    await session.commit()

    parts = await SlackForwardedMessageRepository.get_parts(session, "C1", "1.0")

    assert [p.discord_message_id for p in parts] == ["100", "101"]


@pytest.mark.asyncio
async def test_get_parts_is_scoped_to_channel(session):
    await _add(session, channel="C2")
    await session.commit()

    assert await SlackForwardedMessageRepository.get_parts(session, "C1", "1.0") == []


@pytest.mark.asyncio
async def test_delete_parts_removes_only_that_message(session):
    await _add(session, part=0)
    await _add(session, part=1, message_id="101")
    await _add(session, ts="2.0", message_id="200")
    await session.commit()

    await SlackForwardedMessageRepository.delete_parts(session, "C1", "1.0")
    await session.commit()

    assert await SlackForwardedMessageRepository.get_parts(session, "C1", "1.0") == []
    assert len(await SlackForwardedMessageRepository.get_parts(session, "C1", "2.0")) == 1


@pytest.mark.asyncio
async def test_duplicate_part_is_rejected(session):
    await _add(session)
    await _add(session, message_id="other")

    with pytest.raises(IntegrityError):
        await session.commit()
