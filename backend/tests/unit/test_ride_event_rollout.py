"""Verify online backups and the exact schema rollout without touching application databases."""

import sqlite3
from pathlib import Path

from alembic.config import Config

from alembic import command
from scripts.rollout_ride_events import REVISION, migrate_database


def test_rollout_dry_run_and_online_backup_preserve_existing_data(tmp_path):
    backend = Path(__file__).resolve().parents[2]
    path = tmp_path / "rides.db"
    url = f"sqlite:///{path}"
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "alembic"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "c8d2e4f6a901")
    with sqlite3.connect(path) as connection:
        connection.execute("INSERT INTO locations (name) VALUES ('Keep this rider')")
    assert migrate_database(url, apply=False) is None
    assert list(tmp_path.glob("*.before-ride-events-*")) == []
    backup = migrate_database(url, apply=True)
    assert backup is not None
    with sqlite3.connect(backup) as connection:
        assert connection.execute("SELECT name FROM locations").fetchone() == ("Keep this rider",)
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            "c8d2e4f6a901",
        )
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT name FROM locations").fetchone() == ("Keep this rider",)
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            REVISION,
        )
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
