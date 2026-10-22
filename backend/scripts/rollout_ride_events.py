"""
Back up and migrate SQLite, then import/reconcile current ride announcements.

Run from backend/: uv run python -m scripts.rollout_ride_events --apply
Dry-run is the default. --schema-only explicitly omits Discord import.
"""

import argparse
import asyncio
import logging
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import make_url

logger = logging.getLogger(__name__)
REVISION = "f2a3b4c5d607"


def migrate_database(database_url: str, *, apply: bool) -> Path | None:
    """Take a consistent SQLite online backup before applying the exact rollout revision."""
    from alembic.config import Config

    from alembic import command

    url = make_url(database_url)
    if url.get_backend_name() != "sqlite" or not url.database or url.database == ":memory:":
        raise ValueError("Rollout requires a file-backed SQLite DATABASE_URL")
    database = Path(url.database).resolve()
    backup = database.with_name(
        f"{database.stem}.before-ride-events-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S%f')}{database.suffix}"
    )
    logger.info(
        "%s migration to %s; database=%s; online backup=%s",
        "Applying" if apply else "Dry-run",
        REVISION,
        database.name,
        backup.name if database.exists() else "new database",
    )
    if not apply:
        return None
    if database.exists():
        with (
            sqlite3.connect(f"{database.as_uri()}?mode=ro", uri=True) as source,
            sqlite3.connect(backup) as destination,
        ):
            source.backup(destination)
            if destination.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RuntimeError("Backup integrity check failed; migration was not attempted")
    else:
        database.parent.mkdir(parents=True, exist_ok=True)
        backup = None
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "alembic"))
    config.set_main_option(
        "sqlalchemy.url",
        url.set(drivername="sqlite").render_as_string(hide_password=False).replace("%", "%%"),
    )
    command.upgrade(config, REVISION)
    return backup


async def import_current() -> None:
    """Use REST only to import existing sources; no bot messages or gateway are started."""
    import discord

    from ridebot.services.ride_event_sync_service import RideEventSyncService

    token = os.environ.get("RIDEBOT_TOKEN")
    if not token:
        raise ValueError("RIDEBOT_TOKEN is required to import current announcements")
    async with discord.Client(intents=discord.Intents.none()) as client:
        await client.login(token)
        await RideEventSyncService(client).run(discover=True, strict=True)
    logger.info(
        "Current announcement discovery and reconciliation completed; inspect event freshness for source failures"
    )


def main() -> None:
    """Run a reviewable migration/import or an explicit schema-only rollout."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--schema-only", action="store_true")
    parser.add_argument("--env-file", default=".env")
    args = parser.parse_args()
    load_dotenv(args.env_file)
    logging.basicConfig(level=logging.INFO)
    if args.apply and not args.schema_only and not os.environ.get("RIDEBOT_TOKEN"):
        parser.error(
            "RIDEBOT_TOKEN is required for import; use --schema-only to explicitly migrate without import"
        )
    migrate_database(
        os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./db/bot.db"), apply=args.apply
    )
    if args.apply and not args.schema_only:
        asyncio.run(import_current())
    elif args.apply:
        from ridebot.services.ride_events_service import RideEventsService

        asyncio.run(RideEventsService.import_legacy_requests())
    elif not args.schema_only:
        logger.info(
            "Apply will also import recognized current announcements and reconcile all saved sources"
        )


if __name__ == "__main__":
    main()
