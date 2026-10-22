"""Discord adapter for complete event snapshots and conservative legacy discovery."""

import logging
import re
from datetime import UTC, date, datetime, timedelta

import discord

from ridebot.core import reaction_broadcaster
from ridebot.services.ask_rides_messages_service import AskRidesMessagesService
from ridebot.services.driver_service import DriverService
from ridebot.services.ride_events_service import ReactionChoice, RideEventsService
from ridebot.utils.ask_rides_defaults import DEFAULT_TEMPLATES
from ridebot.utils.time_helpers import LA_TZ, get_current_cycle_start
from shared.core.enums import AskRidesMessageType, ChannelIds, DaysOfWeek

logger = logging.getLogger(__name__)
WEEKDAYS = {
    AskRidesMessageType.WEDNESDAY_FELLOWSHIP: 2,
    AskRidesMessageType.FRIDAY_FELLOWSHIP: 4,
    AskRidesMessageType.SUNDAY_SERVICE: 6,
    AskRidesMessageType.SUNDAY_CLASS: 6,
}


def legacy_event_date(text: str, created_at: datetime, weekday: int) -> date | None:
    """Read an explicit displayed date; refuse ambiguous or implausible reconstructions."""
    local_date = created_at.astimezone(LA_TZ).date()
    candidates = set()
    for month, day in re.findall(r"(?<![\d/])(\d{1,2})/(\d{1,2})(?![\d/])", text):
        for year in (local_date.year - 1, local_date.year, local_date.year + 1):
            try:
                candidate = date(year, int(month), int(day))
            except ValueError:
                continue
            if candidate.weekday() == weekday and 0 <= (candidate - local_date).days <= 14:
                candidates.add(candidate)
    return next(iter(candidates)) if len(candidates) == 1 else None


class RideEventSyncService:
    """Fetch complete source snapshots; failed fetches never clear recorded choices."""

    def __init__(self, bot):
        """Use the already-running bot rather than starting another gateway client."""
        self.bot = bot

    async def reconcile_announcement(self, announcement):
        """Apply one complete snapshot, preserving observations newer than its start."""
        observed_at = datetime.now(UTC)
        try:
            channel = self.bot.get_channel(int(announcement.channel_id))
            if channel is None:
                channel = await self.bot.fetch_channel(int(announcement.channel_id))
            if not isinstance(channel, discord.TextChannel):
                raise ValueError("Announcement channel is not a guild text channel")
            message = await channel.fetch_message(int(announcement.message_id))
            choices = []
            for reaction in message.reactions:
                emoji = str(reaction.emoji)
                if emoji not in announcement.signup_emojis:
                    continue
                async for user in reaction.users():
                    if not user.bot:
                        choices.append(
                            ReactionChoice(str(user.id), user.name, user.display_name, emoji)
                        )
            await RideEventsService.reconcile(
                message_id=announcement.message_id, choices=choices, observed_at=observed_at
            )
            return True
        except discord.NotFound:
            await RideEventsService.clear_reactions(
                message_id=announcement.message_id, observed_at=observed_at, deleted=True
            )
            return False
        except Exception:
            logger.exception("Failed to reconcile ride announcement %s", announcement.message_id)
            await RideEventsService.mark_sync_error(
                announcement.message_id, "Could not refresh Discord reactions"
            )
            return False

    async def discover_current(self):
        """Import recognizable current-week announcements without guessing arbitrary content."""
        if self.bot.user is None:
            return
        known = {a.message_id for a in await RideEventsService.sync_targets()}
        templates = {
            kind: await AskRidesMessagesService.get_effective_template(kind)
            for kind in AskRidesMessageType
        }
        channel_id = int(ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS)
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            channel = await self.bot.fetch_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            return
        async for message in channel.history(after=get_current_cycle_start(), limit=200):
            if (
                str(message.id) in known
                or message.author.id != self.bot.user.id
                or not message.embeds
            ):
                continue
            title = message.embeds[0].title or ""
            body = message.embeds[0].description or ""
            matches = []
            for kind, template in templates.items():
                event_date = legacy_event_date(
                    f"{title}\n{body}", message.created_at, WEEKDAYS[kind]
                )
                if event_date is None:
                    continue
                titles = {
                    template.title.replace("{date}", event_date.strftime("%-m/%-d")),
                    DEFAULT_TEMPLATES[kind].title,
                }
                if title in titles:
                    matches.append((kind, event_date))
            if len(matches) != 1:
                continue
            kind, event_date = matches[0]
            event = await RideEventsService.ensure_event(
                guild_id=str(channel.guild.id), message_type=kind, event_date=event_date
            )
            await RideEventsService.bind_announcement(
                event_id=event.id,
                channel_id=str(channel.id),
                message_id=str(message.id),
                signup_emojis=list(templates[kind].reactions),
            )
        await self._discover_drivers(known)

    async def _discover_drivers(self, known):
        """Bind legacy driver prompts only to an unambiguous already-dated rider event."""
        channel = self.bot.get_channel(int(ChannelIds.SERVING__DRIVER_CHAT_WOOOOO))
        if channel is None:
            channel = await self.bot.fetch_channel(int(ChannelIds.SERVING__DRIVER_CHAT_WOOOOO))
        if not isinstance(channel, discord.TextChannel):
            return
        labels = {
            "Friday felly": AskRidesMessageType.FRIDAY_FELLOWSHIP,
            "Sunday service": AskRidesMessageType.SUNDAY_SERVICE,
            "Wednesday felly": AskRidesMessageType.WEDNESDAY_FELLOWSHIP,
        }
        service = DriverService()
        events = await RideEventsService.list_events(
            date_from=get_current_cycle_start().date(),
            date_to=get_current_cycle_start().date() + timedelta(days=13),
            guild_id=str(channel.guild.id),
        )
        async for message in channel.history(after=get_current_cycle_start(), limit=200):
            if str(message.id) in known or message.author.id != self.bot.user.id:
                continue
            kind = next(
                (
                    kind
                    for label, kind in labels.items()
                    if message.content == service.format_message(label)
                ),
                None,
            )
            candidates = [
                e
                for e in events
                if e.message_type == kind
                and 0 <= (e.event_date - message.created_at.astimezone(LA_TZ).date()).days <= 7
            ]
            if len(candidates) != 1:
                continue
            event = candidates[0]
            emojis = service.get_emojis(
                DaysOfWeek.SUNDAY
                if kind == AskRidesMessageType.SUNDAY_SERVICE
                else DaysOfWeek.FRIDAY
            )
            await RideEventsService.bind_announcement(
                event_id=event.id,
                channel_id=str(channel.id),
                message_id=str(message.id),
                signup_emojis=emojis,
                kind="driver",
            )

    async def run(self, *, discover=False, strict=False):
        """Reconcile sources independently so one permission/transport failure does not stop others."""
        await RideEventsService.import_legacy_requests()
        discovery_ok = True
        if discover:
            try:
                await self.discover_current()
            except Exception:
                logger.exception("Could not discover existing ride announcements")
                discovery_ok = False
                if strict:
                    raise
        failures = 0
        for announcement in await RideEventsService.sync_targets():
            if not await self.reconcile_announcement(announcement):
                failures += 1
        await reaction_broadcaster.publish({"source": "ride_events", "action": "reconciled"})
        if strict and failures:
            raise RuntimeError(
                f"{failures} source messages could not be refreshed; inspect event freshness"
            )
        return discovery_ok
