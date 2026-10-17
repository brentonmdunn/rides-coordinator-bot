"""Exercise identity matching and remaining reactions using a real event store."""

from datetime import UTC, date, datetime

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from ridebot.repositories.ride_reaction_events_repository import RideReactionEventsRepository
from ridebot.services import ride_reaction_log_service as module
from shared.core.base import Base
from shared.core.models import Locations, RideReactionEvent


@pytest_asyncio.fixture
async def store(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(module, "AsyncSessionLocal", factory)
    yield factory
    await engine.dispose()


def event(message="ride", username="old", user_id="123", action="add", emoji="🚗", **kwargs):
    return RideReactionEvent(
        message_id=message,
        discord_username=username,
        discord_user_id=user_id,
        display_name=kwargs.pop("display_name", "Discord Nickname"),
        emoji=emoji,
        action=action,
        occurred_at=datetime(2026, 10, 1, tzinfo=UTC),
        ride_date=date(2026, 10, 2),
        ride_type="friday",
        **kwargs,
    )


async def seed(store, *rows):
    async with store() as session:
        session.add_all(rows)
        await session.commit()


@pytest.mark.asyncio
@pytest.mark.parametrize("search", ["Full Name", "nickname", "OLD", "new"])
async def test_all_names_find_identity_and_latest_state(store, search):
    await seed(
        store,
        Locations(name="Full Name", discord_username="new", discord_user_id="123"),
        event(),
        event(username="new", action="remove"),
        event(message="kept", username="new", emoji="❤️"),
        event(message="other", username="other", user_id="456", display_name=None),
    )
    groups = await module.RideReactionLogService.get_grouped_events(search=search)
    assert [mid for mid, _ in groups] == ["kept"]
    assert groups[0][1]["events"][0].emoji == "❤️"


@pytest.mark.asyncio
async def test_each_emoji_independent_and_readd_wins_ties(store):
    await seed(
        store,
        event(),
        event(action="remove"),
        event(),
        event(emoji="❤️"),
        event(emoji="❤️", action="remove"),
    )
    groups = await module.RideReactionLogService.get_grouped_events(remaining_only=True)
    assert [row.emoji for row in groups[0][1]["events"]] == ["🚗"]
    assert (
        await module.RideReactionLogService.get_grouped_events(
            remaining_only=True,
            emoji="❤️",
        )
        == []
    )


@pytest.mark.asyncio
async def test_legacy_username_matches_linked_person_and_removal(store):
    await seed(
        store,
        Locations(id=1, name="Person", discord_username="old", discord_user_id="123"),
        event(user_id=None),
        event(username="new", action="remove"),
    )
    assert await module.RideReactionLogService.get_grouped_events(person_id=1) == []


@pytest.mark.asyncio
async def test_ids_keep_people_separate_when_usernames_reused(store):
    await seed(
        store,
        Locations(id=1, name="Person", discord_username="old", discord_user_id="123"),
        event(),
        event(user_id="456", action="remove"),
    )
    groups = await module.RideReactionLogService.get_grouped_events(person_id=1)
    assert groups[0][1]["events"][0].discord_user_id == "123"
    assert await module.RideReactionLogService.get_grouped_events(person_id=999) == []


@pytest.mark.asyncio
async def test_date_filters_and_raw_log_preserved(store):
    await seed(store, event(), event(action="remove"))
    groups = await module.RideReactionLogService.get_grouped_events()
    assert len(groups[0][1]["events"]) == 2
    assert (
        await module.RideReactionLogService.get_grouped_events(
            search="old",
            date_from=date(2026, 10, 3),
        )
        == []
    )


@pytest.mark.asyncio
async def test_repository_persists_user_id(store):
    async with store() as session:
        row = await RideReactionEventsRepository.record_event(
            session,
            "ride",
            "username",
            "Name",
            "🚗",
            "add",
            datetime.now(UTC),
            date.today(),
            "friday",
            discord_user_id="123",
        )
        assert row.discord_user_id == "123"


def test_migration_backfills_only_unambiguous_usernames():
    import importlib.util
    from pathlib import Path

    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import create_engine, text

    path = (
        Path(__file__).parents[2] / "alembic/versions/c8d2e4f6a901_add_reaction_discord_user_ids.py"
    )
    spec = importlib.util.spec_from_file_location("reaction_identity_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE ride_reaction_events (discord_username TEXT)"))
        connection.execute(
            text("CREATE TABLE locations (discord_username TEXT, discord_user_id TEXT)")
        )
        connection.execute(
            text(
                "INSERT INTO locations VALUES ('Alice', '1'), ('duplicate', '2'), ('Duplicate', '3'), ('unlinked', NULL)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO ride_reaction_events VALUES ('alice'), ('duplicate'), ('unlinked'), ('unknown')"
            )
        )
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            assert dict(
                connection.execute(
                    text("SELECT discord_username, discord_user_id FROM ride_reaction_events")
                ).all()
            ) == {"alice": "1", "duplicate": None, "unlinked": None, "unknown": None}
            migration.downgrade()
        assert connection.execute(text("SELECT * FROM ride_reaction_events")).keys() == [
            "discord_username"
        ]
    engine.dispose()


@pytest.mark.asyncio
async def test_name_match_outside_date_range_still_finds_current_identity(store):
    old = event(username="old_alias")
    old.ride_date = date(2026, 9, 1)
    await seed(store, old, event(message="recent", username="new_alias"))
    groups = await module.RideReactionLogService.get_grouped_events(
        search="old_alias",
        date_from=date(2026, 10, 1),
    )
    assert [mid for mid, _ in groups] == ["recent"]


@pytest.mark.asyncio
async def test_recording_uses_discord_id_and_display_name(store, monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from sqlalchemy import select

    from shared.core.enums import ReactionAction

    monkeypatch.setattr(module, "get_message_and_embed_content", lambda _: "Friday ride")
    publish = AsyncMock()
    monkeypatch.setattr(module.reaction_broadcaster, "publish", publish)
    await module.RideReactionLogService.record_ask_rides_reaction(
        SimpleNamespace(id=123, name="new_username", display_name="Discord Nickname"),
        SimpleNamespace(message_id=456, emoji="❤️"),
        SimpleNamespace(created_at=datetime(2026, 10, 2, 18, tzinfo=UTC)),
        ReactionAction.ADD,
    )
    async with store() as session:
        row = (await session.scalars(select(RideReactionEvent))).one()
        assert row.discord_user_id == "123"
        assert row.discord_username == "new_username"
        assert row.display_name == "Discord Nickname"
    assert publish.call_args.args[0]["discord_user_id"] == "123"
