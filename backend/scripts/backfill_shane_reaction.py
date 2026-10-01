"""
One-off data repair: backfill the single ride_reaction_event dropped by the
2026-10-01 12:19:01 PDT reaction-handler crash.

A transient Discord 503 on ``channel.fetch_message`` killed ``on_raw_reaction_add``
before ``_record_ask_rides_reaction`` ran, so shane9910199's 🍔 add on the Sunday
ask-rides message left no DB row. This inserts that one row through the ORM +
repository layer (never raw SQL), is idempotent, and supports --dry-run.

RECONSTRUCTION CAVEAT: the username / emoji / message are solidly established by
diffing the live Discord reactor list against the DB. ``occurred_at`` is the crash
timestamp (the fetch that 503'd was triggered by this reaction), not the true
reaction time — the two are within seconds of each other. This is reconstructed
audit data from circumstantial evidence, not a primary record.

Usage (run from backend/, as a module so first-party imports resolve):
    uv run python -m scripts.backfill_shane_reaction            # dry-run (default)
    uv run python -m scripts.backfill_shane_reaction --apply    # actually insert
"""

import argparse
import asyncio
import datetime
import logging

from sqlalchemy import select

# Importing shared.core.logger configures the root logger as a side effect.
import shared.core.logger  # noqa: F401
from ridebot.repositories.ride_reaction_events_repository import RideReactionEventsRepository
from shared.core.database import AsyncSessionLocal
from shared.core.models import RideReactionEvent

logger = logging.getLogger(__name__)

# The reconstructed row. See module docstring for the derivation of each value.
MESSAGE_ID = "1554930864163397674"
DISCORD_USERNAME = "shane9910199"
DISPLAY_NAME: str | None = None
EMOJI = "🍔"
ACTION = "add"
OCCURRED_AT = datetime.datetime(2026, 10, 1, 19, 19, 1)  # UTC — crash timestamp
RIDE_DATE = datetime.date(2026, 9, 30)
RIDE_TYPE = "sunday"


async def _existing_row(session) -> RideReactionEvent | None:
    """Return the matching row if this backfill has already been applied."""
    stmt = select(RideReactionEvent).where(
        RideReactionEvent.message_id == MESSAGE_ID,
        RideReactionEvent.discord_username == DISCORD_USERNAME,
        RideReactionEvent.emoji == EMOJI,
        RideReactionEvent.action == ACTION,
        RideReactionEvent.occurred_at == OCCURRED_AT,
    )
    result = await session.execute(stmt)
    return result.scalars().first()


async def backfill(dry_run: bool) -> None:
    """Insert the reconstructed reaction row unless it already exists."""
    row_desc = (
        f"message_id={MESSAGE_ID} discord_username={DISCORD_USERNAME} "
        f"display_name={DISPLAY_NAME} emoji={EMOJI} action={ACTION} "
        f"occurred_at={OCCURRED_AT} ride_date={RIDE_DATE} ride_type={RIDE_TYPE}"
    )

    async with AsyncSessionLocal() as session:
        existing = await _existing_row(session)
        if existing is not None:
            logger.info("Row already present (id=%s); nothing to do: %s", existing.id, row_desc)
            return

        if dry_run:
            logger.info("[DRY RUN] Would insert: %s", row_desc)
            return

        entry = await RideReactionEventsRepository.record_event(
            session,
            message_id=MESSAGE_ID,
            discord_username=DISCORD_USERNAME,
            display_name=DISPLAY_NAME,
            emoji=EMOJI,
            action=ACTION,
            occurred_at=OCCURRED_AT,
            ride_date=RIDE_DATE,
            ride_type=RIDE_TYPE,
        )
        logger.info("Inserted reconstructed reaction row id=%s: %s", entry.id, row_desc)


def main() -> None:
    """Parse args and run the backfill (dry-run unless --apply is passed)."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually insert the row. Without this flag the script runs as a dry-run.",
    )
    args = parser.parse_args()

    asyncio.run(backfill(dry_run=not args.apply))


if __name__ == "__main__":
    main()
