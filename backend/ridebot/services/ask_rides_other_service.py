"""
Service for the "Something else" button on ask-rides announcements.

Riders whose needs don't fit any reaction option tap the button, describe what
they need in a modal, and this service forwards it to the ride coordinators
channel with enough context to act on.
"""

import logging
from datetime import datetime

import discord

from ridebot.services.pickup_info_service import Person
from ridebot.utils.feature_flags import is_flag_enabled
from shared.core.bots import get_spec
from shared.core.enums import AskRidesMessageType, BotName, FeatureFlagNames

logger = logging.getLogger(__name__)


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
        raise NotImplementedError

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
        raise NotImplementedError

    @staticmethod
    def record_submission(user_id: int, *, now: float | None = None) -> None:
        """
        Record that a user just submitted a request, starting their cooldown.

        Args:
            user_id: The Discord user's id.
            now: Override for the monotonic clock (tests).
        """
        raise NotImplementedError

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
        raise NotImplementedError

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
        raise NotImplementedError
