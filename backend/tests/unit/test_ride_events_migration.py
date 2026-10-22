"""Verify the additive event migration and its downgrade on an isolated database."""

from pathlib import Path

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
    with engine.connect() as connection:
        assert (
            compare_metadata(
                MigrationContext.configure(connection, opts={"compare_type": False}), Base.metadata
            )
            == []
        )
    engine.dispose()
