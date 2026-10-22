"""
Import/reconcile one ride announcement using explicit event metadata.

Run from backend/ with RIDEBOT_TOKEN and DATABASE_URL configured. Dry-run is the
default. This uses Discord REST without connecting a second gateway/scheduler.
No announcement text or message creation date is used to guess the ride date.

Example:
    uv run python -m scripts.reconcile_ride_event \
        --channel-id 123 --message-id 456 --message-type sunday_service \
        --event-date 2026-10-25 --emoji '🍔' --emoji '🏠' --emoji '✳️'
    # Repeat with --apply after reviewing the output.
"""

import argparse
import asyncio
import logging
import os
from datetime import UTC, date, datetime

import discord
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


async def reconcile(args: argparse.Namespace) -> None:
    """Read the entire message snapshot before making any database changes."""
    # Imports follow load_dotenv() in main so the engine sees the configured DB.
    from ridebot.services.ride_events_service import (
        ReactionChoice,
        RideEventsService,
    )
    from shared.core.enums import AskRidesMessageType

    token = os.environ.get("RIDEBOT_TOKEN")
    if not token:
        raise ValueError("RIDEBOT_TOKEN is required")
    message_type = AskRidesMessageType(args.message_type)
    observed_at = datetime.now(UTC)
    async with discord.Client(intents=discord.Intents.none()) as client:
        await client.login(token)
        channel = await client.fetch_channel(args.channel_id)
        if not isinstance(channel, discord.TextChannel):
            raise ValueError("Expected a guild text channel")
        message = await channel.fetch_message(args.message_id)
        if client.user is None or message.author.id != client.user.id:
            raise ValueError("Announcement must have been authored by RideBot")
        choices = []
        for reaction in message.reactions:
            emoji = str(reaction.emoji)
            if emoji not in args.emoji:
                continue
            async for user in reaction.users():
                if not user.bot:
                    choices.append(
                        ReactionChoice(str(user.id), user.name, user.display_name, emoji)
                    )

        logger.info(
            "%s event=%s date=%s guild=%s channel=%s message=%s choices=%s emojis=%s",
            "Applying" if args.apply else "Dry run",
            message_type.value,
            args.event_date,
            channel.guild.id,
            channel.id,
            message.id,
            len(choices),
            args.emoji,
        )
        if not args.apply:
            return
        event = await RideEventsService.ensure_event(
            guild_id=str(channel.guild.id),
            message_type=message_type,
            event_date=args.event_date,
        )
        await RideEventsService.bind_announcement(
            event_id=event.id,
            channel_id=str(channel.id),
            message_id=str(message.id),
            signup_emojis=args.emoji,
        )
        await RideEventsService.reconcile(
            message_id=str(message.id), choices=choices, observed_at=observed_at
        )
        logger.info("Reconciled event %s; GET /api/ride-events/%s", event.id, event.id)


def main() -> None:
    """Parse explicit metadata and run the importer in dry-run mode by default."""
    load_dotenv()
    logging.basicConfig(level=logging.INFO)
    from shared.core.enums import AskRidesMessageType

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--channel-id", type=int, required=True)
    parser.add_argument("--message-id", type=int, required=True)
    parser.add_argument(
        "--message-type", choices=[item.value for item in AskRidesMessageType], required=True
    )
    parser.add_argument("--event-date", type=date.fromisoformat, required=True)
    parser.add_argument("--emoji", action="append", required=True)
    parser.add_argument("--apply", action="store_true")
    asyncio.run(reconcile(parser.parse_args()))


if __name__ == "__main__":
    main()
