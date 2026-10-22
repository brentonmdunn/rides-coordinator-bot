"""Verify the additive event migration and its downgrade on an isolated database."""

from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from alembic import command
from shared.core.base import Base


def test_upgrade_and_downgrade_preserve_existing_roster(tmp_path):
    backend = Path(__file__).resolve().parents[2]
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "alembic"))
    database_url = f"sqlite:///{tmp_path / 'migration.db'}"
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "c8d2e4f6a901")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.exec_driver_sql("INSERT INTO locations (name) VALUES ('Existing Rider')")
    command.upgrade(config, "d1e2f3a4b506")
    assert {"ride_events", "ride_announcements", "ride_signups"} <= set(
        inspect(engine).get_table_names()
    )
    with engine.connect() as connection:
        assert (
            connection.exec_driver_sql("SELECT name FROM locations").scalar_one()
            == "Existing Rider"
        )
    command.downgrade(config, "c8d2e4f6a901")
    assert not {"ride_events", "ride_announcements", "ride_signups"} & set(
        inspect(engine).get_table_names()
    )
    with engine.connect() as connection:
        assert (
            connection.exec_driver_sql("SELECT name FROM locations").scalar_one()
            == "Existing Rider"
        )
    command.upgrade(config, "d1e2f3a4b506")
    command.upgrade(config, "f2a3b4c5d607")
    command.downgrade(config, "d1e2f3a4b506")
    command.upgrade(config, "f2a3b4c5d607")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO ride_events (id, guild_id, message_type, event_date) "
            "VALUES (1, '123', 'sunday_service', '2026-10-25')"
        )
        connection.exec_driver_sql(
            "INSERT INTO ride_driver_offers "
            "(event_id, discord_user_id, discord_username, availability, directions, updated_at) "
            "VALUES (1, '9', 'driver', 'available', '[]', '2026-10-21')"
        )
    with pytest.raises(RuntimeError, match="contains data"):
        command.upgrade(config, "a3b4c5d6e708")
    with engine.begin() as connection:
        assert connection.exec_driver_sql("SELECT COUNT(*) FROM ride_driver_offers").scalar() == 1
        connection.exec_driver_sql("DELETE FROM ride_driver_offers")
        connection.exec_driver_sql(
            "INSERT INTO ride_requests "
            "(event_id, identity_key, source, name, active, pickup, return_preference, "
            "needs_review, updated_at) "
            "VALUES (1, 'non_discord:Guest', 'non_discord', 'Guest', 1, 1, 'lunch', 0, '2026-10-21')"
        )
    command.upgrade(config, "a3b4c5d6e708")
    assert not {"ride_assignments", "ride_driver_offers"} & set(inspect(engine).get_table_names())
    command.downgrade(config, "f2a3b4c5d607")
    command.upgrade(config, "a3b4c5d6e708")
    with engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT name FROM ride_requests").scalar_one() == "Guest"
        assert (
            compare_metadata(
                MigrationContext.configure(connection, opts={"compare_type": False}), Base.metadata
            )
            == []
        )
    engine.dispose()
