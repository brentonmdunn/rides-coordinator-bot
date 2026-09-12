"""
Service for the "Something else" button on ask-rides announcements.

Riders whose needs don't fit any reaction option tap the button, describe what
they need in a modal, and this service forwards it to the ride coordinators
channel with enough context to act on.
"""

import logging
import time
from datetime import datetime, timedelta

import discord

from ridebot.services.pickup_info_service import Person, PickupInfoService
from ridebot.utils.ask_rides_defaults import DEFAULT_TEMPLATES
from ridebot.utils.channels import resolve_channel_id
from ridebot.utils.constants import ASK_RIDES_OTHER_COOLDOWN_SECONDS
from ridebot.utils.feature_flags import is_flag_enabled
from ridebot.utils.time_helpers import LA_TZ
from shared.core.bots import get_spec
from shared.core.enums import AskRidesMessageType, BotName, ChannelIds, FeatureFlagNames
from shared.core.error_reporter import send_error_to_discord

logger = logging.getLogger(__name__)

# Module-level cooldown tracker: user id -> last submission time (monotonic
# seconds). In-memory is fine because losing it on restart doesn't matter.
_last_submission: dict[int, float] = {}


def _reset_cooldowns() -> None:
    """Clear all recorded cooldowns (tests only)."""
    _last_submission.clear()


def _current_cycle_start(now: datetime) -> datetime:
    """
    Return the start of the ride week (Monday 00:00 LA time) containing `now`.

    Mirrors `ridebot.utils.time_helpers.get_current_cycle_start`, but takes an
    explicit `now` instead of always using the real clock, so it can be tested.
    """
    local_now = now.astimezone(LA_TZ)
    week_start = local_now - timedelta(days=local_now.weekday())
    return week_start.replace(hour=0, minute=0, second=0, microsecond=0)


class AskRidesOtherService:
    """Logic for the "Something else" button on ask-rides announcements."""

    @staticmethod
    async def is_enabled() -> bool:
        """Return whether RideBot's kill switch and ASK_RIDES_OTHER_BUTTON are both enabled."""
        kill_switch_flag = get_spec(BotName.RIDEBOT).kill_switch_flag
        return await is_flag_enabled(kill_switch_flag) and await is_flag_enabled(
            FeatureFlagNames.ASK_RIDES_OTHER_BUTTON
        )

    @staticmethod
    def is_current(message_created_at: datetime, *, now: datetime | None = None) -> bool:
        """
        Return whether an announcement was sent during the current ride week.

        Args:
            message_created_at: The announcement's timezone-aware creation time.
            now: Override for the current time (tests).

        Returns:
            True if the message was created at or after this week's Monday 00:00 LA time.
        """
        current_time = now if now is not None else datetime.now(tz=LA_TZ)
        start = _current_cycle_start(current_time)
        return message_created_at >= start

    @staticmethod
    def is_on_cooldown(user_id: int, *, now: float | None = None) -> bool:
        """
        Return whether a user submitted a request too recently to send another.

        Args:
            user_id: The Discord user's id.
            now: Override for the monotonic clock (tests).

        Returns:
            True if the user's last submission is within the cooldown window.
        """
        current_time = now if now is not None else time.monotonic()
        last = _last_submission.get(user_id)
        if last is None:
            return False
        return current_time - last < ASK_RIDES_OTHER_COOLDOWN_SECONDS

    @staticmethod
    def record_submission(user_id: int, *, now: float | None = None) -> None:
        """
        Record that a user just submitted a request, starting their cooldown.

        Args:
            user_id: The Discord user's id.
            now: Override for the monotonic clock (tests).
        """
        current_time = now if now is not None else time.monotonic()
        _last_submission[user_id] = current_time

    @staticmethod
    def build_coordinator_message(
        *,
        user_id: int,
        username: str,
        announcement_title: str,
        jump_url: str,
        text: str,
        person: Person | None,
        lookup_failed: bool,
    ) -> str:
        """
        Build the message posted to the ride coordinators channel.

        Args:
            user_id: The rider's Discord user id.
            username: The rider's Discord username.
            announcement_title: The title of the announcement the button was on.
            jump_url: Link to the announcement.
            text: What the rider typed into the modal.
            person: The rider's pickup info entry, if registered.
            lookup_failed: Whether the pickup info lookup raised.

        Returns:
            The formatted coordinator message.
        """
        if lookup_failed:
            info_line = "⚠️ Couldn't load pickup info"
        elif person is None:
            info_line = "⚠️ Not registered for pickup info"
        else:
            info_line = (
                f"📍 {person.name} · {person.location or 'no pickup spot'} · "
                f"{person.year or 'year unknown'} year"
            )

        quoted_text = "\n".join(f"> {line}" if line else ">" for line in text.strip().split("\n"))

        return (
            f"✳️ **Something else** from <@{user_id}> (`@{username}`) on "
            f"**{announcement_title}** · [Jump to message]({jump_url})\n"
            f"{info_line}\n"
            f"{quoted_text}"
        )

    @staticmethod
    async def submit(
        *,
        client: discord.Client,
        user: discord.User | discord.Member,
        message_type: AskRidesMessageType,
        announcement: discord.Message,
        text: str,
    ) -> bool:
        """
        Forward a rider's "Something else" request to the ride coordinators channel.

        Args:
            client: The bot client that received the interaction.
            user: The rider who submitted the modal.
            message_type: Which announcement type the button belonged to.
            announcement: The announcement message the button was on.
            text: What the rider typed into the modal.

        Returns:
            True if the message was posted; False otherwise.
        """
        embeds = announcement.embeds
        title = (
            embeds[0].title if embeds and embeds[0].title else DEFAULT_TEMPLATES[message_type].title
        )

        lookup_failed = False
        person: Person | None = None
        try:
            person = await PickupInfoService.find_member(
                discord_user_id=user.id, discord_username=user.name
            )
        except Exception:
            logger.exception("Failed to look up pickup info for ask-rides Something else submit")
            lookup_failed = True

        msg = AskRidesOtherService.build_coordinator_message(
            user_id=user.id,
            username=user.name,
            announcement_title=title,
            jump_url=announcement.jump_url,
            text=text,
            person=person,
            lookup_failed=lookup_failed,
        )

        channel = client.get_channel(resolve_channel_id(ChannelIds.SERVING__RIDE_COORDINATORS))
        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            logger.warning(
                f"Ride coordinators channel {ChannelIds.SERVING__RIDE_COORDINATORS} "
                "unavailable; skipping ask-rides Something else submission"
            )
            await send_error_to_discord(
                "**Unexpected Error** in ask-rides Something else submit: "
                "ride coordinators channel unavailable"
            )
            return False

        try:
            await channel.send(
                msg,
                allowed_mentions=discord.AllowedMentions.none(),
                suppress_embeds=True,
            )
        except Exception:
            logger.exception("Failed to send ask-rides Something else submission")
            await send_error_to_discord("**Unexpected Error** in ask-rides Something else submit")
            return False

        AskRidesOtherService.record_submission(user.id)
        logger.info(
            f"Ask-rides Something else submitted by user {user.id} for "
            f"{message_type.value} on announcement {announcement.id}"
        )
        return True
